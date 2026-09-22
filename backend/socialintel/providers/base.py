"""Provider SDK. Unsupported operations are explicit, never empty fabricated data."""

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..config import Settings
from ..discovery import classify_url, entities, extract_urls
from ..models import InvestigationRequest, Link, Manifest, Profile, SourceField, Status, Target
from ..security import Budget, Network, RetrievalError, display_url, safe_url


@dataclass
class Context:
    network: Network
    budget: Budget
    settings: Settings
    request: InvestigationRequest


def plain(value) -> str:
    return BeautifulSoup(str(value or "")[:50000], "html.parser").get_text(" ", strip=True)[:10000]


def public_links(text: str, source: str, html: bool = False) -> list[Link]:
    urls = extract_urls(text)
    if html:
        soup = BeautifulSoup(text[:50000], "html.parser")
        urls += [urljoin(source, str(anchor.get("href", ""))) for anchor in soup.select("a[href]")[:50]]
    links = []
    for value in dict.fromkeys(urls):
        try:
            url = display_url(safe_url(value))
            links.append(Link(source_url=source, destination=url, kind=classify_url(url)["classification"]))
        except ValueError:
            continue
    return links[:30]


class PlatformAdapter:
    manifest: Manifest

    def configured(self, settings: Settings) -> tuple[bool, str]:
        missing = [name for name in self.manifest.requirements if not settings.secret(name)]
        return not missing, "Configure " + ", ".join(
            missing
        ) if missing else "Configured; availability requires a live check."

    def normalize_username(self, value: str) -> str:
        return value.lstrip("@").strip()

    def validate_target(self, target: Target, ctx: Context) -> str:
        if target.kind == "display_name":
            raise RetrievalError(
                Status.UNSUPPORTED, "Display names require public web search; they are not unique usernames."
            )
        if target.kind == "url":
            url = safe_url(target.value, set(self.manifest.domains))
            info = classify_url(url, urlsplit(ctx.settings.mastodon_instance).hostname)
            if info["platform"] != self.manifest.platform or not info["username"]:
                raise RetrievalError(
                    Status.UNSUPPORTED, "Provide a public profile URL supported by this adapter."
                )
            return info["username"]
        return self.normalize_username(target.value)

    def resolve_profile_url(self, username: str) -> str:
        raise RetrievalError(Status.UNSUPPORTED, "Profile URL resolution is unsupported by this provider.")

    async def get_public_profile(self, target: Target, ctx: Context) -> Profile | None:
        raise RetrievalError(Status.UNSUPPORTED, self.manifest.limitations)

    async def get_public_posts(self, profile: Profile, ctx: Context):
        raise RetrievalError(Status.UNSUPPORTED, "Public posts are unsupported by this provider.")

    def get_public_links(self, profile: Profile):
        return profile.links

    def get_public_statistics(self, profile: Profile):
        return {
            name: value
            for name, value in profile.fields.items()
            if name
            in {"followers", "following", "post_count", "public_repos", "subscribers", "views", "karma"}
        }

    def get_public_media_metadata(self, profile: Profile):
        if "media" not in self.supported_features():
            raise RetrievalError(Status.UNSUPPORTED, "Public media metadata is unsupported by this provider.")
        return [media for post in profile.posts for media in post.media]

    def get_public_relationships(self, profile: Profile):
        raise RetrievalError(Status.UNSUPPORTED, "Follower enumeration is not implemented.")

    def extract_public_entities(self, profile: Profile):
        return entities(" ".join(str(field.value) for field in profile.fields.values()), profile.url)

    def get_account_metadata(self, profile: Profile):
        return profile.fields

    def get_source_urls(self, profile: Profile):
        return list(dict.fromkeys([profile.url] + [field.source_url for field in profile.fields.values()]))

    def supported_features(self):
        return self.manifest.capabilities

    async def health_check(self, ctx: Context) -> dict:
        ready, reason = self.configured(ctx.settings)
        return {
            "status": "EXPERIMENTAL" if ready else "API REQUIRED",
            "reason": reason,
            "capabilities": self.supported_features(),
            "response_time_ms": None,
            "last_successful_check": None,
            "probe": "Configuration only; no live request made.",
        }

    def profile(self, username, url, data: dict, source: str, *, account_id=None, method="OFFICIAL API"):
        source, url = display_url(safe_url(source)), display_url(safe_url(url))
        values = {"username": username, "profile_url": url, **data}
        fields = {
            key: SourceField(
                value=value[:10000] if isinstance(value, str) else value,
                source_url=source,
                method=method,
                provider=self.manifest.platform,
            )
            for key, value in values.items()
            if value is not None and value != ""
        }
        return Profile(
            id=f"{self.manifest.platform}:{account_id or username}",
            platform=self.manifest.platform,
            username=str(username),
            url=url,
            fields=fields,
            provider=self.manifest.platform,
            method=method,
        )

    def check_username(self, value, pattern):
        if not re.fullmatch(pattern, value):
            raise RetrievalError(Status.UNSUPPORTED, "Identifier format is unsupported by this provider.")
        return value
