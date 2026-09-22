# Example provider

This is a working SDK example for public HTML metadata on `https://example.org/`.
It is not a social-media adapter and does not return fabricated account data.
The normal website collector supplies robots.txt handling, response limits, and
public HTML metadata extraction. All other domains and username searches are rejected.

From the SocialIntel repository, in the same Python environment:

```sh
python -m pip install --no-deps -e plugins/example_provider
export SOCIALINTEL_PLUGINS=socialintel_example:create_provider
socialintel platforms
socialintel investigate example-page https://example.org/ --no-fallback
```

In PowerShell use `$env:SOCIALINTEL_PLUGINS='socialintel_example:create_provider'`.
Do not deploy this example as a promised social provider. Copy the structure,
choose your own platform ID, implement an allowed public source, and add fixtures
before adding any capability. See [the SDK guide](../../docs/PROVIDER_SDK.md).
