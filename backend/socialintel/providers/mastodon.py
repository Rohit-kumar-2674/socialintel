from urllib.parse import quote, urlsplit

from ..models import Manifest, Post, Status
from ..security import RetrievalError, safe_url
from .base import PlatformAdapter, plain, public_links


class Mastodon(PlatformAdapter):
    def __init__(self, settings):
        self.instance = safe_url(settings.mastodon_instance).rstrip("/")
        if urlsplit(self.instance).path or urlsplit(self.instance).query:
            raise ValueError("MASTODON_INSTANCE must be an HTTPS origin without a path or query.")
        self.host = urlsplit(self.instance).hostname
        self.manifest = Manifest(
            name="Mastodon",
            platform="mastodon",
            domains=[self.host],
            status="API REQUIRED",
            capabilities=["profile", "links", "statistics", "posts", "timeline", "media"],
            methods=["OFFICIAL API"],
            requirements=["MASTODON_ACCESS_TOKEN"],
            limitations="Queries one configured instance; not a search of the federation. Requires read:accounts (and read:statuses for posts). Locked accounts are not collected; only visibility=public statuses are retained.",
            documentation_url="https://docs.joinmastodon.org/methods/accounts/",
        )

    def resolve_profile_url(self, username):
        return f"{self.instance}/@{quote(username, safe='@.')}"

    def headers(self, ctx):
        return {"Authorization": f"Bearer {ctx.settings.secret('MASTODON_ACCESS_TOKEN')}"}

    async def get_public_profile(self, target, ctx):
        username = self.check_username(
            self.validate_target(target, ctx), r"[A-Za-z0-9_.-]+(?:@[A-Za-z0-9.-]+)?"
        )
        response = await ctx.network.get(
            f"{self.instance}/api/v1/accounts/lookup",
            ctx.budget,
            hosts={self.host},
            headers=self.headers(ctx),
            params={"acct": username},
        )
        if response.status == 404:
            return None
        data = response.json()
        if data.get("locked") or data.get("suspended"):
            raise RetrievalError(
                Status.LIMITED,
                "NOT PUBLICLY AVAILABLE: this adapter does not collect locked or suspended accounts.",
            )
        profile = self.profile(
            data["acct"],
            data["url"],
            {
                "display_name": plain(data.get("display_name")),
                "bio": plain(data.get("note")),
                "avatar": data.get("avatar_static"),
                "followers": data.get("followers_count"),
                "following": data.get("following_count"),
                "post_count": data.get("statuses_count"),
                "created_at": data.get("created_at"),
                "public_id": data["id"],
            },
            response.url,
            account_id=data["id"],
        )
        profile.links = public_links(data.get("note", ""), profile.url, html=True)
        for field in data.get("fields", [])[:8]:
            profile.links += public_links(field.get("value", ""), profile.url, html=True)
        return profile

    async def get_public_posts(self, profile, ctx):
        response = await ctx.network.get(
            f"{self.instance}/api/v1/accounts/{quote(str(profile.fields['public_id'].value), safe='')}/statuses",
            ctx.budget,
            hosts={self.host},
            headers=self.headers(ctx),
            params={
                "limit": ctx.request.limits.max_posts,
                "exclude_reblogs": "true",
                "exclude_replies": "true",
            },
        )
        posts = []
        for item in response.json()[: ctx.request.limits.max_posts]:
            if item.get("visibility") != "public" or item.get("reblog") or not item.get("url"):
                continue
            if str(item.get("account", {}).get("id")) != str(profile.fields["public_id"].value):
                continue
            media = [
                {
                    "type": value.get("type"),
                    "source_page": item["url"],
                    "description": plain(value.get("description")),
                    "width": value.get("meta", {}).get("original", {}).get("width"),
                    "height": value.get("meta", {}).get("original", {}).get("height"),
                }
                for value in item.get("media_attachments", [])[:4]
            ]
            posts.append(
                Post(
                    id=item["id"],
                    url=item["url"],
                    published_at=item.get("created_at"),
                    text=plain(item.get("content")),
                    statistics={"favourites": item.get("favourites_count", 0)},
                    media=media,
                    links=[
                        link.destination
                        for link in public_links(item.get("content", ""), item["url"], html=True)
                    ],
                )
            )
        return posts
