import pytest
from socialintel.discovery import classify_url, entities, normalize, variants
from socialintel.models import CaseUpdate, ImportRequest, InvestigationRequest, Limits


@pytest.mark.parametrize(
    "raw,kind,value",
    [
        (" @Example ", "username", "Example"),
        ("Jane Example", "display_name", "Jane Example"),
        ("123456", "username", "123456"),
        ("did:plc:example", "id", "did:plc:example"),
        ("https://github.com/example", "url", "https://github.com/example"),
        ("Ｅｘａｍｐｌｅ", "username", "Example"),
    ],
)
def test_normalization(raw, kind, value):
    target = normalize(raw)
    assert (target.kind, target.value) == (kind, value)


@pytest.mark.parametrize(
    "url,platform,category,username",
    [
        ("https://github.com/example", "github", "DEVELOPER PROFILE", "example"),
        ("https://github.com/example/repo", "github", "PUBLIC MENTION", None),
        ("https://www.reddit.com/user/example/", "reddit", "FORUM ACCOUNT", "example"),
        ("https://bsky.app/profile/example.bsky.social", "bluesky", "SOCIAL PROFILE", "example.bsky.social"),
        ("https://youtube.com/@example", "youtube", "VIDEO CHANNEL", "example"),
        ("https://onlyfans.com/example", "onlyfans", "CREATOR PROFILE", "example"),
        ("https://x.com/example/status/123", "twitter", "SOCIAL POST", None),
        ("https://example.org/blog/story", None, "BLOG", None),
    ],
)
def test_classification(url, platform, category, username):
    result = classify_url(url)
    assert (result["platform"], result["classification"], result["username"]) == (
        platform,
        category,
        username,
    )


def test_conservative_variants():
    assert variants("example123") == ["example_123", "example.123", "example-123"]
    assert variants("example") == []
    assert variants("example123", 99) == variants("example123")


def test_contacts_are_opt_in_and_explicit():
    text = "Contact public@example.org #research @example https://example.org/"
    assert not any(item["type"] == "PUBLIC EMAIL" for item in entities(text, "https://example.org/"))
    assert any(item["value"] == "public@example.org" for item in entities(text, "https://example.org/", True))
    assert not any(
        item["type"] in ("PERSON", "LOCATION") for item in entities(text, "https://example.org/", True)
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Limits(max_requests=101),
        lambda: InvestigationRequest(target="\n"),
        lambda: CaseUpdate(tags=["x" * 41]),
        lambda: ImportRequest(source_url="https://example.org", fields={"v": float("nan")}),
        lambda: ImportRequest(source_url="https://example.org", fields={"v": "x" * 10001}),
        lambda: normalize("../secret"),
    ],
)
def test_invalid_and_unbounded_inputs(factory):
    with pytest.raises(ValueError):
        factory()
