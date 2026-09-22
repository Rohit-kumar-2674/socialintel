# Testing

## Backend and SDK

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m ruff check backend tests scripts plugins
python -m pytest -q
```

The suite uses synthetic HTTP responses. It covers normalization, provider visibility filters, fallback behavior, time/request limits, cancellation/restart recovery, persistent cooldowns, private-address/DNS defenses, API authentication/origins/body limits, exports and integrity, and plugin declarations/provenance. No provider credentials or real accounts are needed.

For the independently installable example:

```sh
python -m pip install --no-deps plugins/example_provider
SOCIALINTEL_PLUGINS=socialintel_example:create_provider socialintel platforms --json
```

## Dashboard

Build the exact frontend and bundle it into the Python package:

```sh
npm ci --prefix frontend
npm run build --prefix frontend
python scripts/build_frontend.py
cd frontend
npx playwright install chromium
cd ..
```

Use two terminals with the same disposable test token. This server returns **synthetic fixtures only** and binds loopback. Never deploy `tests/serve_dashboard.py` as the application.

Terminal 1:

```sh
SOCIALINTEL_TEST_TOKEN=synthetic-local-token-not-a-real-credential-00000 python tests/serve_dashboard.py
```

Terminal 2:

```sh
SOCIALINTEL_TEST_TOKEN=synthetic-local-token-not-a-real-credential-00000 node scripts/dashboard_smoke.mjs
```

PowerShell users set `$env:SOCIALINTEL_TEST_TOKEN` before each command. Linux systems missing browser libraries may use Playwright's documented `install --with-deps chromium` command where package installation is available.

The checks exercise unlock errors/success, case creation and notes, unverified imports and escaping, unsupported-provider fallback, profiles/evidence/timeline/graph, all report downloads, provider readiness/health separation, mobile navigation/overflow, and locking. Results and screenshots are saved under ignored `.qa/dashboard/`. No browser requests to external hosts are expected. These checks do not validate live upstream availability.

`SOCIALINTEL_BROWSER_EXECUTABLE` optionally selects an existing test Chromium executable when standard Playwright installation is unavailable. Record the browser version when using it.

## Distribution and containers

```sh
python -m build
python scripts/configure_docker.py
docker compose config --quiet
docker compose up --build --wait --wait-timeout 180 -d
docker compose exec -T socialintel python /app/healthcheck.py
```

Validate installed wheels in a separate virtual environment and outside the source tree. Ensure the dashboard assets and SDK are included. Do not claim a Docker run was verified if only configuration parsing or Python tests ran. The CI workflow includes a real Docker build/start/authentication check where a daemon is available.
