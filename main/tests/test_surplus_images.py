import base64
import io
from contextlib import asynccontextmanager
import pytest
from aiohttp import web
from PIL import Image
from fastapi import HTTPException
from open_webui.utils import surplus_images as images

@pytest.fixture
def png():
    output = io.BytesIO()
    Image.new('RGB', (4, 4), '#112233').save(output, format='PNG')
    return output.getvalue()

@asynccontextmanager
async def provider(handler):
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try: yield f'http://127.0.0.1:{port}/v1'
    finally: await runner.cleanup()

@pytest.mark.asyncio
async def test_generation_and_json_edit(png, monkeypatch):
    monkeypatch.setenv('ALLOW_HTTP_TEST_PROVIDERS','true')
    monkeypatch.setenv('SURPLUS_API_KEY','canary-secret')
    monkeypatch.setenv('PROVIDER_SECRET_NAMES','SURPLUS_API_KEY')
    requests = []
    async def handler(request):
        requests.append((request.path, request.headers['Authorization'], await request.json()))
        return web.json_response({'data':[{'b64_json':base64.b64encode(png).decode()}]})
    async with provider(handler) as url:
        body = images.image_payload('fixture-image','a blue square',1,'1024x1024', {'quality':'low'})
        assert await images.request_images(url,'SURPLUS_API_KEY','secret',body) == [(png,'image/png')]
        source = 'data:image/png;base64,' + base64.b64encode(png).decode()
        body = images.image_payload('fixture-edit','make it green',sources=[source,source])
        assert await images.request_images(url,'SURPLUS_API_KEY','secret',body,edit=True) == [(png,'image/png')]
    assert requests[0][0] == '/v1/images/generations'
    assert requests[1][0] == '/v1/images/edits'
    assert requests[1][1] == 'Bearer canary-secret'
    assert requests[1][2]['input_images'] == [source,source]
    assert 'image' not in requests[1][2]

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,402,404,429,500])
async def test_error_echo_is_never_returned(status, monkeypatch):
    monkeypatch.setenv('ALLOW_HTTP_TEST_PROVIDERS','true')
    async def handler(request): return web.json_response({'error':request.headers.get('Authorization')},status=status)
    async with provider(handler) as url:
        with pytest.raises(HTTPException) as error:
            await images.request_images(url,'canary-secret','literal',images.image_payload('fixture','x'))
        assert 'canary' not in error.value.detail
        assert error.value.status_code == status

@pytest.mark.parametrize('params',[{'mask':'x'}, {'model':'override'}, {'resolution':'8K'}, {'response_format':'raw'}, {'quality':{}}])
def test_payload_validation(params):
    with pytest.raises(HTTPException): images.image_payload('fixture','x',params=params)

@pytest.mark.asyncio
@pytest.mark.parametrize('url',['http://cdn.example/image.png','https://127.0.0.1/image','https://169.254.169.254/image','https://user:pass@cdn.example/image'])
async def test_unsafe_downloads(url):
    with pytest.raises(ValueError): await images.download_image(url)

def test_invalid_and_oversize_images(png,monkeypatch):
    for value in ['not base64!',base64.b64encode(b'not an image').decode()]:
        with pytest.raises(Exception): images.decode_image(value)
    monkeypatch.setattr(images,'MAX_IMAGE_BYTES',4)
    with pytest.raises(ValueError): images.validate_image(png)

def test_capability_metadata():
    m={'id':'arbitrary','architecture':{'input_modalities':['text','image'],'output_modalities':['image']}}
    assert images.image_capable(m) and images.image_capable(m,edit=True)
    assert not images.image_capable({'id':'image-name-is-not-proof'})
