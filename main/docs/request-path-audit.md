# Request-path and private-access audit

Pin: Open WebUI v0.11.3, full commit/checksum in `upstream.lock.json`.

| Surface | Enforcement / credential boundary |
| --- | --- |
| Native signup / admin add-user / OAuth / LDAP / public shares | Disabled by the outer private middleware; signup stays false even with an empty DB. |
| Accounts and startup | Native migrations and `create_admin_user`; require exactly the configured admin owner before serving. Missing credentials/auth-disabled configuration fail closed. |
| Private HTTP API, files, cache, model metadata, configuration, provider verification, image generation/edit | Outer middleware calls native `get_current_user` with token/cookie and checks owner identity; route-specific admin/ownership checks remain. Deep links redirect to login for HTML requests. |
| Public HTTP | Login shell/build assets, sanitized `/api/config`, sign-in/sign-out, and value-free `/health`. Socket.IO transport handshake is public; authenticated operations remain native. |
| Socket.IO | Native connect/user-join token validation and session lookup; chat, usage, channel, note, Yjs join/update/awareness handlers enforce user/session/room access. The anonymous handshake supports the native login flow; it is not authenticated app access. |
| Immutable settings | `models/config.py` reads/writes force signup/direct/LDAP/OAuth restrictions while retaining unrelated settings persistence. |
| Chat saved connection | `routers/openai.get_openai_connection` resolves a local key; config getters return stored references. Covers chat, Responses, embeddings, speech, generic proxy/model management, and native Azure/Anthropic branches. |
| Chat discovery | `get_models_request` resolves independently; verification resolves unsaved input with 400 errors. No second resolution in header construction. |
| Pipeline/model unload | Pipeline helper delegates to the same saved connection resolver; main model unload resolves against its exact base URL/config. |
| Image configuration | Separate persisted generation/edit source and compatibility fields; validation uses resolver without persisting output. |
| Image discovery/generation/edit | Shared secret resolver; Surplus JSON helper; standard OpenAI still supported. Native tools call the same functions. |
| Image source and result files | Native file ownership/storage API; bounded validated image decode/download, no CDN auth forwarding, public-only connect-time DNS resolver. |
| Provider transport | No automatic redirects; TLS enabled; upstream errors replaced with status-based messages; response headers allowlisted for chat streaming. |
| Browser password | Versioned localStorage record saved after successful manual login; cookie/token validated first; one auto-sign-in; invalid credentials clear record; opt-out/logout/password change clear it. |

The reference mode only supports `SURPLUS_API_KEY` and requires its explicit allowlist entry. It does not expand headers, URLs, prompts, templates, shell expressions, or arbitrary environment variables. Audio/search/video/music standalone configuration does not inherit chat source metadata.

Security checks use canary values and fixture providers. This audit identifies the pinned code paths; external provider behavior, enabled custom Python tools/functions, and future upstream changes require fresh review. The single owner is an administrator and can intentionally run custom tools; do not grant this account to untrusted users.
