"""Explicit, one-request-per-operation live check. May spend provider balance; never retries."""
import argparse
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'main/upstream/backend'))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)
from open_webui.utils.provider_http import ProviderSession
from open_webui.utils.surplus_images import image_payload, request_images
from open_webui.utils.secret_refs import provider_error
from PIL import Image
import aiohttp

async def main(args):
    key = os.environ['SURPLUS_API_KEY']
    os.environ['PROVIDER_SECRET_NAMES'] = 'SURPLUS_API_KEY'
    url = 'https://api.surplusintelligence.ai/v1'
    outcomes = []
    if args.chat_model:
        try:
            async with ProviderSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url + '/chat/completions', headers={'Authorization': 'Bearer ' + key},
                    json={'model':args.chat_model,'messages':[{'role':'user','content':'Reply with the word OK.'}], 'max_tokens':128,'stream':True}) as response:
                    status = response.status
                    data = await response.read() if status == 200 else b''
                    outcomes.append({'operation':'streaming chat','model':args.chat_model,'status':status,
                        'sse_done':b'[DONE]' in data, 'content_type':response.headers.get('Content-Type'),
                        'sse_events':data.count(b'data:'), 'text_delta_present': b'\"content\":\"OK' in data or b'\"content\": \"OK' in data, 'request_id':response.headers.get('X-Request-Id')})
        except Exception as e: outcomes.append({'operation':'streaming chat','error':type(e).__name__})
    for model, edit in [(args.image_model,False),(args.edit_model,True)]:
        if not model: continue
        try:
            sources=None
            if edit:
                output=io.BytesIO();Image.new('RGB',(512,512),'#3366cc').save(output,format='PNG')
                sources=['data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()]
            body=image_payload(model,'A simple blue square on a white background.' if not edit else 'Change the blue square to green.',1,None if edit else '512x512',sources=sources)
            results=await request_images(url,'SURPLUS_API_KEY','secret',body,edit=edit)
            outcomes.append({'operation':'image edit' if edit else 'image generation','model':model,'status':200,
                             'images':len(results),'bytes':[len(data) for data,_ in results]})
        except Exception as e:
            outcomes.append({'operation':'image edit' if edit else 'image generation','model':model,
                             'status':getattr(e,'status_code',None),'error':type(e).__name__,
                             'detail':getattr(e,'detail','Request failed')})
    print(json.dumps(outcomes,indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chat-model');parser.add_argument('--image-model');parser.add_argument('--edit-model')
    asyncio.run(main(parser.parse_args()))
