import httpx
import pytest
from conftest import FixtureNetwork
from socialintel.discovery import normalize
from socialintel.models import Status
from socialintel.providers import Registry
from socialintel.providers.bluesky import Bluesky
from socialintel.providers.github import GitHub
from socialintel.providers.mastodon import Mastodon
from socialintel.providers.reddit import Reddit
from socialintel.providers.twitch import Twitch
from socialintel.providers.website import Website
from socialintel.providers.youtube import YouTube
from socialintel.security import RetrievalError


async def test_github_public_projection_and_repositories(context):
    provider = GitHub()
    profile = await provider.get_public_profile(normalize("example"), context)
    assert "email" not in profile.fields and "private_gists" not in profile.fields
    assert all(
        field.source_url.startswith("https://api.github.com/users/") for field in profile.fields.values()
    )
    posts = await provider.get_public_posts(profile, context)
    assert len(posts) == 1 and posts[0].kind == "PUBLIC REPOSITORY UPDATE"
    assert await provider.get_public_profile(normalize("missing"), context) is None
    with pytest.raises(RetrievalError):
        await provider.get_public_profile(normalize("123", "id"), context)


async def test_bluesky_handle_and_author_filter(context):
    provider = Bluesky()
    profile = await provider.get_public_profile(normalize("example"), context)
    assert profile.username == "example.bsky.social"
    posts = await provider.get_public_posts(profile, context)
    assert len(posts) == 1 and "repost" not in posts[0].text


async def test_website_public_html_and_robots(context):
    provider = Website()
    profile = await provider.get_public_profile(normalize("https://example.org/"), context)
    assert profile.fields["display_name"].value == "Synthetic website"
    assert all("secret" not in str(field.value) for field in profile.fields.values())
    assert any(link.destination == "https://github.com/example" for link in profile.links)
    context.network = FixtureNetwork(
        httpx.MockTransport(lambda _: httpx.Response(200, text="User-agent: *\nDisallow: /"))
    )
    with pytest.raises(RetrievalError, match="robots"):
        await provider.get_public_profile(normalize("https://example.org/"), context)
    await context.network.close()


async def test_website_declines_login_challenges(context):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text='<input type="password">', headers={"content-type": "text/html"})

    context.network = FixtureNetwork(httpx.MockTransport(handler))
    with pytest.raises(RetrievalError, match="Login or challenge"):
        await Website().get_public_profile(normalize("https://example.org/"), context)
    await context.network.close()


async def test_youtube_hidden_subscriber_count_and_key_redaction(context, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "fixture-secret")
    context.network = FixtureNetwork(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UCfixture",
                            "snippet": {
                                "title": "Fixture channel",
                                "customUrl": "@example",
                                "description": "Public bio",
                            },
                            "statistics": {
                                "hiddenSubscriberCount": True,
                                "subscriberCount": "1234",
                                "videoCount": "3",
                            },
                        }
                    ]
                },
            )
        )
    )
    profile = await YouTube().get_public_profile(normalize("https://youtube.com/@example"), context)
    assert "subscribers" not in profile.fields
    assert "fixture-secret" not in profile.model_dump_json()
    await context.network.close()


async def test_twitch_never_collects_email_or_deprecated_counts(context):
    context.network = FixtureNetwork(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "1",
                            "login": "example",
                            "display_name": "Fixture",
                            "email": "private@example.org",
                            "view_count": 999,
                            "description": "Public",
                        }
                    ]
                },
            )
        )
    )
    profile = await Twitch().get_public_profile(normalize("example"), context)
    assert "email" not in profile.fields and "view_count" not in profile.fields
    await context.network.close()


async def test_mastodon_locked_accounts_and_nonpublic_statuses(context):
    provider = Mastodon(context.settings)
    context.network = FixtureNetwork(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "1", "locked": True}))
    )
    with pytest.raises(RetrievalError, match="locked"):
        await provider.get_public_profile(normalize("example"), context)
    await context.network.close()

    def handler(request):
        if request.url.path.endswith("lookup"):
            return httpx.Response(
                200,
                json={
                    "id": "1",
                    "acct": "example",
                    "url": "https://mastodon.social/@example",
                    "locked": False,
                    "note": "Public bio",
                },
            )
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(i),
                    "account": {"id": "1"},
                    "visibility": visibility,
                    "url": f"https://mastodon.social/@example/{i}",
                    "content": "Fixture",
                }
                for i, visibility in enumerate(["public", "unlisted", "private", "direct"])
            ],
        )

    context.network = FixtureNetwork(httpx.MockTransport(handler))
    profile = await provider.get_public_profile(normalize("example"), context)
    posts = await provider.get_public_posts(profile, context)
    assert len(posts) == 1
    await context.network.close()


async def test_reddit_posts_require_public_community(context):
    provider = Reddit()

    def handler(request):
        if request.url.path.endswith("about"):
            return httpx.Response(
                200,
                json={"data": {"name": "example", "id": "1", "subreddit": {"public_description": "Fixture"}}},
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": str(index),
                                "author": "example",
                                "subreddit_type": kind,
                                "permalink": f"/r/example/comments/{index}/fixture/",
                                "title": "Fixture",
                                "created_utc": 1700000000,
                                "selftext": "Public",
                            }
                        }
                        for index, kind in enumerate(["public", "private", "restricted", None])
                    ]
                }
            },
        )

    context.network = FixtureNetwork(httpx.MockTransport(handler))
    profile = await provider.get_public_profile(normalize("example"), context)
    posts = await provider.get_public_posts(profile, context)
    assert len(posts) == 1
    await context.network.close()


def test_registry_does_not_claim_unimplemented_platforms_work(settings):
    registry = Registry(settings)
    catalog = registry.catalog(settings)
    assert len(catalog) >= 29
    instagram = registry.get("instagram")
    assert instagram.manifest.capabilities == []
    assert instagram.manifest.status == "NOT IMPLEMENTED"
    assert {provider.manifest.platform for provider in registry.discovery_providers(settings)} == {
        "github",
        "bluesky",
    }


async def test_unsupported_methods_are_explicit(context):
    with pytest.raises(RetrievalError) as result:
        await YouTube().get_public_posts(None, context)
    assert result.value.status == Status.UNSUPPORTED
