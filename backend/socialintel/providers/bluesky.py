from urllib.parse import quote

from ..models import Manifest, Post, Status
from ..security import RetrievalError
from .base import PlatformAdapter, public_links


class Bluesky(PlatformAdapter):
    manifest = Manifest(
        name="Bluesky",
        platform="bluesky",
        domains=["bsky.app"],
        status="EXPERIMENTAL",
        capabilities=["profile", "links", "statistics", "posts", "timeline"],
        methods=["PUBLIC API"],
        limitations="Public AppView data only. Bare usernames are tried as username.bsky.social. Custom handles and DIDs are accepted; no identity resolution.",
        documentation_url="https://docs.bsky.app/docs/api/app-bsky-actor-get-profile",
    )

    def resolve_profile_url(self, username):
        return f"https://bsky.app/profile/{quote(username, safe=':.')}"

    async def get_public_profile(self, target, ctx):
        username = self.validate_target(target, ctx)
        if "." not in username and not username.startswith("did:"):
            username += ".bsky.social"
        self.check_username(username, r"(?:did:[a-z]+:[A-Za-z0-9:._-]+|[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
        response = await ctx.network.get(
            "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
            ctx.budget,
            hosts={"public.api.bsky.app"},
            params={"actor": username},
        )
        if response.status == 404:
            return None
        data = response.json()
        if not data.get("did") or not data.get("handle"):
            raise RetrievalError(Status.LIMITED, "No usable public profile was returned.")
        profile = self.profile(
            data["handle"],
            self.resolve_profile_url(data["handle"]),
            {
                "display_name": data.get("displayName"),
                "bio": data.get("description"),
                "avatar": data.get("avatar"),
                "followers": data.get("followersCount"),
                "following": data.get("followsCount"),
                "post_count": data.get("postsCount"),
                "created_at": data.get("createdAt"),
                "public_id": data["did"],
            },
            response.url,
            account_id=data["did"],
            method="PUBLIC API",
        )
        profile.links = public_links(data.get("description", ""), profile.url)
        return profile

    async def get_public_posts(self, profile, ctx):
        response = await ctx.network.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
            ctx.budget,
            hosts={"public.api.bsky.app"},
            params={
                "actor": profile.fields["public_id"].value,
                "limit": ctx.request.limits.max_posts,
                "filter": "posts_no_replies",
            },
        )
        posts = []
        for item in response.json().get("feed", [])[: ctx.request.limits.max_posts]:
            post = item.get("post", {})
            if post.get("author", {}).get("did") != profile.fields["public_id"].value:
                continue
            record = post.get("record", {})
            uri = post.get("uri", "")
            if not uri.startswith("at://"):
                continue
            url = f"{profile.url}/post/{quote(uri.rsplit('/', 1)[-1], safe='')}"
            posts.append(
                Post(
                    id=uri,
                    url=url,
                    published_at=record.get("createdAt"),
                    text=str(record.get("text", ""))[:10000],
                    statistics={"likes": post.get("likeCount", 0)},
                    links=[link.destination for link in public_links(record.get("text", ""), url)],
                )
            )
        return posts
