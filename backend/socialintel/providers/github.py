from urllib.parse import quote

from ..models import Manifest, Post, Status
from ..security import RetrievalError
from .base import PlatformAdapter, public_links


class GitHub(PlatformAdapter):
    manifest = Manifest(
        name="GitHub",
        platform="github",
        domains=["github.com"],
        status="EXPERIMENTAL",
        capabilities=["profile", "links", "statistics", "posts", "timeline"],
        methods=["OFFICIAL API"],
        limitations="Unauthenticated public profiles and public repositories only. Repository updates are not social posts. No private data or numeric-ID resolution.",
        documentation_url="https://docs.github.com/en/rest/users/users",
    )

    def resolve_profile_url(self, username):
        return f"https://github.com/{quote(username, safe='')}"

    async def get_public_profile(self, target, ctx):
        username = self.check_username(
            self.validate_target(target, ctx), r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
        )
        if target.kind == "id":
            raise RetrievalError(Status.UNSUPPORTED, "Use a GitHub username or profile URL.")
        response = await ctx.network.get(
            f"https://api.github.com/users/{username}",
            ctx.budget,
            hosts={"api.github.com"},
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"},
        )
        if response.status == 404:
            return None
        data = response.json()
        if not data.get("login") or data.get("id") is None or data["login"].lower() != username.lower():
            raise RetrievalError(Status.LIMITED, "Source did not return the requested public profile.")
        profile = self.profile(
            data["login"],
            self.resolve_profile_url(data["login"]),
            {
                "display_name": data.get("name"),
                "bio": data.get("bio"),
                "avatar": data.get("avatar_url"),
                "account_type": data.get("type"),
                "organization": data.get("company"),
                "location": data.get("location"),
                "website": data.get("blog"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "public_repos": data.get("public_repos"),
                "created_at": data.get("created_at"),
                "public_id": str(data["id"]),
                "declared_twitter_username": data.get("twitter_username"),
            },
            response.url,
            account_id=data["id"],
        )
        profile.links = public_links(f"{data.get('bio') or ''} {data.get('blog') or ''}", profile.url)
        if data.get("twitter_username"):
            profile.links += public_links(
                f"https://x.com/{quote(data['twitter_username'], safe='')}", profile.url
            )
        return profile

    async def get_public_posts(self, profile, ctx):
        response = await ctx.network.get(
            f"https://api.github.com/users/{quote(profile.username, safe='')}/repos",
            ctx.budget,
            hosts={"api.github.com"},
            params={"sort": "updated", "per_page": ctx.request.limits.max_posts},
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"},
        )
        return [
            Post(
                id=str(repo["id"]),
                url=repo["html_url"],
                published_at=repo.get("updated_at"),
                text=f"{repo['name']}: {repo.get('description') or ''}",
                kind="PUBLIC REPOSITORY UPDATE",
                statistics={"stars": repo.get("stargazers_count", 0)},
            )
            for repo in response.json()[: ctx.request.limits.max_posts]
            if repo.get("private") is False
        ]
