"""Authenticated local API. Run one worker; long-running jobs live in this process."""

import hmac
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analytics import compare
from .config import Settings
from .engine import Engine
from .models import (
    AttachmentRequest,
    CaseCreate,
    CaseUpdate,
    ImportRequest,
    InvestigationRequest,
    Verification,
    now,
)
from .reports import render_report
from .search_engines import search_catalog
from .security import display_url, safe_url
from .storage import Store

MAX_BODY = 7_100_000


def create_app(settings=None, *, store=None, network=None, registry=None):
    settings = settings or Settings()
    if settings.token and len(settings.token) < 32:
        raise ValueError("SOCIALINTEL_API_TOKEN must contain at least 32 characters.")
    settings.token = settings.token or secrets.token_urlsafe(32)
    store = store or Store(settings.data_dir)
    engine = Engine(settings, store, network=network, registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        await engine.close()
        store.engine.dispose()

    app = FastAPI(
        title="SocialIntel API",
        version="0.1.0",
        lifespan=lifespan,
        description="Public-source research with explicit uncertainty. Every /api route requires a bearer token.",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.engine, app.state.store, app.state.settings = engine, store, settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    buckets = defaultdict(deque)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api"):
            origin = request.headers.get("origin")
            same_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
            allowed_origin = not origin or origin == same_origin or origin in settings.allowed_origins
            if not allowed_origin or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
            if request.method == "OPTIONS":
                return Response(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": origin or same_origin,
                        "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
                        "Access-Control-Allow-Headers": "Authorization,Content-Type",
                        "Vary": "Origin",
                    },
                )
            authorization = request.headers.get("authorization", "")
            expected = "Bearer " + settings.token
            if not hmac.compare_digest(authorization.encode(), expected.encode()):
                return JSONResponse(
                    {"detail": "A valid bearer token is required."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            peer = request.client.host if request.client else "local"
            if peer not in buckets and len(buckets) >= 1000:
                buckets.clear()
            bucket = buckets[peer]
            stamp = time.monotonic()
            while bucket and bucket[0] < stamp - 60:
                bucket.popleft()
            if len(bucket) >= 240:
                return JSONResponse(
                    {"detail": "API rate limit reached."}, status_code=429, headers={"Retry-After": "60"}
                )
            bucket.append(stamp)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            if length > MAX_BODY:
                return JSONResponse({"detail": "Request is too large."}, status_code=413)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    return JSONResponse({"detail": "Request is too large."}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store" if path.startswith("/api") else "no-cache"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if path != "/docs":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            )
        if path.startswith("/api") and request.headers.get("origin") in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request.headers["origin"]
            response.headers["Vary"] = "Origin"
        return response

    @app.exception_handler(KeyError)
    async def missing(_request, _error):
        return JSONResponse({"detail": "Requested record was not found."}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(_request, error):
        return JSONResponse({"detail": str(error)[:300]}, status_code=400)

    @app.exception_handler(Exception)
    async def failed(_request, _error):
        return JSONResponse(
            {"detail": "Internal processing error. No credentials or upstream response bodies are exposed."},
            status_code=500,
        )

    @app.get("/api/overview")
    def overview():
        return store.overview()

    @app.get("/api/platforms")
    def platforms():
        return engine.registry.catalog(settings)

    @app.get("/api/platforms/{platform}")
    def platform_detail(platform: str):
        engine.registry.get(platform)
        return next(item for item in engine.registry.catalog(settings) if item["platform"] == platform)

    @app.get("/api/platforms/{platform}/health")
    def platform_health(platform: str):
        adapter = engine.registry.get(platform)
        return {
            "observed": store.health(platform),
            "configured": engine.registry.configuration(adapter, settings)[0],
            "status": adapter.manifest.status,
            "note": "Configuration and last observed request; not a live network probe.",
        }

    @app.get("/api/health")
    def health():
        return {
            "providers": store.health(),
            "catalog": engine.registry.catalog(settings),
            "plugin_errors": engine.registry.plugin_errors,
        }

    @app.get("/api/settings")
    def configuration():
        return {
            **settings.public(),
            "search_engines": search_catalog(settings),
            "limits": InvestigationRequest(target="example").limits.model_dump(),
        }

    @app.get("/api/plugins")
    def plugins():
        return {
            "providers": [item for item in engine.registry.catalog(settings) if item["plugin"]],
            "errors": engine.registry.plugin_errors,
            "note": "Install trusted Python packages locally; configure SOCIALINTEL_PLUGINS and restart. No remote code installation.",
        }

    @app.post("/api/investigations", status_code=202)
    async def start(request: InvestigationRequest):
        return engine.submit(request)

    @app.post("/api/search/username", status_code=202)
    @app.post("/api/discovery", status_code=202)
    async def discover(request: InvestigationRequest):
        return engine.submit(request.model_copy(update={"mode": "discovery"}))

    @app.post("/api/search/web", status_code=202)
    async def web_search(request: InvestigationRequest):
        if request.search_engine == "none":
            raise ValueError("Choose a configured search provider.")
        return engine.submit(request.model_copy(update={"mode": "discovery", "target_type": "display_name"}))

    @app.get("/api/investigations")
    def investigations():
        return store.investigations()

    @app.get("/api/investigations/{investigation_id}")
    def investigation(investigation_id: str):
        return store.get_investigation(investigation_id)

    @app.post("/api/investigations/{investigation_id}/cancel")
    async def cancel(investigation_id: str):
        return await engine.cancel(investigation_id)

    @app.post("/api/investigations/{investigation_id}/rerun", status_code=202)
    async def rerun(investigation_id: str):
        record = store.get_investigation(investigation_id)
        return engine.submit(InvestigationRequest.model_validate({**record["request"], "refresh": True}))

    @app.get("/api/compare")
    def comparison(before: str, after: str):
        return compare(store.get_investigation(before), store.get_investigation(after))

    @app.get("/api/cases")
    def cases():
        return store.cases()

    @app.post("/api/cases", status_code=201)
    def create_case(request: CaseCreate):
        return store.create_case(request)

    @app.get("/api/cases/{case_id}")
    def case(case_id: str):
        return store.get_case(case_id)

    @app.patch("/api/cases/{case_id}")
    def update_case(case_id: str, request: CaseUpdate):
        return store.update_case(case_id, request)

    @app.delete("/api/cases/{case_id}", status_code=204)
    def delete_case(case_id: str):
        store.delete_case(case_id)
        return Response(status_code=204)

    @app.post("/api/cases/{case_id}/import", status_code=201)
    def import_fields(case_id: str, request: ImportRequest):
        url = display_url(safe_url(request.source_url))
        evidence = [
            store.add_evidence(
                case_id,
                None,
                {
                    "platform": request.platform,
                    "field": name,
                    "value": value,
                    "source_url": url,
                    "collected_at": now(),
                    "method": "USER EXPORT",
                    "verification": Verification.IMPORT.value,
                    "confidence": "UNVERIFIED",
                    "notes": request.notes,
                    "provider": "user-export",
                },
            )
            for name, value in request.fields.items()
        ]
        store.audit("evidence.import", case_id)
        return {"items": evidence}

    @app.post("/api/cases/{case_id}/attachments", status_code=201)
    def attach(case_id: str, request: AttachmentRequest):
        return store.attach(case_id, request)

    @app.get("/api/attachments/{attachment_id}")
    def attachment(attachment_id: str):
        metadata, data = store.attachment(attachment_id)
        extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[metadata["media_type"]]
        return Response(
            data,
            media_type=metadata["media_type"],
            headers={"Content-Disposition": f'attachment; filename="{attachment_id}.{extension}"'},
        )

    @app.get("/api/evidence")
    def evidence(
        case_id: str | None = None,
        investigation_id: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=1000),
    ):
        return store.evidence(case_id, investigation_id, offset, limit)

    @app.get("/api/evidence/{evidence_id}")
    def evidence_item(evidence_id: str):
        return store.get_evidence(evidence_id)

    @app.get("/api/reports/{case_id}")
    def report(case_id: str, format: str = "html"):
        content, media_type = render_report(store, case_id, format)
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{case_id}.{format}"'},
        )

    @app.delete("/api/cache", status_code=204)
    def clear_cache():
        store.clear_cache()
        return Response(status_code=204)

    @app.post("/api/retention")
    def retention(days: int = Query(90, ge=1, le=36500), apply: bool = False):
        return store.prune(days, apply)

    @app.get("/api/audit")
    def audit():
        return store.audit_log()

    web = Path(__file__).parent / "web"
    if web.is_dir() and (web / "index.html").is_file():
        if (web / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def dashboard():
            return FileResponse(web / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def build_instructions():
            return {
                "product": "SocialIntel",
                "dashboard": "Run npm ci && npm run build in frontend, then python scripts/build_frontend.py.",
                "api_docs": "/docs",
            }

    # OpenAPI declares bearer auth so Swagger's Authorize button works for every API operation.
    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
        }
        for path, methods in schema["paths"].items():
            if path.startswith("/api"):
                for operation in methods.values():
                    if isinstance(operation, dict):
                        operation["security"] = [{"BearerAuth": []}]
        return schema

    app.openapi = openapi
    return app
