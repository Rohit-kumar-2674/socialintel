# API reference

The bundled dashboard and API share `http://127.0.0.1:8000`. `/docs` provides OpenAPI documentation. Every `/api` operation requires `Authorization: Bearer <SOCIALINTEL_API_TOKEN>`; the OpenAPI Authorize button supports it. Tokens are never accepted in query parameters. This is a single-operator API, not a multi-user authorization model.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/overview` | Workspace counts and recent runs |
| GET | `/api/platforms` | Honest capability catalog |
| GET | `/api/platforms/{platform}` | Provider manifest |
| GET | `/api/platforms/{platform}/health` | Configuration and last observation |
| GET | `/api/health` | All recorded provider observations; no live probes |
| GET | `/api/settings` | Limits, non-secret configuration flags, search catalog |
| GET | `/api/plugins` | Registered extensions and sanitized load failures |
| POST | `/api/investigations` | Queue a bounded investigation; returns 202 |
| GET | `/api/investigations` | Recent investigation summaries |
| GET | `/api/investigations/{id}` | Request, status, results, provenance, graph |
| POST | `/api/investigations/{id}/cancel` | Cancel queued/running work |
| POST | `/api/investigations/{id}/rerun` | New manual snapshot, skipping result cache |
| POST | `/api/search/username`, `/api/discovery` | Full discovery |
| POST | `/api/search/web` | Display-name search with a configured search API |
| GET, POST | `/api/cases` | List/create cases |
| GET, PATCH, DELETE | `/api/cases/{id}` | Read, edit notes/tags/status, or delete |
| POST | `/api/cases/{id}/import` | Import public-source fields with an unverified label |
| POST | `/api/cases/{id}/attachments` | Store a supplied public-source screenshot |
| GET | `/api/attachments/{id}` | Download screenshot bytes |
| GET | `/api/evidence` | Paginated observations; `case_id`, `investigation_id`, `offset`, `limit` |
| GET | `/api/evidence/{id}` | Observation with integrity verification |
| GET | `/api/reports/{case_id}?format=html` | HTML, md, json, or csv attachment |
| GET | `/api/compare?before={id}&after={id}` | Compare observed snapshots |
| DELETE | `/api/cache` | Clear shared result cache, preserving cooldowns |
| POST | `/api/retention?days=90&apply=false` | Preview old archived-case deletion; apply only deliberately |
| GET | `/api/audit` | Latest workspace operation records |

Example request body (replace the target with a permitted public identifier):

```json
{
  "platform": "github",
  "target": "YOUR_PUBLIC_USERNAME",
  "mode": "selected",
  "collect_posts": false,
  "search_engine": "none",
  "limits": {"max_requests": 10, "max_seconds": 30}
}
```

Poll the returned investigation ID until its status is no longer queued/running. `completed` means the requested pipeline finished; inspect each provider's status for collection success or limitations. It does not mean every provider succeeded. `FOUND` verifies a public source observation, never the subject's identity.

Unknown/malformed requests yield 400/422, missing authentication 401, disallowed origins 403, unknown records 404, oversized bodies 413, and API throttling 429. Maximum request body is 7.1 MB; the authenticated API allows 240 requests/minute per peer. Screenshot limit is 5 MB each and ten per case. Images are not remotely fetched or rendered as executable content. Only import public material; the service cannot independently establish the provenance of user-supplied files.
