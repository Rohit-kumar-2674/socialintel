"""HTTPS-only retrieval with connection-time DNS pinning and bounded responses."""

import asyncio
import ipaddress
import json
import math
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpcore
import httpx

from .models import Limits, Status

MAX_RESPONSE = 1_000_000
SECRET_KEYS = {"key", "api_key", "apikey", "token", "access_token", "auth", "authorization", "password"}


def public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped:
                return public_ip(str(address.ipv4_mapped))
            # Translation/tunneling ranges can disguise a private IPv4 destination.
            if any(
                address in ipaddress.ip_network(network)
                for network in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32")
            ):
                return False
        return (
            address.is_global
            and not address.is_reserved
            and not address.is_multicast
            and not address.is_unspecified
        )
    except ValueError:
        return False


def safe_url(value: str, allowed_hosts: set[str] | None = None) -> str:
    if len(value) > 2000 or any(ord(char) < 33 for char in value) or "\\" in value:
        raise ValueError("Invalid URL characters or length.")
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid URL.") from error
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Only public HTTPS URLs on port 443 without credentials are accepted.")
    if host.endswith(".") or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local hostnames are not accepted.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or ":" in host or "%" in host:
            raise ValueError("A fully qualified public hostname is required.")
    else:
        if not public_ip(host):
            raise ValueError("Non-public IP addresses are blocked.")
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError("This domain is not allowed for the provider.")
    display_host = f"[{host}]" if ":" in host else host
    return urlunsplit(("https", display_host, parsed.path or "/", parsed.query, ""))


def display_url(value: str) -> str:
    parsed = urlsplit(value)
    query = urlencode([(key, val) for key, val in parse_qsl(parsed.query) if key.lower() not in SECRET_KEYS])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Connect to the checked IP; httpcore retains the original TLS hostname."""

    def __init__(self, backend=None, resolver=None):
        self.backend = backend or httpcore.AnyIOBackend()
        self.resolver = resolver or socket.getaddrinfo

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if port != 443:
            raise httpcore.ConnectError("Only HTTPS port 443 is permitted.")
        try:
            records = await asyncio.wait_for(
                asyncio.to_thread(self.resolver, host, port, type=socket.SOCK_STREAM), timeout=timeout or 10
            )
        except (OSError, TimeoutError) as error:
            raise httpcore.ConnectError("Public host resolution failed.") from error
        addresses = list(dict.fromkeys(record[4][0] for record in records))
        if not addresses or not all(public_ip(address) for address in addresses):
            raise httpcore.ConnectError("DNS resolved to a non-public address.")
        # No second hostname resolution: the connection uses this exact checked IP.
        return await self.backend.connect_tcp(
            addresses[0], port, timeout=timeout, local_address=None, socket_options=socket_options
        )

    async def connect_unix_socket(self, *args, **kwargs):
        raise httpcore.ConnectError("Unix sockets are not permitted.")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class PublicTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        super().__init__(trust_env=False, retries=0)
        # The private pool integration is isolated here and tested against pinned
        # httpx 0.28.1 / httpcore 1.0.9. No proxies or environment proxy inheritance.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PublicNetworkBackend(),
            max_connections=4,
            max_keepalive_connections=4,
            retries=0,
        )


class RetrievalError(Exception):
    def __init__(self, status: Status, reason: str, retry_at: str | None = None):
        super().__init__(reason)
        self.status, self.reason, self.retry_at = status, reason, retry_at


class Budget:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.requests = 0
        self.pages = 0
        self.started = time.monotonic()

    def take(self):
        if time.monotonic() - self.started >= self.limits.max_seconds:
            raise RetrievalError(Status.TIMEOUT, "Investigation time limit reached.")
        if self.requests >= self.limits.max_requests:
            raise RetrievalError(Status.LIMITED, "Investigation request limit reached.")
        self.requests += 1


@dataclass
class Document:
    status: int
    data: bytes
    url: str
    headers: dict[str, str]

    def json(self):
        try:
            return json.loads(self.data)
        except (ValueError, UnicodeError) as error:
            raise RetrievalError(Status.LIMITED, "Provider returned a non-JSON response.") from error

    def text(self):
        return self.data.decode("utf-8", errors="replace")


class Network:
    def __init__(self, transport=None):
        self.client = httpx.AsyncClient(
            transport=transport or PublicTransport(),
            trust_env=False,
            timeout=httpx.Timeout(12, connect=8),
            follow_redirects=False,
            headers={"User-Agent": "SocialIntel/0.1 (public-source research)", "Accept-Encoding": "identity"},
        )
        self.slots = asyncio.Semaphore(4)
        self.locks: dict[str, asyncio.Lock] = {}
        self.last: dict[str, float] = {}
        self.cooldowns: dict[str, float] = {}
        self.on_cooldown = None

    async def close(self):
        await self.client.aclose()

    async def get(
        self,
        url: str,
        budget: Budget,
        *,
        hosts: set[str],
        headers=None,
        params=None,
        interval: float = 1.0,
        allow_404: bool = True,
    ) -> Document:
        url = safe_url(url, hosts)
        host = urlsplit(url).hostname
        lock = self.locks.setdefault(host, asyncio.Lock())
        for attempt in range(2):
            async with lock:
                if self.cooldowns.get(host, 0) > time.time():
                    until = datetime.fromtimestamp(self.cooldowns[host], UTC).isoformat()
                    raise RetrievalError(Status.RATE_LIMITED, "Provider cooldown is active.", until)
                delay = interval - (time.monotonic() - self.last.get(host, 0))
                if delay > 0:
                    await asyncio.sleep(delay)
                budget.take()
                self.last[host] = time.monotonic()
                try:
                    async with (
                        self.slots,
                        self.client.stream("GET", url, params=params, headers=headers) as response,
                    ):
                        code = response.status_code
                        if code == 429 or (
                            code == 403 and response.headers.get("x-ratelimit-remaining") == "0"
                        ):
                            seconds = 60.0
                            retry = response.headers.get("retry-after", "")
                            try:
                                seconds = max(seconds, float(retry))
                            except ValueError:
                                try:
                                    seconds = max(
                                        seconds,
                                        (parsedate_to_datetime(retry) - datetime.now(UTC)).total_seconds(),
                                    )
                                except (ValueError, TypeError, OverflowError):
                                    pass
                            try:
                                seconds = max(
                                    seconds, float(response.headers.get("x-ratelimit-reset", 0)) - time.time()
                                )
                            except ValueError:
                                pass
                            seconds = min(seconds, 86400 * 365) if math.isfinite(seconds) else 86400 * 365
                            self.cooldowns[host] = time.time() + seconds
                            if self.on_cooldown:
                                self.on_cooldown(host, self.cooldowns[host])
                            until = (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()
                            raise RetrievalError(
                                Status.RATE_LIMITED, "Provider rate limit reached; no retry performed.", until
                            )
                        if code == 401:
                            raise RetrievalError(
                                Status.AUTH_REQUIRED, "Provider rejected or requires API authorization."
                            )
                        if code == 403:
                            raise RetrievalError(
                                Status.LIMITED, "Provider denied this request; no bypass attempted."
                            )
                        if 300 <= code < 400:
                            # Redirects never receive credentials or initiate another connection.
                            location = response.headers.get("location", "")
                            if location.startswith("https://"):
                                try:
                                    safe_url(location, hosts)
                                except ValueError:
                                    raise RetrievalError(
                                        Status.LIMITED, "Provider redirect points outside its allowed domain."
                                    ) from None
                            raise RetrievalError(
                                Status.LIMITED, "Redirect was not followed. Use the canonical source URL."
                            )
                        if code >= 500 and attempt == 0:
                            await asyncio.sleep(1)
                            continue
                        if code >= 400 and not (code == 404 and allow_404):
                            raise RetrievalError(Status.UNAVAILABLE, f"Provider returned HTTP {code}.")
                        if response.headers.get("content-encoding", "identity").lower() not in (
                            "",
                            "identity",
                        ):
                            raise RetrievalError(
                                Status.LIMITED, "Compressed response rejected by the bounded fetcher."
                            )
                        data = bytearray()
                        if response.is_stream_consumed:
                            if len(response.content) > MAX_RESPONSE:
                                raise RetrievalError(
                                    Status.LIMITED, "Provider response exceeded the 1 MB limit."
                                )
                            return Document(
                                code, response.content, display_url(str(response.url)), dict(response.headers)
                            )
                        async for chunk in response.aiter_raw():
                            if len(data) + len(chunk) > MAX_RESPONSE:
                                raise RetrievalError(
                                    Status.LIMITED, "Provider response exceeded the 1 MB limit."
                                )
                            data.extend(chunk)
                        return Document(
                            code, bytes(data), display_url(str(response.url)), dict(response.headers)
                        )
                except httpx.TimeoutException as error:
                    raise RetrievalError(Status.TIMEOUT, "Provider request timed out.") from error
                except (httpx.HTTPError, httpcore.NetworkError) as error:
                    raise RetrievalError(
                        Status.UNAVAILABLE, "Secure connection to the public provider failed."
                    ) from error
        raise RetrievalError(Status.UNAVAILABLE, "Provider is temporarily unavailable.")
