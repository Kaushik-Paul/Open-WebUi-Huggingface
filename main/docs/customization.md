# Customizations and upstream upgrades

`main/upstream` is the sole editable source snapshot of Open WebUI v0.11.3. No nested Git repository or unpatched installed Open WebUI package is used. `upstream.lock.json` records the release, full commit, archive URL, SHA-256, and reviewed changed upstream files. Licenses/notices and branding are preserved.

Custom backend helpers: `utils/secret_refs.py` (one allowlisted environment reference), `private_deployment.py` (startup/private HTTP policy), `provider_http.py` (safe provider transport), and `surplus_images.py` (JSON edits, catalog capabilities, bounded image results). They are wired into native env/config/auth lifecycle, chat/images/pipelines/Anthropic/model unload, and diagnostic events. Settings metadata lives in native config rows and API configs.

Frontend changes: native auth page, remembered-login helper, auth API cleanup, root-layout cross-tab logout, app-shell blocked-storage fallback, connection editor, and image settings/API. New image fields use the native config API; old source-less settings are literal. Source metadata remains attached to native connection config during reorder/import/export/delete.

## Verification commands

```sh
python3 main/scripts/check_upstream.py
# Use the Docker runtime dependencies or an isolated environment containing
# pytest, pytest-asyncio, fastapi, aiohttp, pillow, typer, uvicorn, and httpx.
python -m pytest main/tests/test_secret_refs.py main/tests/test_provider_requests.py main/tests/test_surplus_images.py main/tests/test_private_access.py -q
cd main/upstream
CYPRESS_INSTALL_BINARY=0 npm ci --force
npm run build
npm run check
```

Full fixture scripts are `main/tests/mock_provider.py`, `integration_check.py`, and `e2e/browser_check.py`. They require a test-only owner and mock base URL. Browser tests use Playwright and a local Chrome executable; never use your real browser profile. See verification notes for the existing upstream type-check baseline.

## Upgrade procedure

1. Back up database/uploads and save the working image and signing secret securely.
2. Select a stable release and retrieve its full commit and source archive. Verify SHA-256. Inspect upstream release/security/license notes.
3. Compare `check_upstream.py --report` against the previous archive and port only the documented customization changes into a fresh snapshot. Keep new upstream dependency locks and test their compatible runtime versions.
4. Re-audit all credential reads and authentication boundaries, including newly added routes/tools and file access. Inspect config-schema changes; current upstream uses per-key rows.
5. Update the lock only after reviewing source differences. Run unit, integration, browser, container, recreation/restore, and canary-disclosure checks. Separate baseline type errors from new ones.
6. Test migrations on a restored copy. Deploy only with authorization. Roll back code together with a compatible data backup if schemas changed.

Do not vendor generated build/cache/node_modules/data files. The root Python ignore template originally ignored every `lib/` directory; explicit upstream exceptions preserve the required Svelte `src/lib` tree. Credentials must never appear in patches, screenshots, docs, test logs, archive metadata, or frontend bundles.

Frontend helper tests run from root with `main/upstream/node_modules/.bin/vitest run --config main/tests/vitest.config.mts`. Backend test glob `main/tests/test_*.py` also includes redirect/DNS/download limit coverage.

To start an isolated full-app test after building `owui-hf:local`, run `sh main/scripts/run_fixture.sh`. It uses a dedicated Docker network, volume, mock provider, dummy owner, and port 17860. Existing containers with the same names must be deliberately stopped/removed first; the script does not delete them. Install `main/tests/requirements.txt` alongside runtime dependencies for Python/browser testing.
