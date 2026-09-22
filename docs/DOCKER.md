# Docker operation

Install Docker Engine with Compose v2, or Docker Desktop, on a supported host.

```sh
python3 scripts/configure_docker.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The setup script refuses to overwrite an existing `.env`, generates a random token, and requests owner-only permissions on POSIX systems. Review file permissions on Windows. Read the token locally when unlocking the dashboard; do not share it. `docker compose config` without `--quiet` can print environment secrets.

Open `http://127.0.0.1:8000/`. The default host binding is loopback only. This is a local research application, not a ready-made public multi-user service. A remote deployment needs an authenticated TLS reverse proxy, a deliberate host/origin configuration, and one backend worker.

## Image and storage

The multi-stage image builds the locked frontend, creates a Python wheel with the dashboard, and installs pinned runtime packages. It runs under UID/GID 10001. Compose drops capabilities, enables `no-new-privileges`, makes the root filesystem read-only, and supplies a temporary `/tmp` plus a writable `socialintel-data` volume. Base image tags receive upstream updates; a rebuild is not a bit-for-bit reproducibility guarantee.

The health check calls authenticated `/api/settings` without printing its response or token. Health does not probe external providers. Persistent API tokens are not printed by the application. Do not publish container inspection output containing environment variables.

`docker compose down` stops the stack and keeps the named data volume. **Adding `-v` deletes the volume and its cases.** Back up first.

## Backup and restore

Stop the service before copying SQLite files:

```sh
docker compose stop
mkdir -p backups
docker compose cp socialintel:/data/. ./backups/
docker compose start
```

Store backups outside the repository with restrictive permissions. Keep `.env` separately. To restore, stop the service and copy the backed-up files into `/data`, preserving write access for UID 10001, then restart. Test a restore on a disposable deployment before relying on it. Logical case deletion does not erase old backups.

## Updating

Back up data, pull the desired source revision, rebuild, and restart with `docker compose up --build -d`. Review the changelog before changing dependency locks or schemas. This initial release uses a single SQLite schema; it does not include a general database migration framework.

## Plugins in Docker

The base image contains only built-in providers. Build a derived image for reviewed plugins; never mount arbitrary untrusted code into the app.

```dockerfile
FROM socialintel:local
USER root
COPY plugins/example_provider /opt/example_provider
RUN python -m pip install --no-cache-dir --no-deps /opt/example_provider
USER 10001:10001
ENV SOCIALINTEL_PLUGINS=socialintel_example:create_provider
```

The example is limited to example.org public pages. See the SDK guide before adding real providers. Plugins are trusted executable code; container hardening is not a per-plugin sandbox.

## Validation

CI builds this image, checks Compose configuration, starts it, requires an authenticated health check to succeed, and verifies that an unauthenticated API call returns 401. See `VALIDATION.md` for actual execution results and any environment limits.
