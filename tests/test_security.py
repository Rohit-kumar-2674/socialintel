import socket

import httpcore
import httpx
import pytest
from socialintel.models import Limits, Status
from socialintel.security import (
    Budget,
    Network,
    PublicNetworkBackend,
    RetrievalError,
    display_url,
    public_ip,
    safe_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://localhost/",
        "https://127.0.0.1/",
        "https://10.0.0.1/",
        "https://172.16.1.2/",
        "https://192.168.1.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",
        "https://[64:ff9b::7f00:1]/",
        "https://user:password@example.org/",
        "https://example.org:444/",
        "https://example.org./",
        "https://example.org\\@127.0.0.1/",
        "https://2130706433/",
        "https://example.org/\nheader",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        safe_url(url)


def test_exact_domain_and_query_redaction():
    with pytest.raises(ValueError):
        safe_url("https://github.com.attacker.example/profile", {"github.com"})
    assert safe_url("https://github.com/example#bio", {"github.com"}) == "https://github.com/example"
    assert (
        display_url("https://api.example.org/?q=public&key=secret&access_token=private")
        == "https://api.example.org/?q=public"
    )


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "0.0.0.0",
        "100.64.0.1",
        "224.0.0.1",
        "255.255.255.255",
        "::",
        "fc00::1",
        "fe80::1",
        "2002:7f00:1::",
        "64:ff9b::a00:1",
    ],
)
def test_non_public_networks(address):
    assert not public_ip(address)


async def test_dns_pinning_and_mixed_response_rejection():
    calls = []

    class Backend:
        async def connect_tcp(self, *args, **kwargs):
            calls.append(args)
            return "stream"

    def records(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    backend = PublicNetworkBackend(Backend(), records)
    assert await backend.connect_tcp("public.example", 443) == "stream"
    assert calls == [("8.8.8.8", 443)]
    backend.resolver = lambda *args, **kwargs: (
        records() + [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    )
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("rebound.example", 443)
    assert len(calls) == 1
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("public.example", 80)
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_unix_socket("/tmp/socket")


@pytest.mark.parametrize(
    "code,expected",
    [
        (401, Status.AUTH_REQUIRED),
        (403, Status.LIMITED),
        (429, Status.RATE_LIMITED),
        (500, Status.UNAVAILABLE),
    ],
)
async def test_statuses_never_become_not_found(code, expected):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(code, json={"secret": "not exposed"}, headers={"retry-after": "Infinity"})

    network = Network(httpx.MockTransport(handler))
    try:
        with pytest.raises(RetrievalError) as result:
            await network.get(
                "https://example.org/profile", Budget(Limits()), hosts={"example.org"}, interval=0
            )
        assert result.value.status == expected
        assert "secret" not in str(result.value)
        assert len(requests) == (2 if code == 500 else 1)
        if code == 429:
            with pytest.raises(RetrievalError):
                await network.get(
                    "https://example.org/profile", Budget(Limits()), hosts={"example.org"}, interval=0
                )
            assert len(requests) == 1
    finally:
        await network.close()


async def test_redirect_never_forwards_credentials():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/secret"})

    network = Network(httpx.MockTransport(handler))
    with pytest.raises(RetrievalError):
        await network.get(
            "https://example.org/profile",
            Budget(Limits()),
            hosts={"example.org"},
            headers={"Authorization": "Bearer fixture"},
        )
    assert len(calls) == 1
    await network.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"x" * 1_000_001),
        httpx.Response(200, content=b"", headers={"content-encoding": "br"}),
    ],
)
async def test_bounded_response(response):
    network = Network(httpx.MockTransport(lambda _: response))
    with pytest.raises(RetrievalError, match="limit|Compressed"):
        await network.get("https://example.org/", Budget(Limits()), hosts={"example.org"})
    await network.close()


def test_request_budget_is_hard_limit():
    budget = Budget(Limits(max_requests=1))
    budget.take()
    with pytest.raises(RetrievalError, match="request limit"):
        budget.take()
