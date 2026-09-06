"""Immutable single-owner policy, enforced before config imports and at ASGI boundary."""
import os
import time
from collections import OrderedDict, deque

POLICY = {'ui.enable_signup': False, 'ui.enable_login_form': True,
          'direct.enable': False, 'ldap.enable': False, 'oauth.enable': False,
          'oauth.enable_signup': False}


def prepare_environment():
    if os.getenv('WEBUI_AUTH', 'true').lower() != 'true':
        raise RuntimeError('Private deployment requires WEBUI_AUTH=true')
    for name in ('WEBUI_ADMIN_EMAIL', 'WEBUI_ADMIN_PASSWORD', 'WEBUI_SECRET_KEY'):
        value = os.getenv(name, '')
        if not value.strip() or value.startswith('replace-'):
            raise RuntimeError(f'Configure {name} before startup')
    if '@' not in os.environ['WEBUI_ADMIN_EMAIL'] or len(os.environ['WEBUI_ADMIN_PASSWORD']) < 12 or len(os.environ['WEBUI_SECRET_KEY']) < 32:
        raise RuntimeError('Owner email, password (12+ characters), and signing key (32+ characters) are required')
    for name, value in {'WEBUI_AUTH': 'true', 'ENABLE_SIGNUP': 'false', 'ENABLE_LOGIN_FORM': 'true',
                        'ENABLE_DIRECT_CONNECTIONS': 'false', 'ENABLE_LDAP': 'false', 'ENABLE_OAUTH': 'false',
                        'ENABLE_OAUTH_SIGNUP': 'false', 'ENABLE_PERSISTENT_CONFIG': 'true',
                        'WEBUI_AUTH_TRUSTED_EMAIL_HEADER': '', 'WEBUI_AUTH_TRUSTED_NAME_HEADER': '',
                        'WEBUI_AUTH_TRUSTED_GROUPS_HEADER': '', 'ENABLE_OPENAI_API_PASSTHROUGH': 'false',
                        'AIOHTTP_CLIENT_ALLOW_REDIRECTS': 'false'}.items():
        os.environ[name] = value


async def bootstrap_owner():
    from open_webui.models.users import Users
    from open_webui.models.config import Config
    from open_webui.utils.auth import create_admin_user
    email = os.environ['WEBUI_ADMIN_EMAIL'].strip().lower()
    await create_admin_user(email, os.environ['WEBUI_ADMIN_PASSWORD'], os.getenv('WEBUI_ADMIN_NAME', 'Owner'))
    owner = await Users.get_user_by_email(email)
    if owner is None or owner.role != 'admin' or await Users.get_num_users() != 1:
        raise RuntimeError('Private deployment requires exactly the configured owner; restore or recover the database')
    await Config.upsert(POLICY)


class LoginLimiter:
    def __init__(self):
        self.clients = OrderedDict()
        self.global_attempts = deque()

    def allow(self, host, now=None):
        now = time.monotonic() if now is None else now
        q = self.clients.setdefault(host, deque())
        self.clients.move_to_end(host)
        for entries in (q, self.global_attempts):
            while entries and entries[0] <= now - 60:
                entries.popleft()
        if len(q) >= 10 or len(self.global_attempts) >= 100:
            return False
        q.append(now)
        self.global_attempts.append(now)
        while len(self.clients) > 2048:
            self.clients.popitem(last=False)
        return True


class PrivateAccessMiddleware:
    def __init__(self, app):
        self.app = app
        self.limiter = LoginLimiter()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response, RedirectResponse
        from starlette.background import BackgroundTasks
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        from open_webui.utils.auth import get_current_user
        request = Request(scope, receive)
        path = scope['path'].rstrip('/') or '/'
        # Transport handshake is public; native socket events validate session tokens.
        public = path in ('/', '/auth', '/health', '/api/config', '/api/v1/auths/signin', '/api/v1/auths/signout', '/manifest.json', '/favicon.png', '/favicon.ico', '/robots.txt') or path.startswith(('/_app/', '/static/', '/assets/', '/ws/socket.io'))
        blocked = path in ('/api/v1/auths/signup', '/api/v1/auths/add', '/docs', '/openapi.json', '/redoc') or path.startswith(('/oauth/', '/api/v1/auths/ldap', '/s/')) or path.endswith('/share') or path.startswith('/api/v1/chats/shared/')
        if blocked:
            return await JSONResponse({'detail': 'Disabled in this private deployment'}, 403)(scope, receive, send)
        if path == '/health':
            return await JSONResponse({'status': True})(scope, receive, send)
        if path == '/api/v1/auths/signin' and not self.limiter.allow((scope.get('client') or ('unknown',))[0]):
            return await JSONResponse({'detail': 'Too many login attempts; retry in one minute'}, 429, headers={'Retry-After': '60'})(scope, receive, send)
        if not public:
            header = request.headers.get('authorization', '')
            auth = HTTPAuthorizationCredentials(scheme='Bearer', credentials=header[7:]) if header.lower().startswith('bearer ') else None
            try:
                user = await get_current_user(request, Response(), BackgroundTasks(), auth)
                if user.email.lower() != os.environ['WEBUI_ADMIN_EMAIL'].strip().lower() or user.role != 'admin':
                    raise HTTPException(403)
            except HTTPException:
                if request.method == 'GET' and 'text/html' in request.headers.get('accept', ''):
                    from urllib.parse import quote
                    return await RedirectResponse('/auth?redirect=' + quote(path, safe=''), status_code=303)(scope, receive, send)
                return await JSONResponse({'detail': 'Authentication required'}, 401)(scope, receive, send)
        return await self.app(scope, receive, send)
