"""Local SQLite persistence, attributed observations, and tamper-evident digests."""

import base64
import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    delete,
    event,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session

from .models import CaseCreate, CaseUpdate, identifier, now
from .security import display_url, safe_url


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    purpose = Column(Text, default="")
    notes = Column(Text, default="")
    tags = Column(JSON, default=list)
    status = Column(String, default="active")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class Investigation(Base):
    __tablename__ = "investigations"
    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    status = Column(String, nullable=False)
    request = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    started_at = Column(String, nullable=False)
    finished_at = Column(String)


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    investigation_id = Column(
        String, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    body = Column(JSON, nullable=False)
    sha256 = Column(String, nullable=False)


class Cache(Base):
    __tablename__ = "cache"
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    expires_at = Column(String, nullable=False)


class Health(Base):
    __tablename__ = "provider_health"
    platform = Column(String, primary_key=True)
    body = Column(JSON, nullable=False)


class Cooldown(Base):
    __tablename__ = "provider_cooldowns"
    host = Column(String, primary_key=True)
    until = Column(Float, nullable=False)


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    metadata_json = Column(JSON, nullable=False)
    content = Column(LargeBinary, nullable=False)


class Audit(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(String, nullable=False)
    action = Column(String, nullable=False)
    resource_id = Column(String, nullable=False)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def as_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class Store:
    def __init__(self, data_dir):
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = data_dir / "socialintel.sqlite3"
        self.engine = create_engine(
            f"sqlite:///{self.path.as_posix()}", connect_args={"check_same_thread": False, "timeout": 10}
        )

        @event.listens_for(self.engine, "connect")
        def sqlite_options(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA secure_delete=ON")

        Base.metadata.create_all(self.engine)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def session(self):
        with Session(self.engine) as session, session.begin():
            yield session

    def audit(self, action, resource):
        with self.session() as session:
            session.add(Audit(at=now(), action=action, resource_id=resource))

    def recover(self):
        with self.session() as session:
            for row in session.scalars(
                select(Investigation).where(Investigation.status.in_(["queued", "running"]))
            ):
                row.status = "interrupted"
                row.finished_at = now()
                row.result = {
                    **row.result,
                    "limitation": "Process stopped before completion. Manually rerun to resume research.",
                }

    def create_case(self, body: CaseCreate):
        with self.session() as session:
            row = Case(
                id=identifier("case"),
                **body.model_dump(),
                notes="",
                status="active",
                created_at=now(),
                updated_at=now(),
            )
            session.add(row)
            session.flush()
            result = as_dict(row)
        self.audit("case.create", result["id"])
        return result

    def cases(self):
        with self.session() as session:
            return [
                as_dict(row)
                for row in session.scalars(select(Case).order_by(Case.updated_at.desc()).limit(500))
            ]

    def get_case(self, case_id):
        with self.session() as session:
            row = session.get(Case, case_id)
            if row is None:
                raise KeyError("Case not found.")
            result = as_dict(row)
            result["investigations"] = [
                self.investigation_summary(item)
                for item in session.scalars(
                    select(Investigation)
                    .where(Investigation.case_id == case_id)
                    .order_by(Investigation.started_at.desc())
                    .limit(100)
                )
            ]
            result["evidence_count"] = session.scalar(
                select(func.count()).select_from(Evidence).where(Evidence.case_id == case_id)
            )
            result["attachments"] = [
                {"id": item.id, **item.metadata_json}
                for item in session.scalars(select(Attachment).where(Attachment.case_id == case_id))
            ]
            return result

    def update_case(self, case_id, body: CaseUpdate):
        with self.session() as session:
            row = session.get(Case, case_id)
            if row is None:
                raise KeyError("Case not found.")
            for key, value in body.model_dump(exclude_none=True).items():
                setattr(row, key, value)
            row.updated_at = now()
        self.audit("case.update", case_id)
        return self.get_case(case_id)

    def delete_case(self, case_id):
        self.get_case(case_id)
        with self.session() as session:
            active = session.scalar(
                select(func.count())
                .select_from(Investigation)
                .where(Investigation.case_id == case_id, Investigation.status.in_(["queued", "running"]))
            )
            if active:
                raise ValueError("Cancel active investigations before deleting this case.")
            session.execute(delete(Case).where(Case.id == case_id))
            session.execute(delete(Cache))
            session.execute(delete(Audit).where(Audit.resource_id == case_id))
        self.audit("case.delete", case_id)
        # SQLite deletion is logical, not guaranteed forensic erasure of backups or disk snapshots.
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")

    def create_investigation(self, request):
        case_id = (
            request.case_id
            or self.create_case(CaseCreate(name=f"Investigation · {request.target[:100]}"))["id"]
        )
        case = self.get_case(case_id)
        if case["status"] == "archived":
            raise ValueError("Reopen the archived case before adding research.")
        request = request.model_copy(update={"case_id": case_id})
        with self.session() as session:
            row = Investigation(
                id=identifier("inv"),
                case_id=case_id,
                status="queued",
                request=request.model_dump(),
                result={"progress": [], "results": [], "web_results": [], "errors": []},
                started_at=now(),
            )
            session.add(row)
            session.flush()
            result = as_dict(row)
        self.audit("investigation.create", result["id"])
        return result

    @staticmethod
    def investigation_summary(row):
        return {
            "id": row.id,
            "case_id": row.case_id,
            "status": row.status,
            "target": row.request["target"],
            "platform": row.request["platform"],
            "mode": row.request["mode"],
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "summary": row.result.get("summary", {}),
        }

    def investigations(self):
        with self.session() as session:
            return [
                self.investigation_summary(row)
                for row in session.scalars(
                    select(Investigation).order_by(Investigation.started_at.desc()).limit(200)
                )
            ]

    def get_investigation(self, investigation_id):
        with self.session() as session:
            row = session.get(Investigation, investigation_id)
            if row is None:
                raise KeyError("Investigation not found.")
            return as_dict(row)

    def save_investigation(self, investigation_id, result, status="running"):
        with self.session() as session:
            row = session.get(Investigation, investigation_id)
            if row is None:
                raise KeyError("Investigation not found.")
            row.result, row.status = result, status
            if status not in ("running", "queued"):
                row.finished_at = now()
            case = session.get(Case, row.case_id)
            case.updated_at = now()

    def add_evidence(self, case_id, investigation_id, body):
        self.get_case(case_id)
        body = {"id": identifier("ev"), "case_id": case_id, "investigation_id": investigation_id, **body}
        checksum = digest(body)
        with self.session() as session:
            session.add(
                Evidence(
                    id=body["id"],
                    case_id=case_id,
                    investigation_id=investigation_id,
                    body=body,
                    sha256=checksum,
                )
            )
        return {**body, "sha256": checksum}

    def evidence(self, case_id=None, investigation_id=None, offset=0, limit=200):
        query = select(Evidence)
        if case_id:
            query = query.where(Evidence.case_id == case_id)
        if investigation_id:
            query = query.where(Evidence.investigation_id == investigation_id)
        with self.session() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            items = [
                {**row.body, "sha256": row.sha256}
                for row in session.scalars(
                    query.order_by(Evidence.id).offset(max(0, offset)).limit(min(limit, 10000))
                )
            ]
            return {"items": items, "total": total}

    def get_evidence(self, evidence_id):
        with self.session() as session:
            row = session.get(Evidence, evidence_id)
            if row is None:
                raise KeyError("Evidence not found.")
            return {**row.body, "sha256": row.sha256, "integrity_valid": digest(row.body) == row.sha256}

    def cache_get(self, key):
        with self.session() as session:
            row = session.get(Cache, key)
            if row and row.expires_at > now():
                return row.value
            if row:
                session.delete(row)
            return None

    def cache_set(self, key, value, seconds=900):
        with self.session() as session:
            session.merge(
                Cache(
                    key=key,
                    value=value,
                    expires_at=(datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(),
                )
            )

    def clear_cache(self):
        with self.session() as session:
            session.execute(delete(Cache))
        self.audit("cache.clear", "cache")

    def health(self, platform=None):
        with self.session() as session:
            if platform:
                row = session.get(Health, platform)
                return row.body if row else None
            return {row.platform: row.body for row in session.scalars(select(Health))}

    def save_health(self, platform, body):
        with self.session() as session:
            session.merge(Health(platform=platform, body=body))

    def network_cooldowns(self):
        with self.session() as session:
            return {row.host: row.until for row in session.scalars(select(Cooldown))}

    def save_cooldown(self, host, until):
        with self.session() as session:
            session.merge(Cooldown(host=host, until=until))

    def attach(self, case_id, request):
        case = self.get_case(case_id)
        if len(case["attachments"]) >= 10:
            raise ValueError("A case may have at most ten screenshots.")
        try:
            data = base64.b64decode(request.data_base64, validate=True)
        except ValueError:
            raise ValueError("Invalid base64 image.") from None
        media_type = (
            "image/png"
            if data.startswith(b"\x89PNG\r\n\x1a\n")
            else (
                "image/jpeg"
                if data.startswith(b"\xff\xd8\xff")
                else "image/webp"
                if data.startswith(b"RIFF") and data[8:12] == b"WEBP"
                else ""
            )
        )
        if not media_type or len(data) > 5_000_000:
            raise ValueError("Use a PNG, JPEG, or WebP screenshot smaller than 5 MB.")
        attachment_id = identifier("file")
        metadata = {
            "filename": request.filename,
            "media_type": media_type,
            "size": len(data),
            "source_url": display_url(safe_url(request.source_url)) if request.source_url else "",
            "sha256": hashlib.sha256(data).hexdigest(),
            "collected_at": now(),
            "verification": "USER-PROVIDED — NOT INDEPENDENTLY VERIFIED",
        }
        with self.session() as session:
            session.add(Attachment(id=attachment_id, case_id=case_id, metadata_json=metadata, content=data))
        self.audit("attachment.add", case_id)
        return {"id": attachment_id, **metadata}

    def attachment(self, attachment_id):
        with self.session() as session:
            row = session.get(Attachment, attachment_id)
            if row is None:
                raise KeyError("Attachment not found.")
            return row.metadata_json, row.content

    def prune(self, days, apply=False):
        if not 1 <= days <= 36500:
            raise ValueError("Retention must be between 1 and 36500 days.")
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self.session() as session:
            ids = list(
                session.scalars(select(Case.id).where(Case.updated_at < cutoff, Case.status == "archived"))
            )
        if apply:
            for case_id in ids:
                self.delete_case(case_id)
        return {"case_ids": ids, "applied": apply, "cutoff": cutoff}

    def overview(self):
        with self.session() as session:
            counts = {
                "cases": session.scalar(select(func.count()).select_from(Case)),
                "active_cases": session.scalar(
                    select(func.count()).select_from(Case).where(Case.status == "active")
                ),
                "investigations": session.scalar(select(func.count()).select_from(Investigation)),
                "evidence": session.scalar(select(func.count()).select_from(Evidence)),
            }
            summaries = list(session.scalars(select(Investigation.result)))
        counts.update(
            {
                name: sum(result.get("summary", {}).get(name, 0) for result in summaries)
                for name in (
                    "profiles",
                    "verified_profiles",
                    "possible_matches",
                    "platforms_checked",
                    "public_urls",
                )
            }
        )
        return {
            "counts": counts,
            "recent": self.investigations()[:8],
            "health": self.health(),
            "counting_note": "Profile and URL counts are observations across runs, not unique people.",
        }

    def audit_log(self):
        with self.session() as session:
            return [
                as_dict(row) for row in session.scalars(select(Audit).order_by(Audit.id.desc()).limit(200))
            ]
