"""Search indexes supply discovery hints. Their snippets are never verified facts."""

from datetime import UTC, datetime
from urllib.parse import urlsplit

from ..discovery import classify_url
from ..models import Status, Verification
from ..security import RetrievalError, display_url, safe_url


class SearchProvider:
    name = "base"
    requirements: tuple[str, ...] = ()

    def configured(self, settings):
        return all(settings.secret(key) for key in self.requirements)

    async def search(self, query, ctx):
        raise RetrievalError(Status.UNSUPPORTED, "Search provider is not implemented.")

    def results(self, items, source, ctx):
        values = []
        for item in items[: ctx.request.limits.max_candidates]:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            info = classify_url(item["url"], urlsplit(ctx.settings.mastodon_instance).hostname)
            if not info["safe"]:
                continue
            values.append(
                {
                    **info,
                    "url": display_url(info["url"]),
                    "title": str(item.get("title", ""))[:400],
                    "snippet": str(item.get("description", ""))[:1200],
                    "provider": self.name,
                    "source_url": display_url(source),
                    "verification": Verification.INDEX.value,
                }
            )
        return values


class Brave(SearchProvider):
    name = "brave"
    requirements = ("BRAVE_SEARCH_API_KEY",)

    async def search(self, query, ctx):
        response = await ctx.network.get(
            "https://api.search.brave.com/res/v1/web/search",
            ctx.budget,
            hosts={"api.search.brave.com"},
            params={"q": query, "count": 10},
            headers={"X-Subscription-Token": ctx.settings.secret("BRAVE_SEARCH_API_KEY")},
        )
        return self.results(response.json().get("web", {}).get("results", []), response.url, ctx)


class Google(SearchProvider):
    name = "google"
    requirements = ("GOOGLE_SEARCH_API_KEY", "GOOGLE_SEARCH_ENGINE_ID")

    def configured(self, settings):
        return datetime.now(UTC).date().isoformat() < "2027-01-01" and super().configured(settings)

    async def search(self, query, ctx):
        if datetime.now(UTC).date().isoformat() >= "2027-01-01":
            raise RetrievalError(
                Status.UNAVAILABLE, "Google Custom Search JSON API's documented service end has passed."
            )
        response = await ctx.network.get(
            "https://www.googleapis.com/customsearch/v1",
            ctx.budget,
            hosts={"www.googleapis.com"},
            params={
                "q": query,
                "num": 10,
                "key": ctx.settings.secret("GOOGLE_SEARCH_API_KEY"),
                "cx": ctx.settings.secret("GOOGLE_SEARCH_ENGINE_ID"),
            },
        )
        return self.results(
            [
                {"url": item.get("link"), "title": item.get("title"), "description": item.get("snippet")}
                for item in response.json().get("items", [])
            ],
            response.url,
            ctx,
        )


class Custom(SearchProvider):
    name = "custom"
    requirements = ("CUSTOM_SEARCH_URL",)

    async def search(self, query, ctx):
        url = safe_url(ctx.settings.secret("CUSTOM_SEARCH_URL"))
        headers = {}
        if ctx.settings.secret("CUSTOM_SEARCH_API_KEY"):
            headers["Authorization"] = f"Bearer {ctx.settings.secret('CUSTOM_SEARCH_API_KEY')}"
        response = await ctx.network.get(
            url, ctx.budget, hosts={urlsplit(url).hostname}, params={"q": query, "count": 10}, headers=headers
        )
        return self.results(response.json().get("results", []), response.url, ctx)


SEARCH = {provider.name: provider for provider in (Brave(), Google(), Custom())}


def search_catalog(settings):
    return [
        {
            "name": key,
            "configured": provider.configured(settings),
            "requirements": provider.requirements,
            "limitation": "Existing customers only; scheduled end 2027-01-01."
            if key == "google"
            else "Discovery hints only; credentials and provider terms apply.",
        }
        for key, provider in SEARCH.items()
    ] + [
        {
            "name": "bing",
            "configured": False,
            "requirements": [],
            "limitation": "UNAVAILABLE: standalone Bing Search APIs retired on 2025-08-11.",
        }
    ]
