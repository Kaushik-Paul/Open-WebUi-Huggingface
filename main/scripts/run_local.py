"""Native development runner; Docker Compose is the supported reproducible setup."""
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env', override=False)
os.environ.setdefault('DATA_DIR', str(ROOT / 'main/.local-data'))
sys.path.insert(0, str(ROOT / 'main/upstream/backend'))
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('open_webui.main:app', host='0.0.0.0', port=7860, workers=1, proxy_headers=False)
