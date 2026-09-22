"""Shared, bounded contracts for providers, evidence, API, and exports."""

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> str:
    return datetime.now(UTC).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Status(StrEnum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT FOUND"
    POSSIBLE = "POSSIBLE"
    RATE_LIMITED = "RATE LIMITED"
    API_REQUIRED = "API REQUIRED"
    AUTH_REQUIRED = "AUTH REQUIRED"
    UNSUPPORTED = "UNSUPPORTED BY THIS PROVIDER"
    UNAVAILABLE = "UNAVAILABLE"
    LIMITED = "LIMITED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class Verification(StrEnum):
    VERIFIED = "VERIFIED PUBLIC SOURCE"
    INDEX = "SEARCH INDEX REFERENCE — NOT INDEPENDENTLY VERIFIED"
    INFERENCE = "ANALYTICAL INFERENCE"
    IMPORT = "USER-PROVIDED — NOT INDEPENDENTLY VERIFIED"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceField(Model):
    value: Any
    source_url: str
    collected_at: str = Field(default_factory=now)
    method: str
    verification: Verification = Verification.VERIFIED
    provider: str


class Link(Model):
    source_url: str
    destination: str
    kind: str = "UNKNOWN"
    method: str = "PUBLIC BIO LINK"
    collected_at: str = Field(default_factory=now)


class Post(Model):
    id: str
    url: str
    published_at: str | None = None
    text: str = ""
    kind: str = "PUBLIC POST"
    statistics: dict[str, int] = Field(default_factory=dict)
    media: list[dict[str, Any]] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class Profile(Model):
    id: str
    platform: str
    username: str
    url: str
    fields: dict[str, SourceField] = Field(default_factory=dict)
    links: list[Link] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    collected_at: str = Field(default_factory=now)
    verification: Verification = Verification.VERIFIED
    method: str = "OFFICIAL API"
    provider: str


class ProviderResult(Model):
    platform: str
    target: str
    status: Status
    reason: str = ""
    profile: Profile | None = None
    checked_at: str = Field(default_factory=now)
    duration_ms: int = 0
    cached: bool = False
    variant: bool = False
    source_url: str | None = None
    retry_at: str | None = None


class Manifest(Model):
    sdk_version: Literal["1"] = "1"
    public_only: Literal[True] = True
    name: str
    platform: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,39}$")
    version: str = "0.1.0"
    author: str = "SocialIntel contributors"
    domains: list[str]
    status: str
    capabilities: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    limitations: str
    documentation_url: str
    rate_interval: float = Field(default=1.0, ge=0.2)
    plugin: bool = False


class Target(Model):
    raw: str
    value: str
    kind: Literal["username", "url", "id", "display_name"]
    platform: str | None = None


class Limits(Model):
    max_requests: int = Field(default=40, ge=1, le=100)
    max_candidates: int = Field(default=20, ge=1, le=50)
    max_platforms: int = Field(default=8, ge=1, le=12)
    max_pages: int = Field(default=5, ge=0, le=10)
    max_depth: int = Field(default=1, ge=0, le=2)
    max_seconds: int = Field(default=90, ge=5, le=180)
    max_posts: int = Field(default=10, ge=0, le=20)


class InvestigationRequest(Model):
    target: str = Field(min_length=1, max_length=500)
    platform: str = "github"
    mode: Literal["selected", "fallback", "discovery"] = "fallback"
    target_type: Literal["auto", "username", "url", "id", "display_name"] = "auto"
    case_id: str | None = None
    search_engine: Literal["none", "brave", "google", "custom", "bing"] = "none"
    variants: bool = False
    follow_links: bool = False
    collect_posts: bool = False
    collect_contacts: bool = False
    refresh: bool = False
    limits: Limits = Field(default_factory=Limits)

    @field_validator("target")
    @classmethod
    def valid_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Provide a non-empty identifier without control characters.")
        return value


class CaseCreate(Model):
    name: str = Field(min_length=1, max_length=140)
    purpose: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A case name is required.")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def bounded_tags(cls, value: list[str]) -> list[str]:
        if any(len(tag) > 40 for tag in value):
            raise ValueError("Tags may contain at most 40 characters.")
        return list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))


class CaseUpdate(Model):
    notes: str | None = Field(default=None, max_length=20000)
    status: Literal["active", "archived"] | None = None
    tags: list[str] | None = Field(default=None, max_length=12)

    @field_validator("tags")
    @classmethod
    def bounded_tags(cls, value):
        return CaseCreate.bounded_tags(value) if value is not None else None


class ImportRequest(Model):
    source_url: str = Field(max_length=2000)
    platform: str = Field(default="user-export", max_length=50)
    fields: dict[str, str | int | float | bool | None] = Field(min_length=1, max_length=30)
    notes: str = Field(default="", max_length=2000)

    @field_validator("fields")
    @classmethod
    def bounded_fields(cls, fields: dict) -> dict:
        if any(isinstance(value, float) and not math.isfinite(value) for value in fields.values()):
            raise ValueError("Imported numbers must be finite.")
        if any(len(key) > 80 or len(str(value)) > 10000 for key, value in fields.items()):
            raise ValueError("An imported field is too large.")
        return fields


class AttachmentRequest(Model):
    filename: str = Field(min_length=1, max_length=200)
    data_base64: str = Field(max_length=7_000_000)
    source_url: str = Field(default="", max_length=2000)
