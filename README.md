<div align="center">

# SocialIntel

### Public sources. Traceable evidence. Explicit uncertainty.

A local workspace for public-profile research, with a shared Python engine behind a CLI, authenticated API, and React dashboard.

**Research release · v0.1.0 · MIT · Public data only**

[Get started](#get-started) · [Provider coverage](docs/PROVIDERS.md) · [Docker](docs/DOCKER.md) · [Plugin SDK](docs/PROVIDER_SDK.md) · [Security](SECURITY.md)

</div>

## What it does

Start with a platform and a public username or profile URL. SocialIntel records what each source actually returned, preserves the source and collection time, and keeps uncertainty visible throughout the investigation.

- **Three collection modes:** selected platform, automatic fallback when the primary cannot provide a public profile, or full discovery across configured adapters.
- **Evidence workspace:** cases, notes, tags, source fields, public links, optional public posts, immutable observation records, and SHA-256 integrity checks.
- **Review tools:** profile comparison, source-linked relationship graphs, publication timelines, and manual snapshot comparisons.
- **Reports:** HTML, Markdown, JSON, and spreadsheet-safe CSV. HTML reports can be printed to PDF.
- **Operator controls:** request, time, page, candidate, and traversal limits; cancellation; cache clearing; archived-case retention previews.
- **Extension SDK:** explicit local plugin loading, manifest validation, a public-source output contract, and an installable example.

**A verified public source is not a verified identity.** Matching usernames, biographies, or links are research signals, not proof that two accounts belong to one person.

## Provider coverage

| Provider | Implemented collection | Access requirement |
| --- | --- | --- |
| GitHub | Public profile, public repository updates, links, counts | Public unauthenticated API |
| Bluesky | Public AppView profile, authored posts, links, counts | Public API |
| Mastodon | Unlocked account profile and explicitly public authored statuses | Configured instance and authorized API token |
| Reddit | Public profile and posts explicitly associated with public communities | Approved API access, OAuth token, user agent |
| YouTube | Public channel metadata and visible statistics | Data API key |
| Twitch | Public Helix profile fields | Client ID and app access token |
| Public website | Bounded HTML metadata and links | HTTPS URL; robots.txt and access checks |

These adapters are **experimental or credential-dependent**, not a promise of live availability. Instagram, Facebook, X, Threads, TikTok, Snapchat, LinkedIn, OnlyFans, Fansly, and the other catalog-only platforms are explicitly **NOT IMPLEMENTED / UNSUPPORTED BY THIS PROVIDER**. Search results for those platforms remain unverified references. See the [complete matrix](docs/PROVIDERS.md).

## Get started

Requires Python 3.11+ and Node.js 22.18+ for building the dashboard. Keep the project in a private local directory; cases and tokens do not belong in Git.

### Linux, macOS, Ubuntu / WSL

```sh
git clone https://github.com/Rohit-kumar-2674/socialintel.git
cd socialintel
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
npm ci --prefix frontend
npm run build --prefix frontend
python scripts/build_frontend.py
socialintel serve
```

Open the private session link printed by the command. The dashboard removes the token from the address bar and keeps it only in tab session storage or memory. When a token is configured through the environment, it is not printed; enter it on the unlock screen.

### Windows PowerShell

```powershell
git clone https://github.com/Rohit-kumar-2674/socialintel.git
cd socialintel
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
npm ci --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe scripts/build_frontend.py
.\.venv\Scripts\socialintel.exe serve
```

These commands do not require changing PowerShell execution policy. See [installation and Android notes](docs/INSTALLATION.md) for the CLI-only path and troubleshooting. Cross-platform support is a target; see [the validation record](docs/VALIDATION.md) for what was actually tested.

### Docker Compose

```sh
python3 scripts/configure_docker.py
docker compose up --build -d
```

Open `http://127.0.0.1:8000/` and use `SOCIALINTEL_API_TOKEN` from your private `.env`. The container runs as a non-root user, binds to host loopback, and stores case data in a named volume. [Docker operation, backup, and limitations →](docs/DOCKER.md)

## CLI examples

```sh
socialintel platforms
socialintel investigate github YOUR_PUBLIC_USERNAME --no-fallback
socialintel investigate instagram YOUR_PUBLIC_USERNAME
socialintel investigate --all YOUR_PUBLIC_USERNAME
socialintel discover YOUR_PUBLIC_USERNAME --search-engine brave
socialintel case create --name "Public-source review"
socialintel case list
socialintel report CASE_ID --format html --output report.html
socialintel verify EVIDENCE_ID
socialintel retention --days 90
```

Replace uppercase placeholders. Provider API keys are optional environment variables, described in `.env.example`. The native CLI does **not** automatically load `.env`; Docker Compose does. The application never acquires login cookies, subscriber sessions, or credentials for you.

## Privacy boundary

Only collect information from publicly accessible sources or explicitly authorized public-data APIs. Private messages, private/locked profiles, subscriber-only or paid material, deleted-content recovery, authentication/CAPTCHA bypass, rate-limit evasion, and identity claims are excluded. Imports must follow the same public-only scope and stay labeled **USER-PROVIDED — NOT INDEPENDENTLY VERIFIED**.

No face recognition, biometric matching, password discovery, background account surveillance, or hidden-contact enrichment is implemented. Unknown fields are omitted or displayed as **NOT PUBLICLY AVAILABLE**, never invented. Public material can still contain personal information: minimize collection and sharing.

## Development

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m ruff check backend tests scripts plugins
python -m pytest -q
npm run build --prefix frontend
python scripts/build_frontend.py
```

Tests use explicit synthetic HTTP fixtures, not live accounts. The [testing guide](docs/TESTING.md) explains local browser checks and container smoke tests. GitHub Actions runs backend tests, dashboard/SDK/package checks, and a Docker build with an authenticated readiness check.

## Project map

| Path | Purpose |
| --- | --- |
| `backend/socialintel/` | Engine, API, CLI, evidence storage, exports, retrieval guardrails |
| `backend/socialintel/providers/` | Public adapters and honest unsupported-provider catalog |
| `backend/socialintel/sdk.py` | Versioned provider contract and provenance validation |
| `frontend/` | React / TypeScript dashboard |
| `plugins/example_provider/` | Installable, explicitly scoped example.org adapter |
| `tests/` | Offline unit, integration, privacy, and regression checks |
| `scripts/` | Frontend packaging, Docker configuration, health and browser checks |
| `docs/` | Architecture, API, installation, SDK, provider matrix, and validation |

## Scope and limitations

This release is a **single-operator, single-process SQLite application**. PostgreSQL, multi-user roles, distributed workers, scheduled monitoring, remote plugin installation, and direct PDF generation are not implemented. Use one API worker. Provider health is the last observed result, not a continuous availability test. Upstream APIs, terms, quotas, and schemas can change.

Read [ARCHITECTURE](docs/ARCHITECTURE.md), [SECURITY](SECURITY.md), [CONTRIBUTING](CONTRIBUTING.md), and [CHANGELOG](CHANGELOG.md) before extending it. Licensed under [MIT](LICENSE).
