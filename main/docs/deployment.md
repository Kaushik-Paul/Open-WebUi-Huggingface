# Deployment, persistence, and recovery

## Runtime contract

The root Dockerfile compiles the vendored Svelte frontend and runs only the vendored Python backend. It uses Node 22.19.0, Python 3.11.13, upstream package-lock/requirements, CPU Torch, UID/GID 1000, port 7860, and one Uvicorn worker. No Ollama or CUDA service is included. `main/scripts/entrypoint.sh` validates configuration and execs the server. Migrations and the native admin bootstrap finish before traffic is accepted. An existing database must contain exactly the configured owner with the admin role.

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

Space container storage is ephemeral. Current Hugging Face documentation describes attached bucket volumes; do not assume a paid subscription supplies a POSIX filesystem suitable for SQLite. See [official storage guidance](https://huggingface.co/docs/hub/spaces-storage) and [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker).

Use `DATABASE_URL` for an external PostgreSQL database and upstream S3 storage for uploads/generated images:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
STORAGE_PROVIDER=s3
S3_BUCKET_NAME=your-private-bucket
S3_REGION_NAME=your-region
S3_ENDPOINT_URL=https://your-s3-compatible-endpoint
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_KEY_PREFIX=open-webui/
```

Supply credential-bearing values through Space Secrets, require TLS according to the database provider's connection instructions, and keep the bucket private. The native authenticated file-content API retrieves stored files; do not publish private uploads to support edits. External PostgreSQL alone does not preserve image bytes. Bucket/FUSE mounts are not accepted SQLite storage unless locking/atomic writes are explicitly verified. Ephemeral SQLite is demo mode only.

Set `WEBUI_URL=https://YOUR-SPACE.hf.space` and `WEBUI_AUTH_COOKIE_SECURE=true`. Test the actual origin's cookies/localStorage, SSE through the Space proxy, Socket.IO reconnect, and UID permissions. `main/scripts/deploy_space.py` creates or updates the Docker Space, builds the frontend locally, uploads Git-visible files plus `main/frontend-dist`, and applies `.env` as Secrets/Variables without printing values. Hugging Face `cpu-basic` builders OOM on the in-cluster Vite build; the uploaded dist skips that step. The script does not provision PostgreSQL, object storage, or paid hardware. Space disk remains ephemeral until those are configured.

## Password recovery and sessions

Changing `WEBUI_ADMIN_PASSWORD` only changes first-install provisioning; it does not reset an existing account. While logged in, use native Account password settings. Offline recovery:

```sh
docker compose stop webui
# Back up the database and uploads first.
docker compose run --rm --entrypoint python webui /app/scripts/reset_owner_password.py
```

Then update `WEBUI_SECRET_KEY` to a new random value and recreate the service. Signing-key rotation invalidates all old JWTs. The pinned native password change/logout token revocation requires Redis; without Redis, already issued JWTs remain valid until expiry or signing-key rotation. Revoke any separately created native API keys independently. Clear remembered browser credentials after recovery. Normal password changes clear this browser's remembered record automatically.

Back up before upgrades. Migrations may make data incompatible with old code; rollback requires the matching database/upload backup, not just an old image tag. Keep the signing key stable for routine restarts.
