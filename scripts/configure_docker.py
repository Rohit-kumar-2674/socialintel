"""Create a private Docker .env without printing secrets or overwriting existing settings."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
value = (root / ".env.example").read_text(encoding="utf-8")
value = value.replace("SOCIALINTEL_API_TOKEN=\n", f"SOCIALINTEL_API_TOKEN={secrets.token_urlsafe(32)}\n")
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; keep it or edit it locally. No settings were overwritten.") from None
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(value)
print("Created .env. Keep its API token private; use it to unlock http://127.0.0.1:8000/.")
print("Start with: docker compose up --build -d")
