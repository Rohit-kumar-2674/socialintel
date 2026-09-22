"""All automated collection uses explicit synthetic HTTP fixtures, never live websites."""

import httpx
import pytest
from socialintel.config import Settings
from socialintel.models import InvestigationRequest, Limits
from socialintel.providers.base import Context
from socialintel.security import Budget, Network
from socialintel.storage import Store


class FixtureNetwork(Network):
    async def get(self, *args, **kwargs):
        kwargs["interval"] = 0
        return await super().get(*args, **kwargs)


def fixture_response(request):
    path, host = request.url.path, request.url.host
    if host == "api.github.com":
        username = path.split("/")[2]
        if username == "missing":
            return httpx.Response(404, json={"message": "Not Found"})
        if path.endswith("/repos"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 123,
                        "name": "public-fixture",
                        "private": False,
                        "html_url": f"https://github.com/{username}/public-fixture",
                        "description": "Synthetic fixture",
                        "updated_at": "2026-09-01T10:00:00Z",
                        "stargazers_count": 3,
                    },
                    {
                        "id": 999,
                        "name": "private-fixture",
                        "private": True,
                        "html_url": "https://github.com/private/secret",
                    },
                ],
            )
        return httpx.Response(
            200,
            json={
                "id": 10,
                "login": username,
                "name": "Synthetic Example",
                "bio": f"Synthetic research fixture. https://bsky.app/profile/{username}.bsky.social #research",
                "blog": "https://example.org/",
                "followers": 5,
                "following": 2,
                "public_repos": 1,
                "type": "User",
                "email": "must-not-collect@example.org",
                "private_gists": 999,
                "created_at": "2020-01-01T00:00:00Z",
            },
        )
    if host == "public.api.bsky.app":
        actor = request.url.params.get("actor", "example.bsky.social")
        if path.endswith("getAuthorFeed"):
            return httpx.Response(
                200,
                json={
                    "feed": [
                        {
                            "post": {
                                "uri": "at://did:plc:fixture/app.bsky.feed.post/1",
                                "author": {"did": "did:plc:fixture"},
                                "record": {
                                    "text": "Synthetic public #research",
                                    "createdAt": "2026-09-02T10:00:00Z",
                                },
                                "likeCount": 2,
                            }
                        },
                        {
                            "post": {
                                "uri": "at://did:plc:another/app.bsky.feed.post/2",
                                "author": {"did": "did:plc:another"},
                                "record": {"text": "Do not attribute this repost"},
                            }
                        },
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "did": "did:plc:fixture",
                "handle": actor if not actor.startswith("did:") else "example.bsky.social",
                "displayName": "Synthetic Example",
                "description": "Synthetic fixture. https://example.org/",
                "followersCount": 8,
                "followsCount": 3,
                "postsCount": 1,
            },
        )
    if host == "api.search.brave.com":
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://github.com/example",
                            "title": "Example profile",
                            "description": "Unverified index description",
                        },
                        {
                            "url": "https://x.com/example",
                            "title": "Index candidate",
                            "description": "Not independently verified",
                        },
                        {"url": "http://127.0.0.1/", "title": "SSRF", "description": "Rejected"},
                    ]
                }
            },
        )
    if host == "example.org":
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200,
            text='<html><head><title>Synthetic website</title><meta name="description" content="Public fixture"></head><body><a href="https://github.com/example">Public profile</a><script>secret@example.org</script></body></html>',
            headers={"content-type": "text/html"},
        )
    return httpx.Response(404, json={"error": "No fixture"})


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "REDDIT_ACCESS_TOKEN",
        "REDDIT_USER_AGENT",
        "MASTODON_ACCESS_TOKEN",
        "YOUTUBE_API_KEY",
        "TWITCH_CLIENT_ID",
        "TWITCH_ACCESS_TOKEN",
        "BRAVE_SEARCH_API_KEY",
        "GOOGLE_SEARCH_API_KEY",
        "GOOGLE_SEARCH_ENGINE_ID",
        "CUSTOM_SEARCH_URL",
        "CUSTOM_SEARCH_API_KEY",
        "SOCIALINTEL_PLUGINS",
        "SOCIALINTEL_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        token="fixture-token-" + "x" * 32,
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )


@pytest.fixture
def store(settings):
    value = Store(settings.data_dir)
    yield value
    value.engine.dispose()


@pytest.fixture
async def network():
    value = FixtureNetwork(httpx.MockTransport(fixture_response))
    yield value
    await value.close()


@pytest.fixture
def context(settings, network):
    request = InvestigationRequest(target="example", collect_posts=True)
    return Context(network, Budget(Limits()), settings, request)
