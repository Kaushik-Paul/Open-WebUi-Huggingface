# Deployment, persistence, and recovery

## Runtime contract

The root Dockerfile copies the locally built Svelte frontend and runs only the vendored Python backend. Frontend builds use Node 22.19.0; the runtime uses Python 3.11.13, upstream requirements, CPU Torch, UID/GID 1000, port 7860, and one Uvicorn worker. No Ollama or CUDA service is included. `main/scripts/entrypoint.sh` validates configuration and execs the server. Migrations and the native admin bootstrap finish before traffic is accepted. An existing database must contain exactly the configured owner with the admin role.

Authentication, password login, disabled signup, disabled LDAP/OAuth/trusted headers, and disabled Direct Connections are deployment policy. Persisted settings/API writes cannot relax that policy. Unrelated settings remain persistent. The reverse proxy's forwarded identity/IP headers are not trusted; the login limiter also has a global bound. Use a stable signing secret. Never pass real secrets as Docker build arguments.

`SURPLUS_API_KEY` is the only supported environment credential reference. It must also appear in `PROVIDER_SECRET_NAMES`. Other providers can use explicit literal keys. Source metadata is stored separately; strings are never guessed to be secret references. Restart/recreate the process after rotating an injected secret; editing `.env` does not mutate a running environment.

## Local storage

Compose injects the entire root `.env` and mounts `webui-data` at `/app/backend/data`. SQLite, uploads, caches, and generated image files survive recreation. Back up the volume while the service is stopped. Do not delete the volume on normal shutdown.

```sh
docker compose stop
mkdir -p backups
# Replace VOLUME with the actual name shown by docker volume ls.
docker run --rm -v VOLUME:/source:ro -v "$PWD/backups:/backup" alpine:3.22 tar czf /backup/webui-data.tar.gz -C /source .
docker compose start
```

Backups contain private chats and configuration; restrict access. Test restoration into a separate volume and a separate port before relying on the backup. Restore both the database and uploads from a consistent point in time.

## Durable Spaces configuration

The Space container disk is ephemeral. Chats, owner settings, and file metadata belong in PostgreSQL; uploaded and generated image bytes belong in durable file storage. A private Hugging Face bucket named `kaushikpaul/open-webui-surplus-data` was created for this project and is mounted on the live Space at `/app/backend/data`. Do not place the active SQLite file on a bucket mount: SQLite warns that network filesystem sync and locking can corrupt a database. [Hugging Face bucket volumes](https://huggingface.co/docs/hub/spaces-storage) and [SQLite's network filesystem guidance](https://www.sqlite.org/useovernet.html) explain the tradeoff.

For this one-worker Space, use the Supabase **Session pooler** connection string on port 5432. The deployment helper sets it as a Space Secret named `DATABASE_URL` from the local `SUPABASE_DATABASE_PASSWORD`, with an encoded password and `sslmode=require` in the URL. Keep the URL out of Git, logs, and chat. Supabase documents the pooler URL and SSL setting in its [connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres). Preserve the existing `WEBUI_SECRET_KEY` and owner email/password Secrets when moving to PostgreSQL.

The private bucket is attached as a **read-write** Space volume at `/app/backend/data`. This uses Open WebUI's existing upload path without S3 access keys. The default `DATA_DIR` and UID 1000 must be able to write there. Keep one app worker. Verify startup migrations, owner login, chat save/reload, image generation, file download, and a Space restart before calling it durable.

The owner confirmed the previous Space had no data to retain before the switch. Its SQLite database and uploads were on ephemeral disk and were not migrated. For future storage changes, back up PostgreSQL and bucket files from a consistent point in time.

A fresh deployment needs the Surplus chat and image variables from root `.env.example`, including `PROVIDER_SECRET_NAMES`, `OPENAI_API_CONFIGS`, `DEFAULT_MODELS`, the independent image source/key/model settings, and `ENABLE_IMAGE_GENERATION=true`. Set `WEBUI_URL` to the `.hf.space` origin, `WEBUI_AUTH_COOKIE_SECURE=true`, and `WEBUI_AUTH_COOKIE_SAME_SITE=none` for the cross-site Hugging Face iframe. The frontend also uses bearer-authenticated fetches for private generated images, since browser policies may still block third-party cookies.

`main/scripts/deploy_space.py` remains the sole code upload path. It builds the frontend locally, uploads Git-visible files plus `main/frontend-dist`, and reads `.env` with `python-dotenv` without printing values. A partial `.env` can supply `SURPLUS_API_KEY` and `SUPABASE_DATABASE_PASSWORD` while the existing owner Secrets remain in Space settings. The helper assembles the Supabase URL with an encoded password and `sslmode=require`; `--attach-bucket` mounts the private bucket once that database Secret is available. Its safe Surplus defaults select `deepseek-v4-flash-0731` and `venice-z-image-turbo` on a fresh database. The owner confirmed no previous Space data needed preservation before this deployment. The script does not provision PostgreSQL or paid hardware.

For routine updates, run `/home/kaushik/.hf-cli/venv/bin/python main/scripts/deploy_space.py --update --repo-id kaushikpaul/Open-WebUI-Surplus` from the repository root. This verifies that the Space exists, rebuilds the frontend from current source, and uploads the reviewed files without reading `.env` or modifying Space settings or bucket mounts. For backend-only changes, add `--skip-frontend-build` to reuse the current frontend build. Run with `--dry-run` first to inspect the upload list without changing the Space. The frontend build prints a short status line. Vite's file list and Svelte warnings stay hidden unless the build fails, in which case the end of that log is printed.

## Password recovery and sessions

Changing `WEBUI_ADMIN_PASSWORD` only changes first-install provisioning; it does not reset an existing account. While logged in, use native Account password settings. Offline recovery:

```sh
docker compose stop webui
# Back up the database and uploads first.
docker compose run --rm --entrypoint python webui /app/scripts/reset_owner_password.py
```

Then update `WEBUI_SECRET_KEY` to a new random value and recreate the service. Signing-key rotation invalidates all old JWTs. The pinned native password change/logout token revocation requires Redis; without Redis, already issued JWTs remain valid until expiry or signing-key rotation. Revoke any separately created native API keys independently. Clear remembered browser credentials after recovery. Normal password changes clear this browser's remembered record automatically.

Back up before upgrades. Migrations may make data incompatible with old code; rollback requires the matching database/upload backup, not just an old image tag. Keep the signing key stable for routine restarts.
