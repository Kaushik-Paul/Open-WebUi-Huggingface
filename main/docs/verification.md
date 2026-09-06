# Verification record — 2026-09-06

## Executed

- Imported Open WebUI v0.11.3 at `2a960a59fe1dbbd35282f0556b3666d81102e781`; verified the source archive SHA-256 and documented all 16 modified upstream files plus five new helpers. Runtime image digests are recorded in `upstream.lock.json`.
- Upstream-compatible frontend install and production builds passed. Root multi-stage Docker build passed. Full fixture runtime served on port 7860 as UID/GID 1000 with custom frontend/backend. Final helper changes were exercised in the fixture using the workspace backend and compiled frontend, then copied into the built runtime image for a self-contained final smoke test.
- **47 backend tests passed:** explicit source semantics, name/allowlist/value/CRLF rejection, request-local resolution/rotation, unsupported authentication combinations, HTTPS destinations, image generation/JSON edits, provider errors, malformed/oversized images, public/private redirect behavior, connect-time DNS rejection, streaming tool/usage chunks, immutable startup policy, and bounded throttling.
- **5 frontend tests passed:** safe redirects, corrupt records, opt-out, invalid-password removal, retention on throttling/network failure, logout cleanup.
- **Full-container API integration passed:** anonymous private routes denied, signup denied, owner login, saved chat/image references and independent metadata, unsaved verification, streaming/non-streaming chat, separate image/edit catalogs, generation, editing, mask rejection, authenticated private image download, and saved chat fixture.
- **Additional security fixture passed:** rejected secret names, connection reorder preservation, echoed-provider-error redaction, forged tokens, login 429 behavior, and anonymous Socket.IO operations using native WebSocket transport. Config database and container logs contained no resolved canary key. Compiled frontend and project scripts/tests/docs contained no actual Surplus key.
- **Browser suite passed in headless Chrome:** Log in button, remember default, successful manual login, reload, exactly one automatic login after token/cookie expiry, cross-tab logout without a loop, opt-out, and login with blocked persistent storage. A discovered anonymous version-polling rejection was fixed and the suite rerun successfully.
- **Recreation/rotation passed:** both fixture containers were removed/recreated with a rotated dummy provider key and the same named data volume. The existing owner, sample chat, stored source/reference settings, and generated image remained available. New chat and image requests used the rotated key; the mock provider checked the actual outbound bearer value.
- Persisted writes requesting signup/direct-connections enablement and login-form disablement remained constrained. Authentication-disabled startup failed closed. Python syntax and shell syntax checks passed.

## Upstream type-check baseline

`npm run check` on the untouched archive reported **7,789 errors and 202 warnings in 343 files**. The final customized source reported **7,759 errors and 202 warnings in 343 files**. Comparing normalized file/message diagnostics found no new errors from the customization. Existing warnings include Svelte markup/accessibility diagnostics and missing package export conditions. The successful production build does **not** mean the full upstream type check passes. No `ts-nocheck` suppression was added.

The provider transport currently subclasses the pinned aiohttp ClientSession, which emits one deprecation warning in tests; functionality passed. Revisit this wrapper on an aiohttp major-version upgrade.

## Live Surplus

The user's existing `SURPLUS_API_KEY` was used only server-side for the authorized checks. No credentials were printed or saved in reports. Safe status/model/request-ID results are in `live-surplus-results.json`.

- Authenticated model discovery: 402 models, including 55 image-output entries at test time.
- Text: `gpt-4o-mini` returned HTTP 200, text delta `OK`, and a completed SSE stream with `[DONE]`.
- Other tested sellers (`openai-gpt-oss-120b`, `minimax-m2.1`) returned HTTP 200 SSE without `[DONE]` under small output budgets. Do not equate those HTTP successes with a verified useful final answer. The local streaming fixture explicitly covers EOF without `[DONE]`.
- Generation: `venice-z-image-turbo`, one 512×512 request, returned a valid image (214,951 bytes).
- Editing: `grok-imagine-edit` rejected a 512×512 size request with 400; a corrected JSON request omitting size succeeded with one result. Edit size therefore defaults to blank and is documented as model dependent. No ambiguous timeout was automatically retried.

## Pending external acceptance

No Space was deployed and no database/bucket/hardware was provisioned. Actual Space proxy streaming, origin-specific cookies/localStorage, reconnect behavior, and persistent PostgreSQL/S3 recreation/restore remain pending the user's deployment/storage choices in `doubts.md`. Local named-volume persistence is verified; ephemeral Space SQLite is not presented as durable production storage.

Live vision input and multi-turn function-tool execution were not billed/tested against Surplus. Request/stream transport fixtures preserve their payloads; actual support remains model/seller dependent. Browser tests focused on authentication; image request/storage behavior was exercised through the full application API and live provider adapter, not a complete browser image-edit interaction.
