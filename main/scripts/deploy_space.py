"""Deploy or update this Docker Space without uploading ignored or secret files.

Mirrors the Manga-Translator helper: Git-visible files only, plus extra ignore
patterns. Reads root .env with dotenv semantics and never prints values.
Requires huggingface_hub (provided by the `hf` CLI environment).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from huggingface_hub import HfApi, Volume
from huggingface_hub.utils import filter_repo_objects

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / '.env'
FRONTEND_DIST = PROJECT_ROOT / 'main' / 'frontend-dist'
DEFAULT_SPACE_NAME = 'Open-WebUI-Surplus'
REFERENCE_NAME = 'SURPLUS_API_KEY'
SUPABASE_POOLER_HOST = 'aws-0-ap-northeast-1.pooler.supabase.com'
SUPABASE_POOLER_USER = 'postgres.wbfkaggbcpmgaybddzxd'
SPACE_BUCKET = 'kaushikpaul/open-webui-surplus-data'
SPACE_DATA_PATH = '/app/backend/data'
SURPLUS_URL = 'https://api.surplusintelligence.ai/v1'
SPACE_DEFAULTS = {
    'OPENAI_API_BASE_URL': SURPLUS_URL,
    'OPENAI_API_KEY': REFERENCE_NAME,
    'OPENAI_API_CONFIGS': '{"0":{"key_source":"secret","auth_type":"bearer","enable":true}}',
    'PROVIDER_SECRET_NAMES': REFERENCE_NAME,
    'DEFAULT_MODELS': 'deepseek-v4-flash-0731',
    'ENABLE_OLLAMA_API': 'false',
    'ENABLE_IMAGE_GENERATION': 'true',
    'IMAGE_GENERATION_ENGINE': 'openai',
    'IMAGE_GENERATION_MODEL': 'venice-z-image-turbo',
    'IMAGE_SIZE': '512x512',
    'IMAGES_OPENAI_API_BASE_URL': SURPLUS_URL,
    'IMAGES_OPENAI_API_KEY': REFERENCE_NAME,
    'IMAGES_OPENAI_KEY_SOURCE': 'secret',
    'IMAGES_OPENAI_COMPATIBILITY': 'surplus',
    'WEBUI_AUTH_COOKIE_SAME_SITE': 'none',
}

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
    'SUPABASE_DATABASE_PASSWORD',
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


def ensure_dotenv() -> None:
    try:
        import dotenv  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            'python-dotenv is missing from this Python '
            f'({sys.executable}). Install it there, then rerun. The frontend build was not started.'
        ) from exc


def build_frontend_dist() -> None:
    print('Building frontend from current source so the Hugging Face builder can skip Vite')
    source_dir = PROJECT_ROOT / 'main/upstream'
    lockfile = source_dir / 'package-lock.json'
    installed_lock = source_dir / 'node_modules/.package-lock.json'
    use_installed = (
        (source_dir / 'node_modules/.bin/vite').is_file()
        and installed_lock.is_file()
        and installed_lock.stat().st_mtime >= lockfile.stat().st_mtime
    )
    install_step = '' if use_installed else 'npm ci --force && '
    print('Reusing installed Node dependencies' if use_installed else 'Installing Node dependencies')
    with tempfile.TemporaryDirectory(prefix='owui-frontend-build-') as build_dir:
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '--name', 'owui-hf-frontend-build',
                '-v', f'{PROJECT_ROOT / "main/upstream"}:/src:ro',
                '-v', f'{build_dir}:/out',
                '-e', 'CYPRESS_INSTALL_BINARY=0',
                '-e', 'NODE_OPTIONS=--max-old-space-size=6144',
                '-w', '/app',
                'node:22.19.0-bookworm-slim',
                'sh', '-c',
                f'cp -a /src/. /app/ && {install_step}npm run build && cp -a /app/build/. /out/ && chown -R {os.getuid()}:{os.getgid()} /out/',
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            output = '\n'.join(part for part in (result.stdout, result.stderr) if part).strip()
            tail = '\n'.join(output.splitlines()[-40:])
            if tail:
                print(tail)
            raise SystemExit(f'Frontend build failed (exit {result.returncode})')
        print('Frontend build finished')
        built = Path(build_dir)
        if not (built / 'index.html').is_file():
            raise SystemExit('Frontend build did not produce index.html')
        FRONTEND_DIST.mkdir(parents=True, exist_ok=True)
        for path in FRONTEND_DIST.iterdir():
            if path.name == '.gitkeep':
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        for path in built.iterdir():
            if path.is_dir():
                shutil.copytree(path, FRONTEND_DIST / path.name)
            else:
                shutil.copy2(path, FRONTEND_DIST / path.name)


def git_visible_files() -> list[str]:
    result = subprocess.run(
        ['git', '-C', str(PROJECT_ROOT), 'ls-files', '--cached', '--others', '--exclude-standard'],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    from dotenv import dotenv_values

    parsed = dotenv_values(path, interpolate=False)
    return {name: os.environ.get(name, value) for name, value in parsed.items() if value is not None}


def supabase_database_url(password: str) -> str:
    encoded = quote(password, safe='')
    return f'postgresql://{SUPABASE_POOLER_USER}:{encoded}@{SUPABASE_POOLER_HOST}:5432/postgres?sslmode=require'


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
    if is_placeholder(env.get('DATABASE_URL', '')) and not is_placeholder(env.get('SUPABASE_DATABASE_PASSWORD', '')):
        env = {**env, 'DATABASE_URL': supabase_database_url(env['SUPABASE_DATABASE_PASSWORD'])}
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


def validate_startup(env: dict[str, str], existing_keys: set[str] | None = None) -> None:
    existing_keys = existing_keys or set()
    missing = [name for name in REQUIRED_STARTUP if is_placeholder(env.get(name, '')) and name not in existing_keys]
    if missing:
        raise SystemExit('Configure ' + ', '.join(missing) + ' in .env or existing Space settings; values are not printed')
    password = env.get('WEBUI_ADMIN_PASSWORD', '')
    signing_key = env.get('WEBUI_SECRET_KEY', '')
    email = env.get('WEBUI_ADMIN_EMAIL', '')
    if password and len(password) < 12:
        raise SystemExit('WEBUI_ADMIN_PASSWORD must be at least 12 characters')
    if signing_key and len(signing_key) < 32:
        raise SystemExit('WEBUI_SECRET_KEY must be at least 32 characters')
    if email and '@' not in email:
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
    parser.add_argument('--update', action='store_true', help='Update an existing Space with code only; leave its settings and storage untouched')
    parser.add_argument('--attach-bucket', action='store_true', help='Attach the private data bucket; requires DATABASE_URL')
    parser.add_argument('--skip-frontend-build', action='store_true', help='Reuse main/frontend-dist for backend-only updates; frontend changes require a rebuild')
    parser.add_argument('--dry-run', action='store_true', help='Print upload paths and env key names, not values')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.update:
        if args.public or args.hardware or args.attach_bucket:
            raise SystemExit('--update cannot change visibility, hardware, or bucket mounts')
        args.skip_env = True
    if not args.skip_env:
        ensure_dotenv()
    if not args.dry_run and not args.skip_frontend_build:
        build_frontend_dist()
    elif not args.dry_run and not (FRONTEND_DIST / 'index.html').is_file():
        raise SystemExit('main/frontend-dist/index.html is missing; run without --skip-frontend-build')
    allow_patterns = git_visible_files() + frontend_dist_files()
    upload_files = list(filter_repo_objects(allow_patterns, ignore_patterns=DEPLOY_IGNORE_PATTERNS))
    if any(path == '.env' or path.endswith('/.env') or Path(path).name.startswith('.env.') for path in upload_files):
        raise SystemExit('Refusing to upload an environment file')
    upload_bytes = sum((PROJECT_ROOT / path).stat().st_size for path in upload_files if (PROJECT_ROOT / path).is_file())
    print(f'Upload set: {len(upload_files)} files, {upload_bytes / (1024 * 1024):.1f} MiB')

    api = HfApi()
    space_id = resolve_space_id(api, args.repo_id)
    env: dict[str, str] = {}
    existing_keys: set[str] = set()
    if not args.skip_env or args.attach_bucket:
        try:
            existing_keys = set(api.get_space_secrets(space_id)) | set(api.get_space_variables(space_id))
        except Exception:
            pass  # A new Space has no existing settings.
    if not args.skip_env:
        env = load_env_file(ENV_PATH)
        if not env:
            raise SystemExit('Root .env is missing; copy .env.example, fill values, or pass --skip-env')
        validate_startup(env, existing_keys)

    secrets, variables, notes = classify_env(env, space_id) if env else ({}, {}, [])
    origin = space_runtime_origin(space_id)
    if env:
        for name, value in SPACE_DEFAULTS.items():
            variables.setdefault(name, value)
    if not args.skip_env:
        variables.setdefault('WEBUI_URL', origin)
        variables.setdefault('WEBUI_AUTH_COOKIE_SECURE', 'true')
        variables.setdefault('PROVIDER_SECRET_NAMES', REFERENCE_NAME)
    if args.attach_bucket and 'DATABASE_URL' not in secrets and 'DATABASE_URL' not in existing_keys:
        raise SystemExit('A DATABASE_URL Space Secret is required before attaching the bucket')
    if env and is_placeholder(env.get('SURPLUS_API_KEY', '')):
        notes.append('SURPLUS_API_KEY is unset; chat/image provider calls will fail until it is added as a Space secret')
    if args.skip_env and not args.update:
        notes.append('Space secrets and variables will not be changed')

    if args.dry_run:
        print(f'Would deploy to https://huggingface.co/spaces/{space_id}')
        print('Space secrets: ' + (', '.join(sorted(secrets)) or '(none)'))
        print('Space variables: ' + (', '.join(sorted(variables)) or '(none)'))
        if args.attach_bucket:
            print(f'Would mount private bucket {SPACE_BUCKET} at {SPACE_DATA_PATH}')
        for note in notes:
            print(note)
        for path in upload_files:
            print(path)
        return

    print(f'Deploying to https://huggingface.co/spaces/{space_id}')
    if args.update:
        api.repo_info(repo_id=space_id, repo_type='space')
    else:
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
    for key, value in secrets.items():
        api.add_space_secret(space_id, key, value)
    for key, value in variables.items():
        api.add_space_variable(space_id, key, value)
    if args.attach_bucket:
        api.set_space_volumes(space_id, [Volume(type='bucket', source=SPACE_BUCKET, mount_path=SPACE_DATA_PATH)])
    # Stage only reviewed paths. Passing every path as an allow pattern to
    # upload_folder causes quadratic matching against the full workspace.
    with tempfile.TemporaryDirectory(prefix='owui-space-upload-') as staging_dir:
        staging_root = Path(staging_dir)
        for relative in upload_files:
            target = staging_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / relative, target)
        api.upload_folder(
            repo_id=space_id,
            repo_type='space',
            folder_path=staging_root,
            commit_message='Deploy Open WebUI Docker Space',
        )
    print('Applied Space secrets: ' + (', '.join(sorted(secrets)) or '(none)'))
    print('Applied Space variables: ' + (', '.join(sorted(variables)) or '(none)'))
    for note in notes:
        print(note)
    print(f'Space page: https://huggingface.co/spaces/{space_id}')
    print(f'Runtime origin: {origin}')
    print('Verify PostgreSQL, mounted file storage, and a Space restart before claiming durability.')


if __name__ == '__main__':
    main()
