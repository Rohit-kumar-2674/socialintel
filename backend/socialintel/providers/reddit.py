from datetime import UTC, datetime
from urllib.parse import quote

from ..models import Manifest, Post
from .base import PlatformAdapter, public_links


class Reddit(PlatformAdapter):
    manifest = Manifest(
        name="Reddit",
        platform="reddit",
        domains=["reddit.com", "www.reddit.com"],
        status="API REQUIRED",
        capabilities=["profile", "links", "statistics", "posts", "timeline"],
        methods=["OFFICIAL API"],
        requirements=["REDDIT_ACCESS_TOKEN", "REDDIT_USER_AGENT"],
        limitations="Requires approved Reddit API access and an operator-supplied OAuth token. Only posts explicitly marked as belonging to public communities are collected. No token acquisition or private community access.",
        documentation_url="https://www.reddit.com/dev/api/",
    )

    def resolve_profile_url(self, username):
        return f"https://www.reddit.com/user/{quote(username, safe='')}/"

    def headers(self, ctx):
        return {
            "Authorization": f"Bearer {ctx.settings.secret('REDDIT_ACCESS_TOKEN')}",
            "User-Agent": ctx.settings.secret("REDDIT_USER_AGENT"),
        }

    async def get_public_profile(self, target, ctx):
        username = self.check_username(self.validate_target(target, ctx), r"[A-Za-z0-9_-]{3,20}")
        response = await ctx.network.get(
            f"https://oauth.reddit.com/user/{username}/about",
            ctx.budget,
            hosts={"oauth.reddit.com"},
            headers=self.headers(ctx),
        )
        if response.status == 404:
            return None
        data = response.json()["data"]
        created = (
            datetime.fromtimestamp(data["created_utc"], UTC).isoformat() if data.get("created_utc") else None
        )
        profile = self.profile(
            data["name"],
            self.resolve_profile_url(data["name"]),
            {
                "display_name": data.get("subreddit", {}).get("title"),
                "bio": data.get("subreddit", {}).get("public_description"),
                "avatar": data.get("icon_img"),
                "karma": data.get("total_karma"),
                "created_at": created,
                "public_id": data.get("id"),
            },
            response.url,
            account_id=data.get("id"),
        )
        profile.links = public_links(data.get("subreddit", {}).get("public_description", ""), profile.url)
        return profile

    async def get_public_posts(self, profile, ctx):
        response = await ctx.network.get(
            f"https://oauth.reddit.com/user/{quote(profile.username, safe='')}/submitted",
            ctx.budget,
            hosts={"oauth.reddit.com"},
            headers=self.headers(ctx),
            params={"limit": ctx.request.limits.max_posts, "sort": "new", "raw_json": 1},
        )
        posts = []
        for item in response.json().get("data", {}).get("children", [])[: ctx.request.limits.max_posts]:
            post = item.get("data", {})
            if (
                post.get("subreddit_type") != "public"
                or post.get("author", "").lower() != profile.username.lower()
            ):
                continue
            if post.get("removed_by_category") or post.get("selftext") in ("[removed]", "[deleted]"):
                continue
            url = "https://www.reddit.com" + post["permalink"]
            text = f"{post.get('title', '')}\n{post.get('selftext', '')}"[:10000]
            posts.append(
                Post(
                    id=post["id"],
                    url=url,
                    published_at=datetime.fromtimestamp(post["created_utc"], UTC).isoformat(),
                    text=text,
                    statistics={"score": post.get("score", 0)},
                    links=[link.destination for link in public_links(text, url)],
                )
            )
        return posts
