# Open WebUI on Hugging Face Spaces — implementation plan

Status: local implementation and verification completed; see main/docs/verification.md for executed checks and pending external Space/storage acceptance. The user subsequently specified SURPLUS_API_KEY only; references to SURPLUS_AI_KEY below are historical.

Prepared: 2026-09-06. The project currently contains empty `README.md`, `PLAN.md`, and `main/__init__.py`, with root ignore/license/metadata files. No applicable `AGENTS.md` was found. Upstream source was inspected for this plan; its moving `main` branch is not a build pin.

## 1. Required outcome

Build the actual Open WebUI application for a single owner on a Hugging Face Docker Space, with the same container runnable locally. Preserve its existing chat and administration experience.

1. Show a login form with a **Log in** button. Require valid backend authentication for application data, provider calls, and administration, including direct API requests.
2. Remember the login in the same browser, including the explicitly requested password storage in localStorage. Logout clears remembered credentials.
3. Accept `SURPLUS_AI_KEY` in an API Key field and resolve its value from server environment variables, supplied through Space Secrets or root local `.env`. The reference remains in settings; the resolved key never comes back to the browser.
4. Make Surplus the primary documented provider for text chat, streaming, image generation, and supported image editing. Image creation must work from Open WebUI's image-generation controls, with visible, downloadable results. Image input/vision is a separate capability to verify for compatible chat models.
5. Keep application code, helper scripts, custom tests, and implementation docs under `main/`. Keep project infrastructure/configuration and top-level project documentation at root.

Scope includes server-managed OpenAI-compatible chat connections and the separate OpenAI-compatible image generation/editing settings. Other standalone audio, search, video, music, or arbitrary integration settings are not promised by this version. Existing connection-backed operations must still work. Do not expand “etc.” into a new video/music job UI. Disable browser Direct Connections: they cannot read server Secrets without exposing credentials.

Implement and test locally first. This plan itself does not instruct the next agent to provision accounts, purchase hardware/storage, or deploy. Document live checks needing a configured Space or funded provider account; execute them when subsequently authorized.

## 2. Evidence and decisions

- Native Open WebUI login already exists and stores a session token in localStorage. Extend that flow rather than adding a separate password proxy. [Login source](https://github.com/open-webui/open-webui/blob/main/src/routes/auth/+page.svelte)
- Native environment-based owner bootstrap is first-install provisioning. Disabling signup alone needs special attention because the inspected signup route permits a first-user exception. [Auth router](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/auths.py)
- Chat provider credentials and image credentials follow different backend paths. Image model discovery and image edits need Surplus-specific compatibility work. [Chat router](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/openai.py), [image router](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/images.py)
- Surplus's documented canonical base URL is `https://api.surplusintelligence.ai/v1`. Use bearer API-key authentication. Discover current model IDs instead of copying a static catalog. [Surplus overview](https://www.surplusintelligence.ai/docs)
- The requested production chat-doc URL and production image-doc URL failed retrieval during planning. Surplus's own `preview.surplusintelligence.ai` documentation was accessible and is cited below. Recheck production documentation and authenticated behavior during implementation; preview documentation is not proof that every feature works on production.

## 3. Source strategy and repository layout

Select a stable upstream release during implementation, record its full commit SHA and source archive checksum, and use its compatible dependency lockfiles. Remap the source locations below if that release differs. Never build from an unpinned `main`, `latest`, or an unversioned pip install.

Use a tracked upstream snapshot and small direct source changes. Build its Svelte frontend and Python backend together. Do not copy a stock frontend over the custom build or install a second unpatched Open WebUI package.

```text
/
├── PLAN.md
├── README.md                        # Space YAML + quick start
├── Dockerfile                       # Frontend build + Python runtime stages
├── compose.yaml                     # Local env_file, ports, named volume
├── .dockerignore
├── .gitignore
├── .env.example                     # Placeholders only
├── upstream.lock.json               # Release, SHA, checksum, source URL
├── requirements.txt                 # Only if extra project dependencies need it
├── LICENCE                          # Retain existing project file
└── main/
    ├── __init__.py
    ├── upstream/                    # Tracked source, no nested .git
    │   ├── backend/open_webui/
    │   │   └── utils/
    │   │       ├── secret_refs.py    # New shared server resolver
    │   │       └── surplus_images.py # Scoped compatibility helper if needed
    │   ├── src/                     # Login, connection, image settings changes
    │   └── ...                      # Upstream manifests, lockfiles, assets, licenses
    ├── scripts/
    │   ├── entrypoint.sh            # Startup validation; exec server
    │   └── check_upstream.py        # Provenance verification
    ├── tests/
    │   ├── test_secret_refs.py
    │   ├── test_provider_requests.py
    │   ├── test_surplus_images.py
    │   ├── test_private_access.py
    │   └── e2e/
    └── docs/
        ├── customization.md         # Changed files and upstream upgrade procedure
        ├── deployment.md            # Local/Spaces setup, persistence, recovery
        ├── surplus.md               # Chat/image configuration and compatibility
        └── request-path-audit.md    # Auth and outbound credential coverage
```

Upstream build manifests stay in the snapshot to preserve upstream tooling; project-owned infrastructure stays at root. Maintain one editable source copy, not both a vendored tree and duplicate hand-maintained patches. Record customizations against the pinned SHA in small commits and documentation. Preserve upstream notices, licenses, and branding. Root dependency configuration must defer to the pinned backend's requirements/lockfiles rather than drift into an independent dependency set. [Upstream repository](https://github.com/open-webui/open-webui)

## 4. Login and private access

### 4.1 Native account and backend policy

Retain the native email/password form and label its submit action **Log in**. Remember the email as well as the password; a custom password-only identity adapter is unnecessary.

Provision the owner using `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD`, and optionally `WEBUI_ADMIN_NAME`. Require a stable, random `WEBUI_SECRET_KEY`. Reuse upstream password hashing, account helpers, and session validation. Bootstrap runs after migrations during startup, before application traffic is accepted. These bootstrap variables do not automatically synchronize an existing account's password on every restart. [Environment reference](https://docs.openwebui.com/reference/env-configuration/)

Implement a single-owner deployment policy:

- Require `WEBUI_AUTH=true`, enable password/login-form authentication, and disable public signup and initial-admin HTTP signup, including on an empty database. Reject authentication-disabled startup configuration.
- Validate required credentials before startup. Missing configuration, failed bootstrap, or a missing/mismatched configured owner in an existing database must fail closed with a sanitized error, never fall back to public onboarding. Bootstrap once using the native helper, not a public signup HTTP request. Start with one worker to avoid bootstrap races.
- Enforce these restrictions after persisted configuration is loaded and when relevant settings APIs are updated. A stale database setting or direct admin API request must not re-enable public signup or Direct Connections. Keep unrelated provider settings persistent.
- Disable unused trusted-header, LDAP, and OAuth login paths for this deployment. Do not trust arbitrary incoming identity headers.
- Inventory HTTP routes, public share/file paths, and Socket.IO/WebSocket handlers. Protect every operation exposing private data or invoking providers. Disable public sharing or apply native access checks where upstream intentionally exposes it.
- Only login assets, sanitized bootstrap configuration, sign-in, and a value-free health endpoint should be anonymously available. Protect/disable debug/API-doc surfaces in production. Static login assets being public do not grant application access.
- Preserve admin authorization for connection/image settings and verification. Preserve user/file ownership checks for generated images, downloads, and edits.
- Reuse existing login rate limiting; add bounded server-side throttling if absent. Test `429` behavior and avoid using spoofable forwarded headers as the sole identity source.

Starting points relative to `main/upstream/`: `backend/open_webui/main.py` startup/lifespan, `routers/auths.py`, `utils/auth.py`, and socket authentication. Recheck their APIs at the selected release.

### 4.2 Remembered password: required behavior and tradeoff

Implement the user's explicit localStorage requirement. A raw stored password is readable by same-origin JavaScript and someone with access to the browser profile; an XSS vulnerability can expose it. Token-only persistence would reduce exposure of a reusable password, but is an alternative rather than a silent replacement for this request. Base64 or encryption with a browser-stored key does not solve this.

Add **Remember me on this browser**, enabled by default for this personal deployment, with short help explaining that it saves the password locally. Use a versioned namespaced record such as `owui-hf.rememberedLogin.v1` containing email/password, separate from native session-token storage.

1. Save credentials only after successful manual login with Remember me enabled. If unchecked, delete any prior record. Never store failed passwords.
2. On reload/reopen, validate the native session first. If valid, use it without resending the password.
3. With no valid session and a remembered record, attempt one normal backend sign-in. Storage contents are never trusted as authentication.
4. On invalid credentials, clear the remembered record and invalid session, then show the form. Network errors/rate limits show a retry option without looping or unnecessarily deleting valid credentials.
5. Logout clears credentials and token state before navigation, performs native logout/cookie cleanup, and suppresses automatic login on the logout page. Synchronize logout across tabs using storage events or equivalent existing behavior.
6. Handle blocked storage and malformed records gracefully; manual login must still work. Read storage only in browser lifecycle code. A successful password change removes the remembered record.
7. Restrict login redirects to validated local routes. Remove password/session-bearing debug logs from touched flows. Do not place credentials in URLs, analytics, provider settings, or server logs.

Document password recovery at the pinned version. Changing a bootstrap Secret is not itself an existing-account password reset. Document explicit session invalidation, including signing-key rotation and any additional native session cleanup required; do not claim a password change revokes every existing token.

## 5. Shared secret-reference contract

### 5.1 UI and stored format

Add credential-source metadata with choices **Secret name** and **Literal API key** to server-managed chat connections AND image generation/editing credentials. Default new entries to Secret name; existing settings lacking source metadata remain Literal API key for backward compatibility. Store this metadata in the corresponding persisted config schema, including migrations/defaults and frontend API types.

The Secret name field accepts exactly `SURPLUS_AI_KEY`, without `${...}` or prefixes. In chat settings, preserve URL/key/source association during reorder, import/export, edit, and deletion. In image settings, add separate source metadata for generation and editing; both can reference the same name. Do not silently overwrite a separately configured image key when a chat connection changes.

| Source | Input | Behavior |
| --- | --- | --- |
| Secret name | `SURPLUS_AI_KEY` | Resolve allowed server environment value |
| Secret name | Invalid, absent, disallowed, or empty secret | Error; no provider call; no literal fallback |
| Literal API key | Actual key | Existing literal behavior remains |
| No authentication | Empty key | Native no-auth behavior; skip resolution |

Validate secret names with `^[A-Z_][A-Z0-9_]*$`, document case sensitivity, trim name input, treat whitespace-only values as missing, and reject CR/LF in header credentials. Resolve once without recursion, shell evaluation, template expansion, or file reads.

Add custom runtime configuration `PROVIDER_SECRET_NAMES`, a comma-separated allowlist, e.g. `SURPLUS_AI_KEY`. Only listed names can be resolved. Reject application/auth/database secret names even if mistakenly listed. Document this extra setup step next to Space Secret creation. Provide no environment-value or environment-enumeration endpoint.

### 5.2 Backend resolution boundary

Implement one tested backend helper in `utils/secret_refs.py`, shared by chat and image integrations. Inputs are stored credential, source metadata, and allowlist; output is request-local credential material. Keep resolution separate from storage and config serialization.

- Save/return only the name and source metadata for reference-mode settings. Never put resolved values into database configuration, exports, global config, caches, browser responses, or frontend bundles.
- Resolve immediately before constructing outbound authentication, once per request. Do not mutate shared connection objects or interpret an already-resolved key as another name.
- Apply to unsaved connection verification and every saved request path: model discovery, streaming/non-streaming chat, Responses, embeddings, connection-backed speech, generic proxy/model management, and native provider adaptations present at the pin. Audit internal/background callers as well.
- Independently cover image configuration verification/model lookup, generation, edits, and any image tool wrappers. A chat-only patch is incomplete.
- Search every `Authorization`, `api-key`, `x-api-key`, and relevant key-config read. Preserve correct Azure/other key-based header formats. Do not replace session/OAuth/Entra credentials with environment keys; explicitly reject unsupported combinations.
- Do not expand references in arbitrary headers, URLs, prompts, or request bodies. Reject conflicting custom authentication-header overrides for Secret name mode.
- Only admins configure server-managed destinations/credentials. Require HTTPS production provider URLs and avoid forwarding credentials on cross-origin redirects. Allow local HTTP mock providers only under an explicit test configuration.
- Invalid verification/config input yields a sanitized `400`; unavailable runtime credentials for a saved connection yield `503`, with no outbound call. Admins may see the reference name and corrective action; ordinary users get a generic provider-unavailable message.
- Sanitize exception/provider-error paths and logs so a provider echoing an auth header cannot disclose a key. Do not pass raw request headers or arbitrary provider error bodies to the UI.
- Environment edits become effective when the process receives a refreshed environment, normally via restart/recreation. Saved references remain unchanged when keys rotate. Do not promise `.env` edits automatically update a running process.

Chat navigation hints: `backend/open_webui/routers/openai.py` functions such as `get_openai_connection`, `get_headers_and_cookies`, `send_get_request`, `verify_connection`; frontend `src/lib/components/admin/Settings/Connections.svelte`, `Connections/OpenAIConnection.svelte`, shared `AddConnectionModal.svelte`, and `src/lib/apis/openai`. Verify paths at the chosen version; one helper does not cover all header branches.

## 6. Surplus chat and images — mandatory integration work

### 6.1 Chat, discovery, and vision

Document the chat connection as base URL `https://api.surplusintelligence.ai/v1`, key source Secret name, key `SURPLUS_AI_KEY`. Do not append `/chat/completions` to the base URL or duplicate `/v1`.

Surplus documents `POST /v1/chat/completions`, ordinary OpenAI messages, SSE streaming, and model-dependent function tools. Implement/test streaming text, final usage chunks, and tool-call deltas without assuming every model accepts every OpenAI parameter. Use model capability metadata for tools and vision; image input in a chat message is not an image-generation request. Distinguish invalid keys, insufficient balance, unavailable sellers, and unhealthy sellers in sanitized UI errors. [Surplus chat reference](https://preview.surplusintelligence.ai/docs/api-reference/chat-completions)

Retrieve models with the server-side key. Separate text/vision model choices from image/media choices using available catalog capability data, not hardcoded model-name guesses. Provide a validated manual model-ID fallback when metadata is insufficient. Catalog presence does not ensure there is a currently available seller. [Surplus model documentation](https://preview.surplusintelligence.ai/docs/marketplace/models)

Test image input to a vision-capable chat model and multi-turn function-tool transcripts with mocks. An automatic “draw an image” chat tool may rely on model tool support; the explicit image-generation control must work even if the selected chat model cannot call tools. If automatic image tools are enabled, route them through the same authenticated image service.

### 6.2 Image generation configuration

Extend the existing image settings UI and backend config, not just Connections. Starting points are `backend/open_webui/routers/images.py` and `src/lib/components/admin/Settings/Images.svelte`. Inspect image API types, config key mappings, file storage, and tool wrappers at the pin.

Configure the native OpenAI-compatible image engine with:

```text
Image generation enabled: true
Engine: OpenAI-compatible
Provider compatibility: Surplus (new explicit option if necessary)
Base URL: https://api.surplusintelligence.ai/v1
API key source: Secret name
API key: SURPLUS_AI_KEY
Image model: select a currently available image-generation model
Default count: 1
Default size: a size supported by that model
API version: empty (not an Azure endpoint)
```

Likely upstream settings include `ENABLE_IMAGE_GENERATION`, `IMAGE_GENERATION_ENGINE`, `IMAGE_GENERATION_MODEL`, `IMAGES_OPENAI_API_BASE_URL`, `IMAGES_OPENAI_API_KEY`, and `IMAGES_OPENAI_API_PARAMS`; confirm exact support before writing `.env.example`. The new source/compatibility metadata must be persisted and returned safely. Do not preconfigure an unverified default image model.

Surplus documents synchronous JSON requests to `/v1/images/generations`, with `model`, `prompt`, and optional count/size/quality/resolution/response format; results can contain `b64_json` or URLs. Edits use `/v1/images/edits`, with JSON image data URIs or HTTPS source URLs; masks are documented as unsupported. [Surplus image reference](https://preview.surplusintelligence.ai/docs/api-reference/image-generations)

Implementation requirements:

- Use the shared resolver for the image key. Verify saved config, validation, model lookup, and request construction all preserve the reference rather than its value.
- Replace/bypass the stock OpenAI-only image choices for this compatibility mode. Query Surplus's catalog and select image-capable models; allow manual exact IDs. Do not restrict selections to DALL·E/GPT image names.
- Construct a model-compatible JSON payload. Preserve requested dimensions and allow supported optional quality/resolution fields through typed validation. Omit unsupported defaults instead of assuming every model accepts OpenAI-specific parameters. Start with one image and prevent duplicate clicks/submissions.
- Normalize both base64 and URL responses into native Open WebUI file records. Use the existing authenticated upload/storage pipeline so results render in chat, download, and survive reload. Retain ownership and safe content-type/size validation.
- For URL results, fetch through the backend with SSRF protection, redirect validation, byte/time limits, and TLS verification. Do not send the Surplus bearer key to an unrelated image CDN or redirected host. Use no auth for signed download URLs; only explicitly trusted same-origin downloads may receive provider authorization if required.
- Persist generated image bytes and chat/file associations; a temporary provider URL is not durable storage. Test the final files under the selected persistence backend.
- Configure a bounded image timeout separately from short discovery timeouts; show loading, cancellation/error state, and a retry action. Do not automatically retry ambiguous generation timeouts because the original request may already have completed and been charged.
- Keep image generation endpoints, result downloads, and image tool invocations private. Never put the provider credential in an image URL or browser fetch header.

### 6.3 Image editing compatibility

The inspected Open WebUI edit branch constructs multipart form data. Surplus's documented edit request is JSON. Add an explicit Surplus compatibility branch while retaining the standard multipart OpenAI path for other providers.

- Configure edit engine/base URL/model and key source separately (`IMAGES_EDIT_OPENAI_*` or equivalents at the pin). Reuse `SURPLUS_AI_KEY` by reference, not by copying the resolved value into edit config.
- Convert validated, owner-accessible uploaded input into a bounded data URI where needed; a private Open WebUI file URL is not fetchable by Surplus. Never expose private uploads publicly merely to make edits work.
- Map a single image to Surplus's JSON image field; map multiple references to its supported input structure while preserving order/roles. Keep generation and edit model choices distinct and capability-aware.
- Use only documented supported edit parameters and limits. Disable mask/inpainting controls for this provider and return a clear unsupported-feature error if a direct API caller supplies a mask. Revalidate exact limits and capabilities against production docs at implementation time.
- Run edit responses through the same result normalization, authentication, durable storage, and error handling as generation.

Required live compatibility check, when authorized: one short streamed chat, one small image generation, and one supported edit using current model IDs. Record model IDs, response format, safe request ID, and outcome without credentials. If production differs from preview docs, adapt and document the actual behavior rather than marking the feature complete from mocks alone.

## 7. Docker, configuration, and durable state

### 7.1 Build and runtime

Root `README.md` begins with Space YAML containing `sdk: docker` and `app_port: 7860`. Bind the server to `0.0.0.0:7860`, expose that port, and run as non-root UID 1000 with writable runtime/cache directories. Space Secrets arrive as runtime environment variables. Never include secrets in build args, frontend builds, or image layers. [Docker Spaces documentation](https://huggingface.co/docs/hub/spaces-sdks-docker)

Adapt the pinned upstream multi-stage build with compatible pinned Node/Python versions, frozen frontend dependencies, upstream backend dependencies, and the compiled frontend in its expected backend location. Record runtime image digests when practical. External Surplus calls do not require bundled Ollama/CUDA.

`main/scripts/entrypoint.sh` validates required configuration without printing values, prepares permitted writable directories, and `exec`s the correct server command with explicit host/port and one worker. Keep migrations/bootstrap inside upstream startup; do not run a competing initialization process. Add a value-free health check after initialization.

Local quick start: copy `.env.example` to `.env`, fill values, and run `docker compose up --build`. Compose must use `env_file: .env`; interpolation alone does not inject every variable. Any optional native development entrypoint loads the root `.env` before backend config imports, without overriding supplied process environment.

Extend `.gitignore` and `.dockerignore` for `.env` variants (retain `.env.example`), runtime data, secrets, dependencies, caches, build output, and IDE files. Keep operational logic under `main/scripts/`.

### 7.2 Environment example

Validate upstream names at the selected pin. `PROVIDER_SECRET_NAMES` is proposed custom configuration. Additional source metadata is persisted by the UI; do not infer secret mode from a key string at runtime.

```dotenv
# Secrets: placeholders only; replace locally or set corresponding Space Secrets.
WEBUI_ADMIN_PASSWORD=replace-with-a-strong-unique-password
WEBUI_SECRET_KEY=replace-with-a-long-random-stable-signing-secret
SURPLUS_AI_KEY=replace-with-the-real-surplus-key

# Non-secret configuration: Space Variables or local .env.
WEBUI_ADMIN_EMAIL=owner@example.com
WEBUI_ADMIN_NAME=Owner
WEBUI_AUTH=true
ENABLE_SIGNUP=false
ENABLE_LOGIN_FORM=true
ENABLE_DIRECT_CONNECTIONS=false
ENABLE_PERSISTENT_CONFIG=true
PROVIDER_SECRET_NAMES=SURPLUS_AI_KEY
# Set WEBUI_URL to the actual Space origin or local origin.
# Durable Spaces deployment also requires DATABASE_URL and upload-storage config.
```

Never make placeholder passwords usable defaults. Document all additional version-specific flags required by the private-access policy. A Hugging Face access token is not needed merely to read injected Space Secrets.

Surplus setup guide must cover both Admin Connections and Admin Images: create the Secret, allow its name, restart as required, configure chat, configure image generation and editing, select capability-appropriate models, then verify each independently. Surplus account availability/balance and model seller availability are external prerequisites; no wallet/payment automation is part of this project.

### 7.3 Persistence and recovery

Keep UI-managed settings persistent. Do not globally disable persistent config just to enforce login policy; enforce those restrictions separately. Upstream documents that disabling persisted configuration can discard UI changes after restart. [Configuration persistence](https://docs.openwebui.com/reference/env-configuration/)

Current Hugging Face docs describe ephemeral container storage and attached bucket volumes. Do not assume PRO grants a durable `/data` filesystem or that creating the directory makes it durable. [Spaces storage](https://huggingface.co/docs/hub/spaces-storage)

- Local default: SQLite and all user data on a Docker named volume, with the correct upstream `DATA_DIR`.
- Durable Spaces deployment: prefer external PostgreSQL through a `DATABASE_URL` Secret for accounts/chats/settings, plus a supported durable upload backend or verified volume for source/generated images. Keep disposable caches local. Document resources; do not purchase/provision them automatically.
- Do not put a live SQLite database on a bucket/FUSE mount without documented compatible locking and atomic-write semantics. A mount resembling a directory is insufficient evidence. If a genuine durable filesystem is available and verified, SQLite can be a simpler alternative.
- Ephemeral SQLite is only a labeled demo mode. It does not pass durable-deployment acceptance, even if remembered credentials still exist in the browser.
- Back up database and user/generated files before upgrades. Test restore and document schema-aware rollback; an old image may not understand newly migrated data. Keep the signing key stable across normal restarts.

## 8. Implementation sequence

1. **Baseline:** pin/import upstream, record provenance, establish the root Docker/Compose build, and verify the unmodified baseline serves on port 7860.
2. **Private access:** implement startup validation/bootstrap policy, route/socket restrictions, persisted-setting enforcement, and login throttling. Then add remembered-login UI/state and logout cleanup.
3. **Secret references:** implement shared resolver and metadata; extend chat add/edit/verify APIs and UI; audit all connection-backed outbound auth paths and preserve literal compatibility.
4. **Surplus chat/images:** add documented chat setup, capability-aware discovery, image key-source configuration, generation compatibility, image result persistence, and JSON edit adaptation. Cover all related config schemas/frontend types. Update the request-path audit.
5. **Verification:** add focused tests below, run relevant upstream checks and frontend production build, build/run the final container with a mock provider, and test local state across recreation. Validate the selected durable database/upload configuration.
6. **Handoff:** populate root README and `main/docs/` with exact commands, setup screenshots only if useful, variable meanings, rotation/recovery, Surplus capabilities, persistence, and upstream update procedure. List executed tests and pending live Space/provider checks accurately.

## 9. Acceptance tests

Use dummy canary credentials and a local mock OpenAI-compatible provider. Automated tests should not spend Surplus balance. Assert observable behavior/security boundaries rather than mirror implementation.

| Area | Required evidence |
| --- | --- |
| Build | Pinned production image contains custom frontend/backend; non-root runtime serves on port 7860. |
| Bootstrap | Owner created once; missing/invalid configuration fails closed; HTTP signup rejected even with an empty DB. |
| Private access | Anonymous chat/models/settings/verify/images/files/shares and private socket operations denied; minimal login/health paths work. |
| Policy | Persisted settings or API updates cannot re-enable signup/Direct Connections. |
| Login | Wrong credentials fail, valid credentials work, attempts are throttled, forged storage/token never bypasses backend validation. |
| Remembering | Successful login stores requested credentials; reload/reopen works; expired session triggers at most one auto-login; opt-out and unavailable storage work. |
| Logout | Credentials/native state cleared across tabs; no immediate auto-login; password changes remove stale remembered credentials. |
| Resolver | Missing/empty/disallowed/invalid name or CR/LF key fails before network; no recursion or silent fallback; literal/no-auth compatibility retained. |
| Association | Two concurrent connections receive their own credentials; reorder/delete preserves URL/key/source metadata; chat/image sources remain separate. |
| Chat | Verify/discovery/streaming/non-streaming and other audited paths receive resolved key; usage/tool-call chunks, vision inputs, and error handling work. |
| Image requests | Generation uses exact Surplus endpoint, bearer key, supported JSON fields/model; edits use Surplus JSON while standard OpenAI edits retain multipart. |
| Image results | Both base64 and URL formats render, download, and survive chat reload/recreation; source/result files remain owner-protected. |
| Download safety | Fake external CDN/redirect receives no Surplus key; unsafe URLs and oversized/malformed image data are rejected. |
| Image UX | Separate image model selection works; one-image default, loading/error/cancellation states, unsupported-mask handling, and no duplicate automatic retry. |
| Error cases | Invalid key, balance issue, no seller, unhealthy upstream, image timeout, and malformed result produce useful sanitized errors. |
| No disclosure | Canary key absent from settings responses/exports/DB/frontend storage/bundle/logs/error bodies; fake provider echo errors do not reveal it. |
| Rotation | Recreate process with changed injected key; same saved reference uses the new key for chat AND images. |
| Durability | Owner, sample chat, provider source/reference metadata, uploads, and generated image remain after recreation using documented durable storage. |
| Live Space | When available/authorized, confirm proxy streaming, socket reconnect, UID permissions, browser storage on actual Space origin, and real Surplus chat/generation/edit. |

Run backend resolver/request tests, relevant frontend/type checks at the pin, a production build, and a focused browser suite. Record pre-existing upstream check failures separately. Do not say a live provider or deployment check passed when only mocks were run.

Definition of done: requested login/localStorage and secret-reference behavior works in the built local application; Surplus chat plus image generation/editing integration is implemented and tested; code follows the `main/` structure; configuration never needs a raw Surplus key in the browser; backend access restrictions and durability are verified. Actual production compatibility remains explicitly marked pending until live checks are authorized and executed.
