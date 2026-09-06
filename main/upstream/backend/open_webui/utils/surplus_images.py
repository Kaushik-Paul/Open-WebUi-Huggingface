"""Surplus JSON images and bounded, unauthenticated result downloads."""
import asyncio
import base64
import binascii
import io
import ipaddress
import os
import re
import socket
from urllib.parse import urlsplit, urljoin

import aiohttp
from fastapi import HTTPException
from PIL import Image
from open_webui.utils.secret_refs import connection_credential, provider_error
from open_webui.utils.provider_http import ProviderSession

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_JSON_BYTES = 80 * 1024 * 1024

class PublicResolver(aiohttp.abc.AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        records = await asyncio.get_running_loop().getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        result = []
        for fam, _, proto, _, address in records:
            if not ipaddress.ip_address(address[0]).is_global:
                raise ValueError('Image URL must resolve to public addresses')
            result.append(dict(hostname=host, host=address[0], port=port, family=fam, proto=proto, flags=socket.AI_NUMERICHOST))
        return result

    async def close(self):
        pass

async def bounded_read(response, limit):
    data = bytearray()
    async for chunk in response.content.iter_chunked(65536):
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError('Image response exceeds size limit')
    return bytes(data)

def validate_image(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Invalid image size')
    with Image.open(io.BytesIO(data)) as img:
        if img.format not in ('PNG', 'JPEG', 'WEBP') or img.width * img.height > 40_000_000:
            raise ValueError('Unsupported image format or dimensions')
        mime = Image.MIME[img.format]
        img.verify()
    return data, mime

def decode_image(value):
    if len(value) > (MAX_IMAGE_BYTES * 4 // 3 + 1024):
        raise ValueError('Image exceeds size limit')
    if value.startswith('data:'):
        prefix, value = value.split(',', 1)
        if prefix not in ('data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'):
            raise ValueError('Unsupported image data URI')
    return validate_image(base64.b64decode(value, validate=True))

async def download_image(url):
    # No provider headers, cookies, environment proxies, or automatic redirects.
    connector = aiohttp.TCPConnector(resolver=PublicResolver())
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=45), trust_env=False) as session:
        for _ in range(4):
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Image download requires a public HTTPS URL')
            try:
                if not ipaddress.ip_address(parsed.hostname).is_global:
                    raise ValueError('Private image address rejected')
            except ValueError as exc:
                if str(exc) == 'Private image address rejected':
                    raise
            async with session.get(url, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('Location', ''))
                    continue
                response.raise_for_status()
                return validate_image(await bounded_read(response, MAX_IMAGE_BYTES))
        raise ValueError('Too many image download redirects')

async def image_bytes(value):
    return await download_image(value) if value.startswith(('https:', 'http:')) else decode_image(value)

def image_payload(model, prompt, n=1, size=None, params=None, sources=None):
    if not model or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}', model):
        raise HTTPException(400, 'Enter an exact image model ID')
    if not prompt or not 1 <= (n or 1) <= 10:
        raise HTTPException(400, 'A prompt and image count from 1 to 10 are required')
    body = {'model': model, 'prompt': prompt, 'n': n or 1}
    if size:
        if not re.fullmatch(r'[1-9][0-9]{0,4}x[1-9][0-9]{0,4}', size):
            raise HTTPException(400, 'Image size must be WIDTHxHEIGHT')
        body['size'] = size
    params = params or {}
    if not isinstance(params, dict) or set(params) - {'quality', 'resolution', 'response_format'}:
        raise HTTPException(400, 'Surplus accepts quality, resolution, and response_format options')
    if 'quality' in params and (not isinstance(params['quality'], str) or len(params['quality']) > 32):
        raise HTTPException(400, 'Invalid image quality')
    if params.get('resolution', '1K') not in ('1K', '2K', '4K') or params.get('response_format', 'b64_json') not in ('b64_json', 'url'):
        raise HTTPException(400, 'Invalid image resolution or response format')
    body.update(params)
    if sources is not None:
        if not 1 <= len(sources) <= 8:
            raise HTTPException(400, 'Surplus edits require 1 to 8 source images')
        for source in sources:
            decode_image(source)
        body['n'] = 1
        if len(sources) == 1:
            body['image'] = sources[0]
        else:
            body['input_images'] = sources
    return body

async def catalog(url, key, source, *, edit=False):
    credential = connection_credential(url, key, {'key_source': source})
    async with ProviderSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.get(url.rstrip('/') + '/models', headers={'Authorization': 'Bearer ' + credential}) as response:
            response.raise_for_status()
            result = await response.json()
    return [dict(id=m['id'], name=m.get('name') or m['id']) for m in result.get('data', []) if image_capable(m, edit=edit)]

def image_capable(model, *, edit=False):
    # Only explicit catalog capabilities; unknown models are entered manually.
    capabilities = model.get('capabilities') or {}
    kind = model.get('type') or model.get('task') or model.get('modality')
    modalities = (model.get('architecture') or {}).get('output_modalities', [])
    if 'image_edit' in model.get('supported_features', []):
        return edit
    inputs = (model.get('architecture') or {}).get('input_modalities', [])
    if 'image' in modalities and (not edit or 'image' in inputs):
        return True
    if isinstance(capabilities, dict):
        return bool(capabilities.get('image_edit' if edit else 'image_generation')) or (not edit and ('image' in modalities or kind in ('image', 'image-generation', 'text-to-image')))
    return ('image_edit' if edit else 'image_generation') in capabilities

async def request_images(url, key, source, body, *, edit=False):
    credential = connection_credential(url, key, {'key_source': source})
    timeout = min(max(int(os.getenv('SURPLUS_IMAGE_TIMEOUT', '180')), 10), 600)
    try:
        async with ProviderSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.post(url.rstrip('/') + ('/images/edits' if edit else '/images/generations'), json=body,
                                    headers={'Authorization': 'Bearer ' + credential}) as response:
                if response.status >= 300:
                    raise HTTPException(response.status, provider_error(response.status))
                import json
                result = json.loads(await bounded_read(response, MAX_JSON_BYTES))
        items = result.get('data')
        if not isinstance(items, list) or not 1 <= len(items) <= body.get('n', 1):
            raise ValueError('Malformed image response')
        return [await image_bytes(item.get('b64_json') or item['url']) for item in items]
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(504, 'Image request timed out; check provider activity before retrying') from None
    except Exception:
        raise HTTPException(502, 'Image provider returned an invalid or unavailable image') from None
