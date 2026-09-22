# Security and public-only policy

SocialIntel is a local, single-operator research application. Do not expose it directly to the Internet or treat it as a multi-tenant service.

## Collection boundary

Use only public pages, public APIs, or explicitly authorized APIs restricted to public data. No private messages, locked/private profiles, subscriber-only or paid content, deleted-content recovery, authentication/CAPTCHA bypass, rate-limit evasion, credential theft, or identity claims. User imports must follow the same rule and remain unverified. Unsupported providers remain labeled unsupported; a denial or unavailable source is not an account-existence finding.

The HTTP client uses HTTPS port 443 only, blocks local/private/reserved addresses (including DNS results and IPv6 translation/tunnel forms), connects to the checked IP while retaining TLS hostname verification, refuses redirects, limits response size to 1 MB, and does not inherit proxies. Robots exclusions, login/challenge detection, provider quotas, and retry windows must not be bypassed. HTML collection is conservative and incomplete; it does not execute page JavaScript or recover hidden content.

Built-in providers allowlist returned fields and check public visibility where supplied. No facial recognition or hidden-contact enrichment is performed. Optional contact extraction reads only explicitly published text and is off by default. Search snippets and analytical correlations remain distinct from source-verified observations.

## Local application boundary

All `/api` operations require a bearer token. The server validates host/origin, rejects cross-site browser API requests, applies body/rate limits, and escapes exports. The dashboard uses no third-party images or scripts and does not send case data to analytics. API access logs are disabled by the CLI. Persistent configured tokens are never printed; locally generated session links are secrets.

SQLite and screenshots are not encrypted by the application. Use trusted local accounts, restrictive filesystem permissions, and appropriate disk encryption. Case deletion does not erase backups or guarantee forensic erasure. SHA-256 checksums detect payload changes relative to a stored digest but are not signatures or independent evidence authentication.

Plugins execute trusted Python code with application privileges. The SDK validates declarations and output provenance, but cannot sandbox a malicious package. Review source, dependencies, target domains, public-only behavior, and tests before installation. The dashboard cannot install remote code. Docker's non-root user, read-only root filesystem, capability restrictions, and localhost port binding do not turn plugins into isolated sandboxes.

## Reporting a vulnerability

Do not post credentials, real case material, private account data, or a working exploit against a third party in a public issue. Use the repository's private vulnerability-reporting facility if enabled; otherwise open a minimal issue asking for a private reporting channel without sensitive details. Include a synthetic reproduction, affected version, impact, and proposed fix privately once a channel is agreed.

This research release has not undergone an independent security audit. See `docs/VALIDATION.md` for the actual checks performed.
