"""Exercise download behavior without external DNS or real CDN calls."""
import base64
import io
import socket
from unittest.mock import patch
import pytest
from PIL import Image
from open_webui.utils import surplus_images as images

class Content:
    def __init__(self,data):self.data=data
    async def iter_chunked(self,size):
        for i in range(0,len(self.data),size):yield self.data[i:i+size]
class Response:
    def __init__(self,status=200,data=b'',headers=None):self.status=status;self.content=Content(data);self.headers=headers or {}
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    def raise_for_status(self):assert self.status==200
class Session:
    calls=[];responses=[]
    def __init__(self,**kwargs):self.kwargs=kwargs
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        assert 'headers' not in kwargs and kwargs['allow_redirects'] is False
        return self.responses.pop(0)

@pytest.mark.asyncio
async def test_public_redirect_and_no_credentials(monkeypatch):
    output=io.BytesIO();Image.new('RGB',(4,4)).save(output,format='PNG');png=output.getvalue()
    Session.calls=[];Session.responses=[Response(302,headers={'Location':'https://cdn.example/image'}),Response(data=png)]
    monkeypatch.setattr(images.aiohttp,'TCPConnector',lambda **kwargs:None)
    monkeypatch.setattr(images.aiohttp,'ClientSession',Session)
    assert await images.download_image('https://provider.example/image')==(png,'image/png')
    assert len(Session.calls)==2

@pytest.mark.asyncio
async def test_redirect_to_private_rejected_before_second_fetch(monkeypatch):
    Session.calls=[];Session.responses=[Response(302,headers={'Location':'https://127.0.0.1/secret'})]
    monkeypatch.setattr(images.aiohttp,'TCPConnector',lambda **kwargs:None)
    monkeypatch.setattr(images.aiohttp,'ClientSession',Session)
    with pytest.raises(ValueError):await images.download_image('https://cdn.example/image')
    assert len(Session.calls)==1

@pytest.mark.asyncio
async def test_mixed_dns_answers_fail(monkeypatch):
    import asyncio
    async def lookup(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]
    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',lookup)
    with pytest.raises(ValueError):await images.PublicResolver().resolve('cdn.example',443)

@pytest.mark.asyncio
async def test_bounded_body():
    with pytest.raises(ValueError):await images.bounded_read(Response(data=b'x'*65537),65536)
