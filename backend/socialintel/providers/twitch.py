from urllib.parse import quote

from ..models import Manifest
from .base import PlatformAdapter, public_links


class Twitch(PlatformAdapter):
    manifest = Manifest(
        name="Twitch",
        platform="twitch",
        domains=["twitch.tv", "www.twitch.tv"],
        status="API REQUIRED",
        capabilities=["profile", "links"],
        methods=["OFFICIAL API"],
        requirements=["TWITCH_CLIENT_ID", "TWITCH_ACCESS_TOKEN"],
        limitations="Public Helix profile fields with an app access token. Email, follower lists, subscriber data, live location, and deprecated view counts are never collected. Posts are not implemented.",
        documentation_url="https://dev.twitch.tv/docs/api/reference/#get-users",
    )

    def resolve_profile_url(self, username):
        return f"https://www.twitch.tv/{quote(username, safe='')}"

    async def get_public_profile(self, target, ctx):
        username = self.check_username(self.validate_target(target, ctx), r"[A-Za-z0-9_]{1,25}")
        response = await ctx.network.get(
            "https://api.twitch.tv/helix/users",
            ctx.budget,
            hosts={"api.twitch.tv"},
            params={"id" if target.kind == "id" else "login": username},
            headers={
                "Client-Id": ctx.settings.secret("TWITCH_CLIENT_ID"),
                "Authorization": f"Bearer {ctx.settings.secret('TWITCH_ACCESS_TOKEN')}",
            },
        )
        items = response.json().get("data", [])
        if not items:
            return None
        data = items[0]
        profile = self.profile(
            data["login"],
            self.resolve_profile_url(data["login"]),
            {
                "display_name": data.get("display_name"),
                "bio": data.get("description"),
                "account_type": data.get("broadcaster_type"),
                "avatar": data.get("profile_image_url"),
                "created_at": data.get("created_at"),
                "public_id": data["id"],
            },
            response.url,
            account_id=data["id"],
        )
        profile.links = public_links(data.get("description", ""), profile.url)
        return profile
