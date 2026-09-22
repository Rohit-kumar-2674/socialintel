"""Version 1 public provider SDK; plugins are trusted local code, not a sandbox."""

import re
from urllib.parse import urlsplit

from .config import Settings
from .models import Link, Manifest, Post, Profile, SourceField, Status, Target, Verification
from .providers.base import Context, PlatformAdapter, plain, public_links
from .security import RetrievalError, display_url, safe_url

SDK_VERSION = "1"
CAPABILITIES = frozenset({"profile", "links", "statistics", "posts", "timeline", "media", "metadata"})
METHODS = frozenset({"OFFICIAL API", "PUBLIC API", "PUBLIC WEBPAGE"})

__all__ = [
    "SDK_VERSION", "Context", "Settings", "PlatformAdapter", "Manifest", "Profile", "Post",
    "SourceField", "Link", "Target", "Status", "Verification", "RetrievalError", "safe_url",
    "display_url", "plain", "public_links", "validate_provider", "validate_profile",
]


def validate_provider(provider: PlatformAdapter) -> Manifest:
    """Validate declarations, not the trustworthiness of executable plugin code."""
    if not isinstance(provider, PlatformAdapter):
        raise ValueError("Expected PlatformAdapter.")
    manifest = Manifest.model_validate(provider.manifest.model_dump()).model_copy(deep=True)
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", manifest.version):
        raise ValueError("A semantic version is required.")
    if manifest.status not in {"EXPERIMENTAL", "API REQUIRED", "NOT IMPLEMENTED"}:
        raise ValueError("Manifest readiness cannot claim live availability.")
    if not manifest.capabilities or not set(manifest.capabilities) <= CAPABILITIES:
        raise ValueError("Declare only supported SDK capabilities.")
    if "profile" not in manifest.capabilities or manifest.status == "NOT IMPLEMENTED":
        raise ValueError("An installed collection plugin must implement public profiles.")
    if not manifest.methods or not set(manifest.methods) <= METHODS:
        raise ValueError("Only explicit public collection methods are accepted.")
    if not manifest.limitations.strip() or not manifest.name.strip():
        raise ValueError("Name and limitations are required.")
    safe_url(manifest.documentation_url)
    if not manifest.domains or len(manifest.domains) > 20:
        raise ValueError("Declare between one and twenty public profile domains.")
    for domain in manifest.domains:
        url = safe_url("https://" + domain)
        if urlsplit(url).hostname != domain or urlsplit(url).path != "/" or urlsplit(url).query:
            raise ValueError("Domains must be literal lowercase public hostnames.")
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", name) for name in manifest.requirements):
        raise ValueError("Requirements must be environment variable names, never secret values.")
    if "posts" in manifest.capabilities and type(provider).get_public_posts is PlatformAdapter.get_public_posts:
        raise ValueError("Posts capability requires an implementation.")
    if type(provider).get_public_profile is PlatformAdapter.get_public_profile:
        raise ValueError("Public profile collection requires an implementation.")
    return manifest


def validate_profile(value: Profile, adapter: PlatformAdapter) -> Profile:
    """Check source contracts before any observation is persisted as verified data.

    This does not establish that the endpoint itself is honest or that two profiles
    represent one person. Those remain separate from source observation.
    """
    try:
        profile = Profile.model_validate(value.model_dump()).model_copy(deep=True)
        platform = adapter.manifest.platform
        if profile.platform != platform or profile.provider != platform:
            raise ValueError("Provider mismatch")
        if profile.verification != Verification.VERIFIED or profile.method not in METHODS:
            raise ValueError("Unverified data cannot enter the source-verified collection path")
        hosts = set(adapter.manifest.domains) if adapter.manifest.plugin else None
        profile.url = display_url(safe_url(profile.url, hosts))
        for field in profile.fields.values():
            if field.provider != platform or field.verification != Verification.VERIFIED or field.method not in METHODS:
                raise ValueError("Invalid field provenance")
            field.source_url = display_url(safe_url(field.source_url))
        for link in profile.links:
            link.source_url = display_url(safe_url(link.source_url))
            link.destination = display_url(safe_url(link.destination))
        for post in profile.posts:
            post.url = display_url(safe_url(post.url))
            post.links = [display_url(safe_url(link)) for link in post.links]
        return profile
    except (ValueError, AttributeError, TypeError):
        raise RetrievalError(Status.ERROR, "Provider output failed the public source/provenance contract.") from None
