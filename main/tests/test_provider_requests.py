import asyncio
import pytest
from aiohttp import web
from open_webui.utils.provider_http import ProviderSession
from test_surplus_images import provider

@pytest.mark.asyncio
async def test_streaming_tool_and_usage_chunks():
    wire = b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\\"x\\\":1}"}}]}}]}\n\ndata: {"choices":[],"usage":{"total_tokens":7}}\n\ndata: [DONE]\n\n'
    async def handler(request):
        body=await request.json()
        assert body['messages'][0]['content'][0]['type']=='image_url'
        return web.Response(body=wire,content_type='text/event-stream')
    async with provider(handler) as url:
        async with ProviderSession() as session:
            async with session.post(url+'/chat/completions',json={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,fixture'}}]}]}) as response:
                assert await response.read() == wire

@pytest.mark.asyncio
async def test_redirect_not_followed_and_errors_sanitized():
    paths=[]
    async def handler(request):
        paths.append(request.path)
        return web.Response(status=302,headers={'Location':'/stolen'},text='Bearer canary-secret')
    async with provider(handler) as url:
        async with ProviderSession() as session:
            async with session.get(url+'/models',headers={'Authorization':'Bearer canary-secret'}) as response:
                assert response.status==302
                assert 'canary-secret' not in await response.text()
                assert 'canary-secret' not in str(await response.json())
    assert paths==['/v1/models']
