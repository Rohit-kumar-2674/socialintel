# Installation and troubleshooting

## Native application

Python 3.11+ runs the backend; Node.js 22.18+ builds the frontend. Follow the platform-specific commands in the root README. The CLI works without Node or a dashboard build:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
socialintel platforms
```

For a built wheel, install it into a fresh virtual environment with the runtime lock. The wheel must contain `socialintel/web/index.html` and its assets; run `python scripts/build_frontend.py` before building a distributable. Unbuilt source installations show build instructions at `/`.

## Android / Termux with Debian

Use the existing Debian proot environment and install the CLI there with Python 3.11+. Keep the repository under the Debian home directory rather than Android shared storage, which may not support executable files and symlinks correctly. Open a native server at `http://127.0.0.1:8000/` from the phone browser.

For the dashboard build use a supported Node version and `npm ci --prefix frontend`. If native build tools terminate with an illegal instruction on the device, build the wheel on a supported desktop/CI machine and install the completed wheel on Debian; Node is not needed to serve its bundled dashboard. Do not remove Vite dependencies or externalize React to make a broken build appear successful. Docker requires a Docker-capable host and is not supported inside ordinary Android proot.

Android, Windows, and macOS have not been exhaustively tested in this release. The runtime lock records the tested Linux package versions; wheel availability may depend on architecture.

## Configuration

`SOCIALINTEL_DATA_DIR` selects a local directory; the default is `~/.local/share/socialintel`. It contains `socialintel.sqlite3` and possible SQLite sidecar files. It is not application-encrypted. Use OS access controls and disk encryption where appropriate.

For native runs, set environment variables in the shell that launches SocialIntel. Do not paste credentials into issues or terminal transcripts. Docker Compose reads `.env`. Optional provider credentials are checked for presence, not automatically refreshed. API tokens must contain at least 32 characters. `SOCIALINTEL_ALLOWED_HOSTS` defaults to `127.0.0.1,localhost`. `SOCIALINTEL_ALLOWED_ORIGINS` is empty by default; the bundled dashboard uses the same origin.

The token printed for an unconfigured local session changes on restart. A configured token remains stable and is never printed by `socialintel serve`. Locking the dashboard removes this tab's stored token; it does not revoke the server token or tokens in other tabs. Restart with a new configured token to revoke prior access.

## Common problems

| Symptom | Check |
| --- | --- |
| `socialintel` not found | Activate the correct virtual environment, or use `python -m socialintel`. |
| Dashboard shows build instructions | Build `frontend`, then run `python scripts/build_frontend.py` from the repository root and restart. |
| 401 / unlock fails | Use the current server's token; do not put it in a URL query string. |
| Invalid host (400) | Prefer localhost. For intentional deployments configure the allowed host explicitly; avoid `*`. |
| Origin not allowed (403) | Use the bundled same-origin dashboard or Vite's `/api` proxy. Cross-site browser calls are rejected. |
| Provider says API REQUIRED | Configure the documented credentials in the server environment and restart. |
| RATE LIMITED | Wait until the recorded cooldown expires. Refresh and restarts do not bypass persisted cooldowns. |
| LIMITED / redirect / robots rejection | The source is outside this collector's supported access path. Do not bypass it. |
| An expected field is absent | The adapter did not observe it. Absence is not a fabricated zero or a private-data finding. |
| Plugin will not load | Check the local package, `module:factory`, manifest, unique platform ID, and SDK version. Errors are intentionally sanitized. |
| Duplicate worker activity | Run exactly one worker; the queue is process-local. |
| Docker cannot write `/data` | Use the named volume; bind mounts must be writable by UID/GID 10001. |

Stop the application before moving or restoring its data directory. Back up case data and secrets separately. Never commit either to the repository.
