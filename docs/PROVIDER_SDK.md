# Provider SDK v1

Plugins are installed, reviewed Python packages loaded only from `SOCIALINTEL_PLUGINS=package.module:factory`. This is a local extension mechanism, not a sandbox or remote marketplace. Importing a Python package executes code with the operator's privileges. Never install an untrusted plugin or put code-upload controls in the dashboard.

## Public contract

Import supported contracts from `socialintel.sdk`: `PlatformAdapter`, `Context`, `Manifest`, `Target`, `Profile`, `SourceField`, `Post`, `Link`, `Status`, `Verification`, `RetrievalError`, `safe_url`, `display_url`, `plain`, and `public_links`.

- `sdk_version` is `"1"`; `public_only` must be `true`.
- `factory(settings)` returns a `PlatformAdapter` instance. Factories must not make network calls.
- `manifest.platform` is a unique lowercase ID. Plugins cannot replace a built-in platform or another plugin.
- `domains` lists literal public profile hosts; no wildcards, paths, local names, or private IPs.
- `status` is readiness: `EXPERIMENTAL` or `API REQUIRED`. It must not claim `ONLINE`. Live observations are recorded separately.
- Declare only implemented capabilities: `profile`, `links`, `statistics`, `posts`, `timeline`, `media`, `metadata`.
- Supported methods are `OFFICIAL API`, `PUBLIC API`, and `PUBLIC WEBPAGE`.
- `requirements` names environment variables, never their values. Put credentials in request headers where supported; never in manifests, reasons, evidence, or logs.
- Include a semantic version, a public documentation URL, and concrete limitations. Increment the provider version when interpretation changes; it participates in cache keys.

[The JSON schema](provider-manifest.schema.json) describes serialized fields. Runtime validation also checks capabilities, methods, domains, implementations, and readiness values; schema validation alone is insufficient.

## Collection method

```python
from socialintel.sdk import PlatformAdapter, RetrievalError, Status

class PublicAdapter(PlatformAdapter):
    # Define a reviewed Manifest for your actual provider here.
    async def get_public_profile(self, target, ctx):
        raise RetrievalError(Status.UNSUPPORTED, "Implement an approved public endpoint first.")
```

The snippet is deliberately not a functioning provider. The [installable example](../plugins/example_provider) is complete and restricted to example.org HTML metadata. It uses the same tested robots-aware Website collector as the core; it does not simulate social accounts.

Use `validate_target()` or explicit public URL validation. Reject unsupported target kinds instead of treating IDs or display names as cross-platform identities. All collection must use:

```python
response = await ctx.network.get(
    "https://api.your-public-provider.example/public/profile",
    ctx.budget,
    hosts={"api.your-public-provider.example"},
    params={"username": validated_username},
    interval=max(1.0, self.manifest.rate_interval),
)
```

This illustrative endpoint does not exist. Replace it only with a documented, permitted public-data endpoint. Use an explicit API-host allowlist; `manifest.domains` describes profile URLs, which may use a different host. The SDK cannot force trusted Python code to use this client, so code review and tests are required.

The retrieval client enforces public HTTPS/port 443, connection-time DNS/IP checks, bounded responses, request/time budgets, concurrency, persistent rate-limit cooldowns, and no redirects or proxy inheritance. Never replace it with raw sockets, browser session scraping, or your own client to evade those boundaries.

## Outcomes and evidence

Return `None` only when the supported source explicitly reports no public profile for the requested target. Private/locked, paywalled, forbidden, rate-limited, malformed, and unsupported responses are not NOT FOUND.

Raise `RetrievalError(Status.<value>, "sanitized explanation")` for explicit limitations. Statuses include `UNSUPPORTED`, `API_REQUIRED`, `AUTH_REQUIRED`, `RATE_LIMITED`, `LIMITED`, `TIMEOUT`, `UNAVAILABLE`, and `ERROR`. Unexpected exceptions are isolated; do not put exception bodies or credentials in user-facing reasons.

Build observations with `self.profile(username, profile_url, observed_fields, public_source_url, method=...)`. Omit unavailable fields. Every field has its source, collection time, provider, method, and verification label. Before persistence, the engine validates provider identity, public source URLs, and verification/method contracts. It rejects search-index hints in the source-verified collection path. These structural checks cannot certify that a remote source or plugin is truthful.

Implement `get_public_posts(profile, ctx)` only when declaring `posts`. Return authored, explicitly public, non-deleted content and obey `ctx.request.limits.max_posts`. Respect `collect_posts`; never silently broaden scope. Media metadata is descriptive only; the app does not download media, perform face recognition, or infer identity.

Use `public_links()` for declared public URLs. A public cross-link is an observation, not a confirmed owner match. User imports and search snippets use separate unverified paths and must never be promoted to source-verified observations by a plugin.

## Install and test

```sh
python -m pip install --no-deps -e plugins/example_provider
export SOCIALINTEL_PLUGINS=socialintel_example:create_provider
socialintel platforms --json
socialintel serve
```

PowerShell: `$env:SOCIALINTEL_PLUGINS='socialintel_example:create_provider'`.
Restart the server after changes. Up to ten explicit plugin specifications are loaded; duplicate or malformed declarations are reported as sanitized plugin errors. Configuration errors do not disable other providers.

A provider contribution needs offline fixtures for success, not-found, private/restricted content, malformed data, 401/403/429, unsupported target kinds, source URLs/provenance, and its declared features. Mock `httpx` through the supplied `Network` instead of making live calls in CI. Run `tests/test_sdk.py` and the complete suite. See [CONTRIBUTING](../CONTRIBUTING.md).
