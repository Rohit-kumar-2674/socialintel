"""Package the existing Vite build; does not install dependencies or execute npm."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "frontend" / "dist"
destination = root / "backend" / "socialintel" / "web"
if not (source / "index.html").is_file():
    raise SystemExit("Build the frontend first: cd frontend && npm ci && npm run build")
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
print("Bundled dashboard into the Python package.")
