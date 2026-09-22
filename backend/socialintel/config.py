import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("SOCIALINTEL_DATA_DIR") or Path.home() / ".local" / "share" / "socialintel"
        )
    )
    token: str = field(default_factory=lambda: os.getenv("SOCIALINTEL_API_TOKEN", ""))
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip()
            for item in os.getenv("SOCIALINTEL_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
            if item.strip()
        )
    )
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip().rstrip("/")
            for item in os.getenv("SOCIALINTEL_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        )
    )
    mastodon_instance: str = field(
        default_factory=lambda: os.getenv("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    )
    plugins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip() for item in os.getenv("SOCIALINTEL_PLUGINS", "").split(",") if item.strip()
        )
    )

    def secret(self, name: str) -> str:
        return os.getenv(name, "").strip()

    def public(self) -> dict:
        names = [
            "MASTODON_ACCESS_TOKEN",
            "REDDIT_ACCESS_TOKEN",
            "YOUTUBE_API_KEY",
            "TWITCH_CLIENT_ID",
            "TWITCH_ACCESS_TOKEN",
            "BRAVE_SEARCH_API_KEY",
            "GOOGLE_SEARCH_API_KEY",
            "GOOGLE_SEARCH_ENGINE_ID",
            "CUSTOM_SEARCH_URL",
            "CUSTOM_SEARCH_API_KEY",
        ]
        return {
            "credentials": {name: bool(self.secret(name)) for name in names},
            "mastodon_instance": self.mastodon_instance,
            "storage": "Local SQLite; not encrypted by the application",
            "single_user": True,
            "version": "0.1.0",
        }
