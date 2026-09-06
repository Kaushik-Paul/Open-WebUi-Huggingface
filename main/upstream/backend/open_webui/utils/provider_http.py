"""Provider transport: no redirects, no provider error bodies in responses/logs."""
import aiohttp
from open_webui.utils.secret_refs import provider_error

class ProviderResponse(aiohttp.ClientResponse):
    async def json(self, *args, **kwargs):
        if self.status >= 300:
            return {'error': {'message': provider_error(self.status), 'code': self.status}}
        return await super().json(*args, **kwargs)

    async def text(self, *args, **kwargs):
        if self.status >= 300:
            import json
            return json.dumps({'error': {'message': provider_error(self.status), 'code': self.status}})
        return await super().text(*args, **kwargs)

    def raise_for_status(self):
        if self.status >= 300:
            self.release()
            raise aiohttp.ClientResponseError(self.request_info, (), status=self.status,
                                             message=provider_error(self.status))


class ProviderSession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        kwargs['response_class'] = ProviderResponse
        super().__init__(*args, **kwargs)

    async def _request(self, method, url, **kwargs):
        kwargs['allow_redirects'] = False
        kwargs['ssl'] = True
        return await super()._request(method, url, **kwargs)

_provider_session = None
async def get_provider_session():
    global _provider_session
    if _provider_session is None or _provider_session.closed:
        from open_webui.utils.session_pool import get_client_timeout
        _provider_session = ProviderSession(timeout=get_client_timeout(), trust_env=False)
    return _provider_session

async def close_provider_session():
    if _provider_session is not None:
        await _provider_session.close()
