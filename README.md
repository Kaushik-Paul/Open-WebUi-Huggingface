---
title: Open WebUI for Surplus
emoji: 💬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Open WebUI on Hugging Face Spaces

The actual Open WebUI v0.11.3 application, customized for one owner and Surplus text/image APIs. The same Docker image runs locally and in a Docker Space. Upstream branding and licenses are retained in `main/upstream/`.

## Local setup

1. Copy `.env.example` to `.env` **only if you do not already have a `.env`**. For an existing file, merge the missing entries and keep your `SURPLUS_API_KEY`.
2. Set `WEBUI_ADMIN_EMAIL`, a unique `WEBUI_ADMIN_PASSWORD` (12+ characters), and a random, stable `WEBUI_SECRET_KEY` (32+ characters). Generate the signing key with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
3. Set `SURPLUS_API_KEY` and `PROVIDER_SECRET_NAMES=SURPLUS_API_KEY`. Copy the connection defaults from the example; `OPENAI_API_KEY=SURPLUS_API_KEY` is the **reference**, not your key's value.
4. Run `docker compose up --build` and open **http://localhost:7860**. First build downloads the full upstream dependencies and can take several minutes. Startup fails if owner configuration is missing.
5. Log in with the configured owner. In **Admin Panel → Settings → Connections**, verify the Surplus connection. In **Settings → Images**, choose OpenAI, Surplus compatibility, Secret name, `SURPLUS_API_KEY`, and a current image model; then enable generation. Editing has its own model and credentials.

The local named volume preserves accounts, chats, settings, uploads, and generated images across container recreation. Do not run `docker compose down -v` unless you intend to erase that data.

“Remember me on this browser” is enabled by default and stores your email **and raw password** in localStorage, as requested. Same-origin JavaScript and anyone with access to the browser profile can read it. Opt out on shared devices. Logout clears it across tabs. Provider secret values stay on the server.

## Spaces

Create a Docker Space from this repository. Add the `.env.example` secret values as Space Secrets and configuration values as Space Variables; set `WEBUI_URL` to the Space origin. Use external PostgreSQL and durable upload storage for durable use. The default container filesystem is ephemeral on Spaces; a directory named `/data` does not make it durable. No Hugging Face access token is required for injected Secrets.

See [deployment and recovery](main/docs/deployment.md), [Surplus setup](main/docs/surplus.md), [customizations and upgrades](main/docs/customization.md), [request-path audit](main/docs/request-path-audit.md), and [verification results](main/docs/verification.md). Open decisions are in [doubts.md](doubts.md).
