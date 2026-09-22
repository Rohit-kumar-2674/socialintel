"""An installable example, deliberately limited to example.org public pages."""

from socialintel.providers.website import Website
from socialintel.sdk import Manifest, RetrievalError, Status, safe_url


class ExampleProvider(Website):
    manifest = Manifest(
        name="Example.org public page (SDK example)",
        platform="example-page",
        version="0.1.0",
        domains=["example.org"],
        status="EXPERIMENTAL",
        capabilities=["profile", "links", "metadata"],
        methods=["PUBLIC WEBPAGE"],
        limitations="SDK example for explicit example.org HTTPS pages only. No username search, social accounts, posts, or identity claims. Honors robots.txt and collection limits.",
        documentation_url="https://www.iana.org/help/example-domains",
    )

    async def get_public_profile(self, target, ctx):
        if target.kind != "url":
            raise RetrievalError(Status.UNSUPPORTED, "This example requires an explicit example.org HTTPS URL.")
        safe_url(target.value, set(self.manifest.domains))
        return await super().get_public_profile(target, ctx)


def create_provider(settings):
    return ExampleProvider()
