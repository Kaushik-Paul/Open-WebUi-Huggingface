#!/bin/sh
set -eu
python -c 'from open_webui.utils.private_deployment import prepare_environment; prepare_environment()'
mkdir -p "${DATA_DIR:-/app/backend/data}/cache"
exec python -m uvicorn open_webui.main:app --host 0.0.0.0 --port 7860 --workers 1 --no-proxy-headers
