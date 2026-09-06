"""Deploy this Docker Space to Hugging Face without uploading ignored or secret files.

Mirrors the Manga-Translator helper: Git-visible files only, plus extra ignore
patterns. Reads root .env with dotenv semantics and never prints values.
Requires huggingface_hub (provided by the `hf` CLI environment).
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.utils import filter_repo_objects

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / '.env'
FRONTEND_DIST = PROJECT_ROOT / 'main' / 'frontend-dist'
DEFAULT_SPACE_NAME = 'Open-WebUI-Surplus'
REFERENCE_NAME = 'SURPLUS_API_KEY'
FRONTEND_IMAGE = 'owui-hf-frontend:local'

DEPLOY_IGNORE_PATTERNS = [
    '.env',
    '.env.*',
    '**/.env',
    '**/.env.*',
    '.git',
    '.git/**',
    '.idea/**',
    '.venv/**',
    'venv/**',
    '**/.venv/**',
    '**/__pycache__/**',
    '**/*.pyc',
    '**/node_modules/**',
    '**/.svelte-kit/**',
    '**/backend/data/**',
    '**/.pytest_cache/**',
    'main/.local-data/**',
    'backups/**',
    'sdk_metadata.txt',
    '.codex/**',
    '.agents/**',
]

SECRET_KEYS = {
    'WEBUI_ADMIN_PASSWORD',
    'WEBUI_SECRET_KEY',
    'SURPLUS_API_KEY',
    'DATABASE_URL',
    'S3_ACCESS_KEY_ID',
    'S3_SECRET_ACCESS_KEY',
}
REFERENCE_KEYS = {
    'OPENAI_API_KEY',
    'IMAGES_OPENAI_API_KEY',
    'IMAGES_EDIT_OPENAI_API_KEY',
}
SKIP_FROM_ENV = {
    'WEBUI_URL',
    'WEBUI_AUTH_COOKIE_SECURE',
    'ALLOW_HTTP_TEST_PROVIDERS',
    'HF_TOKEN',
    'HUGGING_FACE_HUB_TOKEN',
}
REQUIRED_STARTUP = ('WEBUI_ADMIN_EMAIL', 'WEBUI_ADMIN_PASSWORD', 'WEBUI_SECRET_KEY')


def frontend_dist_files() -> list[str]:
    if not (FRONTEND_DIST / 'index.html').is_file():
        return []
    files: list[str] = []
    for path in FRONTEND_DIST.rglob('*'):
        if path.is_file() and path.name != '.gitkeep':
            files.append(str(path.relative_to(PROJECT_ROOT)))
    return files


def build_frontend_dist() -> None:
    print('Building frontend locally so the Hugging Face builder can skip Vite')
    existing = subprocess.run(['docker', 'image', 'inspect', FRONTEND_IMAGE], capture_output=True)
    if existing.returncode != 0:
        subprocess.run(
            [
                'docker', 'run', '--rm', '--name', 'owui-hf-frontend-build',
                '-v', f'{PROJECT_ROOT / "main/upstream"}:/src:ro',
                '-v', f'{FRONTEND_DIST}:/out',
                '-e', 'CYPRESS_INSTALL_BINARY=0',
                '-e', 'NODE_OPTIONS=--max-old-space-size=4096',
                '-w', '/app',
                'node:22.19.0-bookworm-slim',
                'sh', '-c',
                'cp -a /src/. /app/ && npm ci --force && npm run build && cp -a /app/build/. /out/',
            ],
            check=True,
        )
    else:
        cid = subprocess.check_output(['docker', 'create', FRONTEND_IMAGE], text=True).strip()
        try:
            FRONTEND_DIST.mkdir(parents=True, exist_ok=True)
            for path in FRONTEND_DIST.rglob('*'):
                if path.is_file() and path.name != '.gitkeep':
                    path.unlink()
            subprocess.run(['docker', 'cp', f'{cid}:/app/build/.', str(FRONTEND_DIST)], check=True)
        finally:
            subprocess.run(['docker', 'rm', cid], check=True, stdout=subprocess.DEVNULL)
    if not (FRONTEND_DIST / 'index.html').is_file():
        raise SystemExit('Frontend build did not produce main/frontend-dist/index.html')


def git_visible_files() -> list[str]:
    result = subprocess.run(
        ['git', '-C', str(PROJECT_ROOT), 'ls-files', '--cached', '--others', '--exclude-standard'],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key.startswith('export '):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped.startswith('replace-')


def is_secret_key(name: str) -> bool:
    if name in REFERENCE_KEYS:
        return False
    if name in SECRET_KEYS:
        return True
    upper = name.upper()
    return any(token in upper for token in ('PASSWORD', 'SECRET', 'TOKEN', 'ACCESS_KEY'))


def space_runtime_origin(space_id: str) -> str:
    user, name = space_id.split('/', 1)
    slug = f'{user}-{name}'.lower().replace('_', '-')
    return f'https://{slug}.hf.space'


def classify_env(env: dict[str, str], space_id: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    secrets: dict[str, str] = {}
    variables: dict[str, str] = {}
    notes: list[str] = []
    for name, value in env.items():
        if name in SKIP_FROM_ENV or is_placeholder(value):
            continue
        if name in REFERENCE_KEYS and value.strip() != REFERENCE_NAME:
            secrets[name] = value
            notes.append(f'{name} is not the {REFERENCE_NAME} reference; stored as a Space secret')
            continue
        if is_secret_key(name):
            secrets[name] = value
        else:
            variables[name] = value
    variables['WEBUI_URL'] = space_runtime_origin(space_id)
    variables['WEBUI_AUTH_COOKIE_SECURE'] = 'true'
    return secrets, variables, notes


def validate_startup(env: dict[str, str]) -> None:
    missing = [name for name in REQUIRED_STARTUP if is_placeholder(env.get(name, ''))]
    if missing:
        raise SystemExit('Configure ' + ', '.join(missing) + ' in .env before deploying; values are not printed')
    if len(env.get('WEBUI_ADMIN_PASSWORD', '')) < 12:
        raise SystemExit('WEBUI_ADMIN_PASSWORD must be at least 12 characters')
    if len(env.get('WEBUI_SECRET_KEY', '')) < 32:
        raise SystemExit('WEBUI_SECRET_KEY must be at least 32 characters')
    if '@' not in env.get('WEBUI_ADMIN_EMAIL', ''):
        raise SystemExit('WEBUI_ADMIN_EMAIL must be a valid email address')


def resolve_space_id(api: HfApi, explicit: str | None) -> str:
    if explicit:
        return explicit
    env_id = os.environ.get('HF_SPACE_ID', '').strip()
    if env_id:
        return env_id
    identity = api.whoami()
    username = identity.get('name') or identity.get('user')
    if not username:
        raise SystemExit('Could not read Hugging Face username; pass --repo-id')
    return f'{username}/{DEFAULT_SPACE_NAME}'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-id', help=f'Space id, for example kaushikpaul/{DEFAULT_SPACE_NAME}')
    parser.add_argument('--hardware', default=None, help='Optional Space hardware, for example cpu-basic')
    parser.add_argument('--public', action='store_true', help='Create a public Space (default is private)')
    parser.add_argument('--skip-env', action='store_true', help='Upload code only; do not read or apply .env')
    parser.add_argument('--skip-frontend-build', action='store_true', help='Reuse existing main/frontend-dist instead of rebuilding')
    parser.add_argument('--dry-run', action='store_true', help='Print upload paths and env key names, not values')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.skip_frontend_build:
        build_frontend_dist()
    elif not args.dry_run and not (FRONTEND_DIST / 'index.html').is_file():
        raise SystemExit('main/frontend-dist/index.html is missing; run without --skip-frontend-build')
    allow_patterns = git_visible_files() + frontend_dist_files()
    upload_files = list(filter_repo_objects(allow_patterns, allow_patterns=allow_patterns, ignore_patterns=DEPLOY_IGNORE_PATTERNS))
    if any(path == '.env' or path.endswith('/.env') or Path(path).name.startswith('.env.') for path in upload_files):
        raise SystemExit('Refusing to upload an environment file')
    upload_bytes = sum((PROJECT_ROOT / path).stat().st_size for path in upload_files if (PROJECT_ROOT / path).is_file())
    print(f'Upload set: {len(upload_files)} files, {upload_bytes / (1024 * 1024):.1f} MiB')

    env: dict[str, str] = {}
    if not args.skip_env:
        env = load_env_file(ENV_PATH)
        if not env:
            raise SystemExit('Root .env is missing; copy .env.example, fill values, or pass --skip-env')
        validate_startup(env)

    api = HfApi()
    space_id = resolve_space_id(api, args.repo_id)
    secrets, variables, notes = classify_env(env, space_id) if env else ({}, {}, [])
    origin = space_runtime_origin(space_id)
    variables.setdefault('WEBUI_URL', origin)
    variables.setdefault('WEBUI_AUTH_COOKIE_SECURE', 'true')
    variables.setdefault('PROVIDER_SECRET_NAMES', REFERENCE_NAME)
    if env and is_placeholder(env.get('SURPLUS_API_KEY', '')):
        notes.append('SURPLUS_API_KEY is unset; chat/image provider calls will fail until it is added as a Space secret')
    if args.skip_env:
        notes.append('Owner secrets were not applied; add WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD, WEBUI_SECRET_KEY, and SURPLUS_API_KEY in Space settings or re-run without --skip-env')

    if args.dry_run:
        print(f'Would deploy to https://huggingface.co/spaces/{space_id}')
        print('Space secrets: ' + (', '.join(sorted(secrets)) or '(none)'))
        print('Space variables: ' + (', '.join(sorted(variables)) or '(none)'))
        for note in notes:
            print(note)
        for path in upload_files:
            print(path)
        return

    print(f'Deploying to https://huggingface.co/spaces/{space_id}')
    create_kwargs = {
        'repo_id': space_id,
        'repo_type': 'space',
        'space_sdk': 'docker',
        'exist_ok': True,
        'private': not args.public,
    }
    if args.hardware:
        create_kwargs['space_hardware'] = args.hardware
    api.create_repo(**create_kwargs)
    api.upload_folder(
        repo_id=space_id,
        repo_type='space',
        folder_path=PROJECT_ROOT,
        allow_patterns=allow_patterns,
        ignore_patterns=DEPLOY_IGNORE_PATTERNS,
        commit_message='Deploy Open WebUI Docker Space',
    )
    for key, value in secrets.items():
        api.add_space_secret(space_id, key, value)
    for key, value in variables.items():
        api.add_space_variable(space_id, key, value)
    print('Applied Space secrets: ' + (', '.join(sorted(secrets)) or '(none)'))
    print('Applied Space variables: ' + (', '.join(sorted(variables)) or '(none)'))
    for note in notes:
        print(note)
    print(f'Space page: https://huggingface.co/spaces/{space_id}')
    print(f'Runtime origin: {origin}')
    print('Space disk is ephemeral until PostgreSQL and durable file storage are configured.')


if __name__ == '__main__':
    main()
