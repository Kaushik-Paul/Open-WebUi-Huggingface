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

Local login, remembered credentials, secret-name API keys, Surplus chat, and Surplus image generation/editing are implemented. Open decisions (Space database/storage and preferred models) are in [doubts.md](doubts.md). Do not treat ephemeral Space disk as durable storage.

## Local setup

1. Copy `.env.example` to `.env` **only if you do not already have a `.env`**. For an existing file, merge the missing entries and keep your `SURPLUS_API_KEY`.
2. Set `WEBUI_ADMIN_EMAIL`, a unique `WEBUI_ADMIN_PASSWORD` (12+ characters), and a random, stable `WEBUI_SECRET_KEY` (32+ characters). Generate the signing key with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
3. Set `SURPLUS_API_KEY` and `PROVIDER_SECRET_NAMES=SURPLUS_API_KEY`. Copy the connection defaults from the example; `OPENAI_API_KEY=SURPLUS_API_KEY` is the **reference**, not your key's value.
4. Run `docker compose up --build` and open **http://localhost:7860**. First build downloads the full upstream dependencies and can take several minutes. Startup fails if owner configuration is missing.
5. Log in with the configured owner. In **Admin Panel → Settings → Connections**, verify the Surplus connection. In **Settings → Images**, choose OpenAI, Surplus compatibility, Secret name, `SURPLUS_API_KEY`, and a current image model; then enable generation. Editing has its own model and credentials.

The local named volume preserves accounts, chats, settings, uploads, and generated images across container recreation. Do not run `docker compose down -v` unless you intend to erase that data.

“Remember me on this browser” is enabled by default and stores your email **and raw password** in localStorage, as requested. Same-origin JavaScript and anyone with access to the browser profile can read it. Opt out on shared devices. Logout clears it across tabs. Provider secret values stay on the server.

Changing `WEBUI_ADMIN_PASSWORD` does not reset an existing account. While logged in, use native Account settings. Offline recovery: stop the service, back up data, then `docker compose run --rm --entrypoint python webui /app/scripts/reset_owner_password.py`. Rotate `WEBUI_SECRET_KEY` afterward to invalidate existing sessions.

## Spaces

The authenticated `hf` CLI is enough. The helper creates a **private** Docker Space, uploads Git-visible files (never `.env`), and copies owner configuration from the local `.env` into Space Secrets and Variables without printing values. It sets `WEBUI_URL` to the Space origin.

```sh
# From an environment that has huggingface_hub, for example the hf CLI:
#   /home/kaushik/.hf-cli/venv/bin/python main/scripts/deploy_space.py
python3 main/scripts/deploy_space.py --dry-run
python3 main/scripts/deploy_space.py
python3 main/scripts/deploy_space.py --skip-env   # later code-only updates
```

The helper builds the Svelte frontend locally, then uploads `main/frontend-dist` so Hugging Face does not run the memory-heavy Vite build. Re-run after frontend changes so the Space stays in sync. Local `docker compose` still compiles from source unless that dist directory contains `index.html` (delete it to force a local frontend rebuild).

Default Space: `kaushikpaul/Open-WebUI-Surplus` (override with `--repo-id` or `HF_SPACE_ID`). Use external PostgreSQL and durable upload storage for durable use. The default container filesystem is ephemeral on Spaces; a directory named `/data` does not make it durable. No Hugging Face access token is required for injected Secrets.

See [deployment and recovery](main/docs/deployment.md), [Surplus setup](main/docs/surplus.md), [customizations and upgrades](main/docs/customization.md), [request-path audit](main/docs/request-path-audit.md), and [verification results](main/docs/verification.md). Agent/maintainer rules, including when not to add tests, are in [AGENTS.md](AGENTS.md).
