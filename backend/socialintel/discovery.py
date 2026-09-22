"""Conservative identifiers and candidate classification; never identity resolution."""

import re
import unicodedata
from urllib.parse import unquote, urlsplit

from .models import Target
from .security import safe_url

DOMAINS = {
    "github.com": "github",
    "reddit.com": "reddit",
    "www.reddit.com": "reddit",
    "bsky.app": "bluesky",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "twitch.tv": "twitch",
    "www.twitch.tv": "twitch",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "x.com": "twitter",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "threads.net": "threads",
    "www.threads.net": "threads",
    "threads.com": "threads",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "snapchat.com": "snapchat",
    "www.snapchat.com": "snapchat",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "pinterest.com": "pinterest",
    "www.pinterest.com": "pinterest",
    "tumblr.com": "tumblr",
    "patreon.com": "patreon",
    "www.patreon.com": "patreon",
    "onlyfans.com": "onlyfans",
    "fansly.com": "fansly",
    "soundcloud.com": "soundcloud",
    "open.spotify.com": "spotify",
    "steamcommunity.com": "steam",
    "medium.com": "medium",
    "quora.com": "quora",
    "www.quora.com": "quora",
    "flickr.com": "flickr",
    "www.flickr.com": "flickr",
    "vk.com": "vk",
    "weibo.com": "weibo",
    "t.me": "telegram",
    "discord.com": "discord",
}
RESERVED = {
    "about",
    "explore",
    "search",
    "login",
    "signup",
    "settings",
    "help",
    "privacy",
    "terms",
    "intent",
    "share",
    "home",
    "features",
    "pricing",
    "orgs",
    "topics",
}


def classify_url(value: str, mastodon_host: str | None = None) -> dict:
    try:
        url = safe_url(value)
    except ValueError:
        return {"url": value, "platform": None, "classification": "UNKNOWN", "username": None, "safe": False}
    parsed = urlsplit(url)
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    platform = DOMAINS.get(parsed.hostname)
    if parsed.hostname == mastodon_host:
        platform = "mastodon"
    username = None
    category = "PUBLIC MENTION" if platform else "PERSONAL WEBSITE"
    if platform == "github" and len(parts) == 1 and parts[0].lower() not in RESERVED:
        username, category = parts[0], "DEVELOPER PROFILE"
    elif platform == "reddit" and len(parts) == 2 and parts[0] in ("user", "u"):
        username, category = parts[1], "FORUM ACCOUNT"
    elif platform == "bluesky" and len(parts) == 2 and parts[0] == "profile":
        username, category = parts[1], "SOCIAL PROFILE"
    elif platform == "youtube" and (
        (len(parts) == 1 and parts[0].startswith("@"))
        or (len(parts) == 2 and parts[0] in ("channel", "user"))
    ):
        username, category = parts[-1].lstrip("@"), "VIDEO CHANNEL"
    elif platform == "mastodon" and len(parts) == 1 and parts[0].startswith("@"):
        username, category = parts[0][1:], "SOCIAL PROFILE"
    elif platform == "linkedin" and len(parts) == 2 and parts[0] in ("in", "company"):
        username, category = parts[1], "SOCIAL PROFILE" if parts[0] == "in" else "ORGANIZATION PAGE"
    elif platform in ("onlyfans", "fansly", "patreon") and len(parts) == 1:
        username, category = parts[0].lstrip("@"), "CREATOR PROFILE"
    elif platform == "snapchat" and len(parts) == 2 and parts[0] == "add":
        username, category = parts[1], "SOCIAL PROFILE"
    elif platform and len(parts) == 1 and parts[0].lower() not in RESERVED:
        username, category = parts[0].lstrip("@"), "SOCIAL PROFILE"
    elif platform and any(
        part in ("status", "post", "posts", "p", "reel", "comments", "video", "watch") for part in parts
    ):
        category = "SOCIAL POST"
    elif not platform and any(part in ("blog", "article", "news") for part in parts):
        category = "BLOG" if "blog" in parts else "NEWS ARTICLE"
    return {"url": url, "platform": platform, "classification": category, "username": username, "safe": True}


def normalize(raw: str, kind: str = "auto", mastodon_host: str | None = None) -> Target:
    value = unicodedata.normalize("NFKC", raw).strip()
    if not value or len(value) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Invalid target.")
    if kind == "auto":
        kind = (
            "url"
            if "://" in value
            else "id"
            if value.startswith("did:")
            else ("display_name" if any(char.isspace() for char in value) else "username")
        )
    platform = None
    if kind == "url":
        value = safe_url(value)
        platform = classify_url(value, mastodon_host)["platform"]
    elif kind == "username":
        value = value.lstrip("@")
        if not re.fullmatch(r"[\w.@-]{1,253}", value, flags=re.ASCII):
            raise ValueError(
                "Usernames may contain letters, digits, dots, underscores, hyphens, and a federated host."
            )
    elif kind == "id" and not re.fullmatch(r"[A-Za-z0-9:._-]{1,253}", value):
        raise ValueError("Unsupported identifier characters.")
    return Target(raw=raw, value=value, kind=kind, platform=platform)


def variants(username: str, maximum: int = 3) -> list[str]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", username)
    if not match:
        return []
    return [f"{match[1]}{separator}{match[2]}" for separator in ("_", ".", "-")][: min(maximum, 3)]


def extract_urls(text: str) -> list[str]:
    values = []
    for match in re.findall(r"https://[^\s<>\"']+", text):
        try:
            candidate = safe_url(match.rstrip(".,;!?)"))
            if candidate not in values:
                values.append(candidate)
        except ValueError:
            pass
    return values[:30]


def entities(text: str, source_url: str, contacts: bool = False) -> list[dict]:
    items = []
    for kind, pattern in [
        ("HASHTAG", r"(?<!\w)#[\w]{1,64}"),
        ("PUBLIC USERNAME", r"(?<![\w@])@[\w.-]{1,100}"),
    ]:
        for value in list(dict.fromkeys(re.findall(pattern, text)))[:40]:
            items.append(
                {
                    "type": kind,
                    "value": value,
                    "source_url": source_url,
                    "basis": "SOURCE-PROVIDED TEXT; REGEX EXTRACTION",
                }
            )
    for url in extract_urls(text):
        items.append(
            {"type": "WEBSITE", "value": url, "source_url": source_url, "basis": "SOURCE-PROVIDED TEXT"}
        )
    if contacts:
        for value in list(
            dict.fromkeys(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text))
        )[:10]:
            items.append(
                {
                    "type": "PUBLIC EMAIL",
                    "value": value,
                    "source_url": source_url,
                    "basis": "EXPLICIT SOURCE TEXT; NOT AN OWNERSHIP CLAIM",
                }
            )
    return items
