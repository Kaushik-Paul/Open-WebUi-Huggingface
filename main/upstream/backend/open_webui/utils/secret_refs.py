"""Request-local provider credentials. Never persist the return value."""
import os
import re
from urllib.parse import urlsplit
from fastapi import HTTPException


def resolve_secret(value, source='literal', allowlist=None, *, status=503):
    if source not in ('literal', 'secret'):
        raise HTTPException(status, 'Invalid credential source')
    value = value or ''
    if source == 'secret':
        name = value.strip()
        allowed = {v.strip() for v in (allowlist if allowlist is not None else os.getenv('PROVIDER_SECRET_NAMES', '')).split(',')}
        # This deployment supports exactly the provider secret requested by its owner.
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', name) or name != 'SURPLUS_API_KEY' or name not in allowed:
            raise HTTPException(status, 'Provider secret unavailable; allow SURPLUS_API_KEY on the server')
        value = os.getenv(name, '')
        if not value.strip():
            raise HTTPException(status, 'Provider secret unavailable; configure SURPLUS_API_KEY on the server')
    if '\r' in value or '\n' in value:
        raise HTTPException(status, 'Invalid provider credential')
    return value


def validate_destination(url, *, status=503):
    p = urlsplit(url)
    test_http = os.getenv('ALLOW_HTTP_TEST_PROVIDERS') == 'true' and p.hostname in ('localhost', '127.0.0.1', 'mock-provider')
    if (p.scheme != 'https' and not test_http) or not p.hostname or p.username or p.password or p.fragment or p.query:
        raise HTTPException(status, 'Provider base URL must use HTTPS without credentials, query, or fragment')


def connection_credential(url, key, config=None, *, status=503):
    config = config or {}
    source = config.get('key_source', 'literal')
    validate_destination(url, status=status)
    if config.get('auth_type') == 'none' and not key:
        return ''
    if source == 'secret':
        if config.get('auth_type') not in (None, 'bearer'):
            raise HTTPException(status, 'Secret names require API key authentication')
        if any(h.lower() in ('authorization', 'api-key', 'x-api-key') for h in (config.get('headers') or {})):
            raise HTTPException(status, 'Custom authentication headers conflict with Secret name mode')
    return resolve_secret(key, source, status=status)


def provider_error(status):
    return {401: 'Provider rejected the API key', 403: 'Provider access denied',
            402: 'Provider balance is insufficient', 404: 'Model or available seller not found',
            429: 'Provider rate limit reached', 504: 'Provider timed out; check before retrying'}.get(status, 'Provider request failed; check model availability and settings')
