# Contributing

Open a focused issue or pull request describing a concrete problem, the change, and how it was verified. Keep changes scoped; do not replace unsupported providers with URL-guessing claims or fabricated data.

Set up Python and frontend dependencies using the README. Before submitting:

```sh
python -m ruff check backend tests scripts plugins
python -m pytest -q
npm run build --prefix frontend
python scripts/build_frontend.py
```

For UI changes, run the browser smoke checks in `docs/TESTING.md`. For provider changes, include synthetic success, missing, denied/private, malformed, rate-limit, and source-provenance fixtures. Tests must not query real accounts or require secrets. Describe any upstream API or quota requirements honestly in the manifest and provider matrix.

Plugins must follow `docs/PROVIDER_SDK.md`. Collection changes must preserve HTTPS/DNS/SSRF boundaries, public visibility filters, robots exclusions, response/request budgets, and persistent cooldowns. Source verification, search hints, imports, and identity inferences must remain separate.

Never commit `.env`, tokens, case databases, screenshots of real investigations, downloaded personal data, or virtual environments. Review dependency/lock changes intentionally. A public-ready patch includes documentation, meaningful regression coverage, and a truthful validation record. The project's MIT license applies to contributed source.
