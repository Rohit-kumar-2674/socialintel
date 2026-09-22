"""Honest capability catalog and explicitly opted-in trusted plugins."""

import importlib
import re

from ..discovery import DOMAINS
from ..models import Manifest
from .base import PlatformAdapter
from .bluesky import Bluesky
from .github import GitHub
from .mastodon import Mastodon
from .reddit import Reddit
from .twitch import Twitch
from .website import Website
from .youtube import YouTube

UNIMPLEMENTED = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "X / Twitter",
    "threads": "Threads",
    "tiktok": "TikTok",
    "snapchat": "Snapchat",
    "linkedin": "LinkedIn",
    "pinterest": "Pinterest",
    "tumblr": "Tumblr",
    "telegram": "Telegram",
    "discord": "Discord",
    "patreon": "Patreon",
    "onlyfans": "OnlyFans",
    "fansly": "Fansly",
    "soundcloud": "SoundCloud",
    "spotify": "Spotify",
    "steam": "Steam",
    "medium": "Medium",
    "quora": "Quora",
    "flickr": "Flickr",
    "vk": "VK",
    "weibo": "Weibo",
}


class Unsupported(PlatformAdapter):
    def __init__(self, platform, name):
        domains = [domain for domain, value in DOMAINS.items() if value == platform]
        self.manifest = Manifest(
            name=name,
            platform=platform,
            domains=domains,
            status="NOT IMPLEMENTED",
            limitations="UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded.",
            documentation_url=f"https://{domains[0]}" if domains else "https://github.com",
        )

    def configured(self, settings):
        return False, self.manifest.limitations


class Registry:
    def __init__(self, settings):
        adapters = [GitHub(), Bluesky(), Reddit(), Mastodon(settings), YouTube(), Twitch(), Website()]
        adapters += [Unsupported(key, value) for key, value in UNIMPLEMENTED.items()]
        self.providers = {adapter.manifest.platform: adapter for adapter in adapters}
        self.plugin_errors = []
        for spec in settings.plugins[:10]:
            try:
                if not re.fullmatch(r"[a-zA-Z_][\w.]*:[a-zA-Z_]\w*", spec):
                    raise ValueError("Invalid entry point")
                module, factory = spec.split(":")
                provider = getattr(importlib.import_module(module), factory)(settings)
                if not isinstance(provider, PlatformAdapter):
                    raise ValueError("Expected PlatformAdapter")
                from ..sdk import validate_provider

                provider.manifest = validate_provider(provider)
                if provider.manifest.platform in self.providers:
                    raise ValueError("Duplicate platform")
                if not provider.manifest.capabilities or len(self.providers) >= 40:
                    raise ValueError("Invalid capabilities or provider limit")
                provider.manifest.plugin = True
                self.providers[provider.manifest.platform] = provider
            except Exception:
                # Plugin exceptions can contain credentials; do not expose them.
                self.plugin_errors.append(
                    {
                        "entry_point": spec,
                        "error": "Plugin could not be loaded; inspect trusted installation and manifest.",
                    }
                )

    def get(self, name):
        if name not in self.providers:
            raise ValueError("Unknown platform.")
        return self.providers[name]

    @staticmethod
    def configuration(adapter, settings):
        try:
            ready, reason = adapter.configured(settings)
            if type(ready) is not bool or not isinstance(reason, str):
                raise ValueError("Invalid configuration result")
            return ready, reason
        except Exception:
            return False, "Provider configuration failed; inspect the trusted plugin locally."

    def catalog(self, settings):
        result = []
        for adapter in self.providers.values():
            ready, reason = self.configuration(adapter, settings)
            result.append(
                {**adapter.manifest.model_dump(), "configured": ready, "configuration_note": reason}
            )
        return result

    def discovery_providers(self, settings):
        return [
            provider
            for provider in self.providers.values()
            if provider.manifest.platform != "website"
            and provider.manifest.capabilities
            and self.configuration(provider, settings)[0]
        ]
