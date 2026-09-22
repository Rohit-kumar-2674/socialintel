# Release validation — 2026-09-22

The original SocialIntel source was recovered and continued. This was not a replacement implementation. The untouched recovered source passed 102 existing tests before the release fixes.

## Results observed locally

| Check | Result |
| --- | --- |
| Fresh Python 3.12 virtual environment using dependency locks | Installed; `pip check` passed |
| Backend, API, CLI, provider/privacy, SDK and regression suite | **122 passed** |
| Ruff checks | Passed |
| TypeScript and Vite production build | Passed |
| Installable example provider | Installed from its own package and registered through the SDK |
| Python wheel | Built with dashboard assets; installed into a separate environment |
| Installed-wheel smoke checks outside the source tree | Dashboard served, unauthenticated API rejected, authenticated catalog returned |
| Chromium dashboard workflow | Passed; browser 153.0.8010.0 |
| Browser console exceptions | None |
| Browser requests to external hosts | None |
| Responsive overflow checks | Passed at 320, 390, 768, 1440 pixels |
| Docker Compose configuration | YAML structure and security settings checked |
| Local container build/run | **Not executed: no Docker daemon available in this environment** |

The UI checks used a local server with explicitly synthetic HTTP fixtures. They covered wrong/correct tokens, cases and saved notes, imports and HTML escaping, unsupported Instagram primary with honest fallback, public-post collection, profiles, evidence, timelines, relationship graph, four export formats, provider readiness versus observations, health/plugins/settings, refresh, mobile navigation, and tab locking. No real social account was investigated.

Two dependency deprecation warnings originate from FastAPI/Starlette's test client (httpx/portal integration); they did not fail tests. They should be revisited when upgrading that integration rather than suppressing all warnings.

## Limits of this validation

Offline tests validate code behavior, not successful live access to each upstream provider. Experimental and credential-dependent statuses remain unchanged. Provider terms, quotas, schema changes, network policy, and valid credentials can still prevent collection. No independent security audit, load test, live-provider certification, or full Windows/macOS/Android test matrix is claimed.

The committed GitHub Actions workflow adds a Python 3.11–3.13 matrix, a repeatable dashboard/package job, and an actual Docker build/start/authentication check. A committed workflow is not itself proof that those remote runs succeeded; consult the repository's Actions results for the specific commit.
