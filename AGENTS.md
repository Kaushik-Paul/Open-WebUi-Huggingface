# Project guidance

This repository vendors the actual Open WebUI application for a single owner on a Hugging Face Docker Space, with the same container runnable locally. Read `README.md`, `main/docs/customization.md`, `main/docs/verification.md`, and `main/docs/request-path-audit.md` before changing behavior. `PLAN.md` is the original specification; its old `SURPLUS_AI_KEY` spelling was superseded by the user's explicit instruction: **only `SURPLUS_API_KEY` is supported**. Put unresolved product/deployment questions in root `doubts.md` and continue independent work.

## Layout and provenance

- Application source: `main/upstream/`, pinned to Open WebUI v0.11.3 / `2a960a59fe1dbbd35282f0556b3666d81102e781`. Full archive checksum and customization inventory: `upstream.lock.json`.
- Project scripts/tests/docs belong under `main/scripts`, `main/tests`, and `main/docs`. Root holds Docker/Compose/env/ignore infrastructure and top-level docs.
- Do not replace the custom frontend with a stock build, install a second unpatched Open WebUI package, build from `main`/`latest`, or create duplicate hand-maintained patch trees.
- Preserve upstream licenses, notices, logos, titles, and branding. The root `LICENCE` is also retained.
- Root ignore rules explicitly preserve upstream `src/lib`; do not let a generic Python `lib/` ignore silently omit the frontend. Never track dependencies, caches, build output, `.env*` secrets, database files, or private uploads.

## Important boundaries

- The existing root `.env` belongs to the user. Never print, overwrite, or commit it. Read it with dotenv without overriding process environment. Do not run billable provider tests unless authorized; the implementation session authorized limited live checks, not perpetual background usage.
- `secret_refs.py` accepts only allowlisted `SURPLUS_API_KEY` in explicit `key_source=secret` mode. Existing metadata-less settings are literal. Resolve once per outbound request; never write the returned value into settings, caches, exports, logs, events, frontend data, or URLs.
- Chat source metadata stays with the native connection config, including reorder/import/export/delete. Image generation/editing have independent persisted sources/keys/models.
- Private policy is mandatory: owner bootstrap after migrations, native backend auth, one configured admin, no public signup/initial HTTP onboarding, no Direct Connections/OAuth/LDAP/trusted-header auth. Persisted config/API calls cannot relax it. Do not globally disable configuration persistence.
- Public login assets and the Socket.IO transport handshake are intentional; private APIs/files/provider calls and socket operations still require native authentication. Run the security fixture after changing routes/middleware/socket behavior.
- Raw password localStorage is explicitly requested. Keep the remember checkbox/help text, successful-login-only save, session-first validation, one automatic attempt, opt-out, invalid-password cleanup, password-change cleanup, and cross-tab logout. Do not silently replace this with token-only persistence. Native logout/revocation needs Redis for existing JWTs; signing-key rotation invalidates all old JWTs.
- Surplus edits are JSON; standard OpenAI edits remain multipart. Respect explicit image-edit metadata, max eight sources, no masks, private native file ownership, bounded image decoding, public-only connect-time DNS resolution, and no authorization on CDN downloads. Do not automatically retry image requests.

## Development and checks

Run frontend commands from `main/upstream`, not root:

```sh
CYPRESS_INSTALL_BINARY=0 npm ci --force
npm run build
npm run check
```

The untouched pin has thousands of existing Svelte/TypeScript errors; compare diagnostics against the verified archive rather than hiding errors with ts-nocheck or claiming the check passes. Production builds are a separate gate. See `main/docs/verification.md` for counts/results.

From root:

```sh
python3 main/scripts/check_upstream.py
python -m pytest main/tests/test_*.py -q
main/upstream/node_modules/.bin/vitest run --config main/tests/vitest.config.mts
docker compose up --build
```

Python tests need pytest, pytest-asyncio, FastAPI/aiohttp/Pillow, typer/uvicorn, and httpx; prefer the runtime's compatible dependency versions or an isolated venv. `integration_check.py`, `security_check.py`, `persistence_check.py`, and `e2e/browser_check.py` use a dedicated mock provider and fixture owner, not the user's `.env`. Security checks intentionally exhaust the login limiter; run them last or allow its window to expire. Browser tests use Playwright with local Chrome, never the user's browser profile.

The Dockerfile runs UID 1000 and port 7860, with one Uvicorn worker and `/app/backend/data` writable. The local named volume is durable across recreation. A Space's local filesystem is ephemeral; actual production durability requires configured/tested PostgreSQL plus durable file storage. Do not provision or purchase resources, or deploy a Space, without task authorization. Document missing external resources in `doubts.md`.

## Handoff discipline

Update the request-path audit and customization inventory when adding outbound credential paths or auth surfaces. Update verification notes with what actually ran, including failures and pending checks. No fabricated live compatibility, browser, storage, or deployment claims. Use fixture canary keys to test absence from config/database/logs/bundles. Back up database and files before upgrades; rollback may require the matching pre-migration data backup.
