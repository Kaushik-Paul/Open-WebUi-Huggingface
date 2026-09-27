# Open WebUI on Hugging Face Spaces

A private, single-owner deployment of [Open WebUI](https://github.com/open-webui/open-webui) **v0.11.3**, wired to [Surplus](https://www.surplusintelligence.ai/) for chat and image generation. The same Docker image runs locally and on a Hugging Face Docker Space. Upstream branding, notices, and licenses stay in `main/upstream/`.

The Space is private. Signup, public onboarding, Direct Connections, OAuth, LDAP, and trusted-header login stay off. One configured admin owns the instance.

---

## What this deployment adds

| Area | Behavior |
|---|---|
| **Access** | Native login for one owner. Persisted settings cannot turn signup back on or disable the login form. |
| **Chat** | OpenAI-compatible Surplus connection. The browser stores the secret **name** `SURPLUS_API_KEY`; the server resolves the key on each outbound request. |
| **Images** | Independent generation and edit settings, Surplus JSON edits, and private native file storage for results. |
| **Remembered login** | The login page can keep the email and password in this browser. See [Remembered login](#remembered-login). |
| **Local data** | A Docker named volume keeps accounts, chats, settings, uploads, and generated images across container recreation. |
| **Space data** | Supabase PostgreSQL holds chats and settings. A private Hugging Face bucket holds uploaded and generated files. |

The application pin, archive checksum, and customization inventory are in [`upstream.lock.json`](upstream.lock.json).

---

## Repository layout

```text
README.md                   This guide
LICENCE                     MIT license for this project's customizations
Dockerfile                  Runtime image (Python backend + prebuilt frontend)
compose.yaml                Local service and durable named volume
.env.example                Owner, Surplus, and image defaults
upstream.lock.json          Pinned Open WebUI release and changed files
main/
  upstream/                 Vendored Open WebUI v0.11.3 source
  frontend-dist/            Production Svelte build consumed by the image
  scripts/                  Entrypoint, deploy, checks, and owner-password reset
  tests/                    Existing regression suite
  docs/                     Surplus, deployment, customization, and verification
```

`main/frontend-dist` is produced locally and stays out of Git. The image copies that directory in as the finished frontend.

---

## Local setup

1. Copy `.env.example` to `.env` when that file does not already exist. When `.env` already exists, add any missing keys and keep the current `SURPLUS_API_KEY`.
2. Set `WEBUI_ADMIN_EMAIL`, a unique `WEBUI_ADMIN_PASSWORD` of at least 12 characters, and a stable `WEBUI_SECRET_KEY` of at least 32 characters:

   ```sh
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```

3. Set `SURPLUS_API_KEY` and `PROVIDER_SECRET_NAMES=SURPLUS_API_KEY`. In the connection defaults, `OPENAI_API_KEY=SURPLUS_API_KEY` is the environment **name** the server resolves on each request.
4. Build the frontend into `main/frontend-dist` when `main/frontend-dist/index.html` is missing, or after UI changes. `python3 main/scripts/deploy_space.py` builds it before an upload. `--dry-run` only lists the upload set.
5. Start the app:

   ```sh
   docker compose up --build
   ```

   Open <http://localhost:7860>. The first image build downloads the upstream Python dependencies and can take several minutes. Startup stops when the owner email, password, or signing key is missing.

6. Sign in as the configured owner. In **Admin Panel → Settings → Connections**, confirm the Surplus base URL `https://api.surplusintelligence.ai/v1`, **Secret name**, and `SURPLUS_API_KEY`. In **Settings → Images**, choose OpenAI, Surplus compatibility, the same secret name, and a current image model, then enable generation. Editing uses its own model and credentials.

The `webui-data` volume is the local database and file store. `docker compose down -v` deletes it.

---

## Remembered login

**Remember me on this browser** is on by default. A successful login saves the email and the password in `localStorage`. Same-origin scripts and anyone with access to that browser profile can read it. Leave it unchecked on a shared device.

Logout clears the saved record in other tabs of this browser. A wrong password removes the saved record. Changing the account password clears it as well. Provider keys stay on the server and are not written into the browser, exports, or logs.

---

## Configuration

Values live in the root `.env` locally and in Space Secrets or Variables when deployed. Placeholder values from `.env.example` are skipped.

| Variable | Role |
|---|---|
| `WEBUI_ADMIN_EMAIL` | Owner account created on first startup |
| `WEBUI_ADMIN_PASSWORD` | Initial owner password (12+ characters). Later changes do not reset an existing account |
| `WEBUI_SECRET_KEY` | JWT signing secret (32+ characters). Keep it stable across restarts |
| `SURPLUS_API_KEY` | Server-side Surplus key. The only allowed secret reference |
| `PROVIDER_SECRET_NAMES` | Must include `SURPLUS_API_KEY` |
| `OPENAI_API_BASE_URL` | `https://api.surplusintelligence.ai/v1` |
| `OPENAI_API_KEY` | Set to the name `SURPLUS_API_KEY` when the connection uses secret mode |
| `DEFAULT_MODELS` | Initial chat model. The deploy default is `deepseek-v4-flash-0731` |
| `IMAGE_GENERATION_MODEL` | Initial image model. The deploy default is `venice-z-image-turbo` |
| `WEBUI_URL` | `http://localhost:7860` locally. The deploy helper sets the Space origin |
| `DATABASE_URL` | Supabase Session pooler URL for the Space. Local Compose uses the volume's SQLite database |

Image generation and image editing each have their own base URL, key source, and model. Details and live compatibility notes are in [Surplus setup](main/docs/surplus.md).

---

## Storage

**Local.** Compose mounts `webui-data` at `/app/backend/data`. Accounts, chats, settings, uploads, and generated images survive `docker compose up --build` and container recreation. Stop the service before taking a backup. Restore both the database and the files from the same point in time. The procedure is in [deployment and recovery](main/docs/deployment.md).

**Space.** The Space disk is ephemeral. Chats, the owner account, and settings use Supabase PostgreSQL. Uploaded and generated files use the private bucket `kaushikpaul/open-webui-surplus-data`, mounted read-write at `/app/backend/data`. The active database stays on Postgres; the bucket is for files. Keep a single Uvicorn worker.

---

## Deployment

Deploy only with `main/scripts/deploy_space.py`. The Hugging Face account must already be logged in (`hf auth login` or `HF_TOKEN`), and the Python environment needs `huggingface_hub` and `python-dotenv`.

The helper creates a **private** Docker Space, uploads Git-visible files plus `main/frontend-dist`, and copies owner settings from `.env` into Space Secrets and Variables. Logs show setting names only. The `.env` file stays local.

Default Space id: `kaushikpaul/Open-WebUI-Surplus`, or `{hf-username}/Open-WebUI-Surplus`. Override it with `--repo-id` or `HF_SPACE_ID`. The runtime origin for that default id is <https://kaushikpaul-open-webui-surplus.hf.space>.

```sh
python3 main/scripts/deploy_space.py --dry-run
python3 main/scripts/deploy_space.py --attach-bucket
python3 main/scripts/deploy_space.py --update --repo-id kaushikpaul/Open-WebUI-Surplus
```

| Flag | Effect |
|---|---|
| `--dry-run` | Lists the upload set and setting names. Does not build the frontend or change the Space |
| `--attach-bucket` | Writes `DATABASE_URL` from the local Supabase password and mounts the private bucket |
| `--update` | Uploads code to an existing Space. Leaves Secrets, Variables, hardware, visibility, and the bucket mount as they are |
| `--skip-frontend-build` | Reuses the current `main/frontend-dist`. Use it for backend or documentation changes |
| `--skip-env` | Uploads code and does not read `.env` |

`--update` implies `--skip-env`. Rebuild the frontend for UI changes; `--skip-frontend-build` is for backend or documentation changes. A fresh database receives the Surplus chat and image defaults from the helper, including `deepseek-v4-flash-0731` and `venice-z-image-turbo`.

For the cross-site Hugging Face frame, the helper sets `WEBUI_URL` to the Space origin, `WEBUI_AUTH_COOKIE_SECURE=true`, and `WEBUI_AUTH_COOKIE_SAME_SITE=none`. Private generated images are also loaded with the bearer token.

---

## Password recovery

While signed in, change the password in the native account settings. `WEBUI_ADMIN_PASSWORD` applies only when the owner account is first created.

To reset a local account offline, stop the service, back up the data volume, then:

```sh
docker compose run --rm --entrypoint python webui /app/scripts/reset_owner_password.py
```

Set a new random `WEBUI_SECRET_KEY` afterward and recreate the container. Signing-key rotation invalidates existing JWTs. Revoking those tokens on logout itself requires Redis. Clear the remembered browser password after recovery.

---

## Further reading

- [Deployment, persistence, and recovery](main/docs/deployment.md)
- [Surplus setup and compatibility](main/docs/surplus.md)
- [Customizations and upstream upgrades](main/docs/customization.md)
- [Request-path audit](main/docs/request-path-audit.md)
- [Verification results](main/docs/verification.md)
- [Maintainer rules](AGENTS.md)

---

## License

This project is available under the [MIT License](LICENCE).

Open WebUI v0.11.3 in `main/upstream/` remains under its own [license](main/upstream/LICENSE). Its [license notice](main/upstream/LICENSE_NOTICE), branding, and copyright notices are retained.
