from urllib.parse import quote

from ..models import Manifest
from .base import PlatformAdapter, public_links


class YouTube(PlatformAdapter):
    manifest = Manifest(
        name="YouTube",
        platform="youtube",
        domains=["youtube.com", "www.youtube.com"],
        status="API REQUIRED",
        capabilities=["profile", "links", "statistics"],
        methods=["OFFICIAL API"],
        requirements=["YOUTUBE_API_KEY"],
        limitations="Public channel metadata and visible statistics through Data API v3. Handles, channel IDs, and legacy /user/ URLs supported. Video collection is not implemented. Subscriber counts may be rounded by YouTube.",
        documentation_url="https://developers.google.com/youtube/v3/docs/channels/list",
    )

    def resolve_profile_url(self, username):
        return f"https://www.youtube.com/@{quote(username, safe='')}"

    async def get_public_profile(self, target, ctx):
        username = self.check_username(self.validate_target(target, ctx), r"[A-Za-z0-9_.-]{1,100}")
        key = (
            "id"
            if target.kind == "id" or (target.kind == "url" and "/channel/" in target.value)
            else ("forUsername" if target.kind == "url" and "/user/" in target.value else "forHandle")
        )
        response = await ctx.network.get(
            "https://www.googleapis.com/youtube/v3/channels",
            ctx.budget,
            hosts={"www.googleapis.com"},
            params={
                "part": "snippet,statistics",
                key: username,
                "key": ctx.settings.secret("YOUTUBE_API_KEY"),
            },
        )
        items = response.json().get("items", [])
        if not items:
            return None
        data = items[0]
        snippet, statistics = data.get("snippet", {}), data.get("statistics", {})
        profile = self.profile(
            snippet.get("customUrl", data["id"]).lstrip("@"),
            f"https://www.youtube.com/channel/{quote(data['id'], safe='')}",
            {
                "display_name": snippet.get("title"),
                "bio": snippet.get("description"),
                "created_at": snippet.get("publishedAt"),
                "country": snippet.get("country"),
                "subscribers": None
                if statistics.get("hiddenSubscriberCount")
                else statistics.get("subscriberCount"),
                "views": statistics.get("viewCount"),
                "post_count": statistics.get("videoCount"),
                "public_id": data["id"],
            },
            response.url,
            account_id=data["id"],
        )
        profile.links = public_links(snippet.get("description", ""), profile.url)
        return profile
