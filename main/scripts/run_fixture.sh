#!/bin/sh
# Isolated full-app fixture. Never loads the user's .env or calls Surplus.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
FIXTURE_ENV=$(mktemp)
trap 'rm -f "$FIXTURE_ENV"' EXIT
cat > "$FIXTURE_ENV" <<'ENV'
WEBUI_ADMIN_EMAIL=owner@example.com
WEBUI_ADMIN_PASSWORD=fixture-password-123
WEBUI_SECRET_KEY=fixture-signing-key-01234567890123456789
SURPLUS_API_KEY=fixture-canary
PROVIDER_SECRET_NAMES=SURPLUS_API_KEY
ALLOW_HTTP_TEST_PROVIDERS=true
WEBUI_AUTH=true
OPENAI_API_BASE_URL=http://mock-provider:8000/v1
OPENAI_API_KEY=SURPLUS_API_KEY
OPENAI_API_CONFIGS={"0":{"key_source":"secret","enable":true}}
ENABLE_OLLAMA_API=false
IMAGES_OPENAI_KEY_SOURCE=secret
IMAGES_OPENAI_COMPATIBILITY=surplus
IMAGES_EDIT_OPENAI_KEY_SOURCE=secret
IMAGES_EDIT_OPENAI_COMPATIBILITY=surplus
RAG_EMBEDDING_ENGINE=openai
OFFLINE_MODE=true
HF_HUB_OFFLINE=1
ENV
docker network inspect owui-hf-test >/dev/null 2>&1 || docker network create owui-hf-test
docker volume create owui-hf-test-data >/dev/null
docker run -d --name mock-provider --network owui-hf-test --env-file "$FIXTURE_ENV" \
    -v "$ROOT/main/tests/mock_provider.py:/app/mock_provider.py:ro" \
    --entrypoint python owui-hf:local /app/mock_provider.py
docker run -d --name owui-hf-test --network owui-hf-test -p 127.0.0.1:17860:7860 \
    --env-file "$FIXTURE_ENV" -v owui-hf-test-data:/app/backend/data owui-hf:local
printf '%s\n' 'Fixture starting at http://127.0.0.1:17860. Wait for /health, then run integration_check.py, e2e/browser_check.py, security_check.py (last).'
printf '%s\n' 'Cleanup only this fixture: docker rm -f owui-hf-test mock-provider; docker network rm owui-hf-test. Keep the test volume for persistence checks.'
