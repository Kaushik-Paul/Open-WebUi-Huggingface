# Project guidance

This repository vendors Open WebUI for a single owner on a Hugging Face Docker Space, with the same container runnable locally. Local implementation and verification are **complete**. `PLAN.md` is the original specification, not a backlog. Its old `SURPLUS_AI_KEY` spelling was superseded: **only `SURPLUS_API_KEY` is supported**.

Read `README.md`, `main/docs/customization.md`, `main/docs/verification.md`, and `main/docs/request-path-audit.md` before changing behavior. Put unresolved product or deployment questions in root `doubts.md` and continue independent work. Do not re-implement the plan, add a parallel Open WebUI, or expand scope into audio, search, video, music, or extra job UIs.

Remaining gaps are owner decisions in `doubts.md` (Space PostgreSQL/S3, preferred models). Do not provision or purchase databases, buckets, or paid Space hardware unless the user explicitly authorizes it. Space deploys use `main/scripts/deploy_space.py` only.

## Layout and provenance

- Application source: `main/upstream/`, pinned to Open WebUI v0.11.3 / `2a960a59fe1dbbd35282f0556b3666d81102e781`. Full archive checksum and customization inventory: `upstream.lock.json`.
- Project scripts, the existing test suite, and docs belong under `main/scripts`, `main/tests`, and `main/docs`. Root holds Docker/Compose/env/ignore infrastructure and top-level docs.
- Do not replace the custom frontend with a stock build, install a second unpatched Open WebUI package, build from `main`/`latest`, or create duplicate hand-maintained patch trees.
- Preserve upstream licenses, notices, logos, titles, and branding. The root `LICENCE` is also retained.
- Root ignore rules explicitly preserve upstream `src/lib`; do not let a generic Python `lib/` ignore silently omit the frontend. Never track dependencies, caches, build output, `.env*` secrets, database files, or private uploads.

## Important boundaries

- The existing root `.env` belongs to the user. Never print, overwrite, or commit it. Read it with dotenv without overriding process environment. Do not run billable provider tests unless authorized.
- `secret_refs.py` accepts only allowlisted `SURPLUS_API_KEY` in explicit `key_source=secret` mode. Existing metadata-less settings are literal. Resolve once per outbound request; never write the returned value into settings, caches, exports, logs, events, frontend data, or URLs.
- Chat source metadata stays with the native connection config, including reorder/import/export/delete. Image generation/editing have independent persisted sources/keys/models.
- Private policy is mandatory: owner bootstrap after migrations, native backend auth, one configured admin, no public signup/initial HTTP onboarding, no Direct Connections/OAuth/LDAP/trusted-header auth. Persisted config/API calls cannot relax it. Do not globally disable configuration persistence.
- Public login assets and the Socket.IO transport handshake are intentional; private APIs/files/provider calls and socket operations still require native authentication.
- Raw password localStorage is explicitly requested. Keep the remember checkbox/help text, successful-login-only save, session-first validation, one automatic attempt, opt-out, invalid-password cleanup, password-change cleanup, and cross-tab logout. Do not silently replace this with token-only persistence. Native logout/revocation needs Redis for existing JWTs; signing-key rotation invalidates all old JWTs.
- Surplus edits are JSON; standard OpenAI edits remain multipart. Respect explicit image-edit metadata, max eight sources, no masks, private native file ownership, bounded image decoding, public-only connect-time DNS resolution, and no authorization on CDN downloads. Do not automatically retry image requests.

## Do not add tests, scripts, or docs unless required

`main/tests/` and `main/scripts/` are required and must stay. They are the existing regression and operations suite, not leftover scaffolding. Do **not** delete them, replace them, or add a second tree.

Do **not** create new tests for documentation, copy, formatting, comments, ignore-file edits, or other mechanical changes. Do not add snapshot/golden files, extra e2e suites, Playwright configs, pytest plugins, or coverage tooling. Do not duplicate coverage that already exists in `main/tests/`.

Only extend an existing test file when the change actually alters one of these surfaces:

- credential resolution (`secret_refs.py` and callers)
- private-access / auth / bootstrap policy
- Surplus chat or image request paths, including downloads/SSRF
- remembered-login behavior

If the change does not affect those surfaces, run nothing new and do not invent fixtures. Prefer updating an existing test over adding a file. Fixture checks use a dedicated mock provider and owner, never the user's `.env`.

Do not add scripts unless there is a documented operational gap that `entrypoint.sh`, `check_upstream.py`, `reset_owner_password.py`, `run_fixture.sh`, `run_local.py`, `smoke_surplus.py`, or `deploy_space.py` cannot cover. The Docker image must contain only `entrypoint.sh` and `reset_owner_password.py`. Do not add new `main/docs/` files for small edits; update the existing doc that already covers the topic.

`deploy_space.py` is the Hugging Face upload path. Never print, log, or commit `.env` or Space secret values. Default Space id is `HF_SPACE_ID` or `{hf-username}/Open-WebUI-Surplus`, created private. Re-run the same script after code changes; pass `--skip-env` for a code-only update. Do not add a second deploy helper.

## Development and checks

Run frontend commands from `main/upstream`, not root:

```sh
CYPRESS_INSTALL_BINARY=0 npm ci --force
npm run build
npm run check
```

The untouched pin has thousands of existing Svelte/TypeScript errors; compare diagnostics against the verified archive rather than hiding errors with ts-nocheck or claiming the check passes. Production builds are a separate gate. See `main/docs/verification.md` for counts/results.

From root, after changing customization behavior:

```sh
python3 main/scripts/check_upstream.py
python -m pytest main/tests/test_*.py -q
main/upstream/node_modules/.bin/vitest run --config main/tests/vitest.config.mts
docker compose up --build
```

Python tests need pytest, pytest-asyncio, FastAPI/aiohttp/Pillow, typer/uvicorn, and httpx; prefer the runtime's compatible dependency versions or an isolated venv. `integration_check.py`, `security_check.py`, `persistence_check.py`, and `e2e/browser_check.py` use a dedicated mock provider and fixture owner, not the user's `.env`. Security checks intentionally exhaust the login limiter; run them last or allow its window to expire. Browser tests use Playwright with local Chrome, never the user's browser profile. Isolated full-app fixtures: `sh main/scripts/run_fixture.sh` after building `owui-hf:local`.

The Dockerfile runs UID 1000 and port 7860, with one Uvicorn worker and `/app/backend/data` writable. The local named volume is durable across recreation. A Space's local filesystem is ephemeral; actual production durability requires configured/tested PostgreSQL plus durable file storage.

## Handoff discipline

Update the request-path audit and customization inventory when adding outbound credential paths or auth surfaces. Update verification notes with what actually ran, including failures and pending checks. No fabricated live compatibility, browser, storage, or deployment claims. Use fixture canary keys to test absence from config/database/logs/bundles. Back up database and files before upgrades; rollback may require the matching pre-migration data backup.
