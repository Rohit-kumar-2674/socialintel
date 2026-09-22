# Changelog

## 0.1.0 — 2026-09-22

Initial research release, completed from the recovered original implementation.

- Shared CLI / API / React investigation workflow, local cases, attributed evidence, graphs, timelines, and HTML/Markdown/JSON/CSV exports.
- Seven built-in collection adapters with explicit capabilities and 22 catalog-only unsupported platforms.
- Bounded public HTTPS retrieval, DNS/IP validation, visibility filters, persisted cooldowns, cancellation, retention previews, and integrity checks.
- Fixed jobs cancelled before execution remaining queued, including shutdown handling.
- Reject mismatched profile platform URLs before creating a case.
- Prevent configured API tokens from appearing in serve logs.
- Separate provider readiness from last-observed availability in the dashboard; recover selection after case deletion.
- Add SDK v1, provenance validation, isolated plugin configuration failures, and an installable example.org provider.
- Add Docker/Compose setup, dependency version locks, distribution packaging, CI, regression tests, and operator/developer documentation.

Experimental adapters are not a live-service guarantee. PostgreSQL, multi-user roles, background monitoring, private-content access, remote plugin installation, and identity verification are not part of this release.
