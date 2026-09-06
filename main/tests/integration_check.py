"""Full-container checks against an isolated owner, database, and mock provider."""
import json
import os
from pathlib import Path
import httpx
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:17860')
EMAIL=os.getenv('TEST_OWNER_EMAIL','owner@example.com')
PASSWORD=os.getenv('TEST_OWNER_PASSWORD','fixture-password-123')
CANARY='fixture-canary'
with httpx.Client(base_url=BASE,timeout=60) as client:
    for path in ['/openai/models','/api/models','/api/v1/chats/','/api/v1/images/config','/api/v1/files/','/api/v1/configs/export','/cache/private','/api/v1/auths/']:
        r=client.get(path);assert r.status_code==401,(path,r.status_code)
    assert client.post('/api/v1/auths/signup',json={'email':EMAIL,'password':PASSWORD,'name':'attacker'}).status_code==403
    assert client.get('/health').json()=={'status':True}
    config=client.get('/api/config').json();assert config['features']['enable_signup'] is False
    assert client.post('/api/v1/auths/signin',json={'email':EMAIL,'password':'wrong'}).status_code in (400,401)
    r=client.post('/api/v1/auths/signin',json={'email':EMAIL,'password':PASSWORD});assert r.status_code==200,r.text[:300]
    client.headers['Authorization']='Bearer '+r.json()['token']
    connection={'ENABLE_OPENAI_API':True,'OPENAI_API_BASE_URLS':['http://mock-provider:8000/v1'],
                'OPENAI_API_KEYS':['SURPLUS_API_KEY'],'OPENAI_API_CONFIGS':{'0':{'key_source':'secret','auth_type':'bearer','enable':True}}}
    r=client.post('/openai/config/update',json=connection);assert r.status_code==200,r.text[:300]
    assert CANARY not in r.text and r.json()['OPENAI_API_KEYS']==['SURPLUS_API_KEY']
    r=client.post('/openai/verify',json={'url':connection['OPENAI_API_BASE_URLS'][0],'key':'SURPLUS_API_KEY','config':{'key_source':'secret'}});assert r.status_code==200,r.text[:300]
    r=client.get('/openai/models');assert r.status_code==200,r.text[:300]
    for stream in [False,True]:
        r=client.post('/openai/chat/completions',json={'model':'fixture-chat','messages':[{'role':'user','content':'hello'}],'stream':stream})
        assert r.status_code==200 and 'Mock reply.' in r.text,r.text[:500]
        if stream:assert 'total_tokens' in r.text
    config=client.get('/api/v1/images/config').json()
    for prefix in ['IMAGES_OPENAI','IMAGES_EDIT_OPENAI']:
        config.update({prefix+'_API_BASE_URL':'http://mock-provider:8000/v1',prefix+'_API_KEY':'SURPLUS_API_KEY',prefix+'_KEY_SOURCE':'secret',prefix+'_COMPATIBILITY':'surplus',prefix+'_API_VERSION':''})
    config.update(ENABLE_IMAGE_GENERATION=True,ENABLE_IMAGE_EDIT=True,IMAGE_GENERATION_ENGINE='openai',IMAGE_EDIT_ENGINE='openai',IMAGE_GENERATION_MODEL='fixture-image',IMAGE_EDIT_MODEL='fixture-edit',IMAGE_SIZE='512x512',IMAGE_EDIT_SIZE='',IMAGES_OPENAI_API_PARAMS={})
    r=client.post('/api/v1/images/config/update',json=config);assert r.status_code==200,r.text[:500]
    assert CANARY not in r.text
    for edit in [False,True]:
        r=client.get('/api/v1/images/models',params={'edit':str(edit).lower()});assert r.status_code==200,r.text
        assert ('fixture-edit' if edit else 'fixture-image') in r.text
    r=client.post('/api/v1/images/generations',json={'prompt':'blue square','n':1});assert r.status_code==200,r.text[:500]
    generated=r.json();item=generated[0]
    r=client.get(item['url']);assert r.status_code==200 and r.headers['content-type'].startswith('image/')
    r=client.post('/api/v1/images/edit',json={'prompt':'green square','image':item['url']});assert r.status_code==200,r.text[:500]
    assert client.post('/api/v1/images/edit',json={'prompt':'x','image':item['url'],'mask':'x'}).status_code==400
    r=client.post('/api/v1/chats/new',json={'chat':{'title':'Persistence fixture','messages':[],'history':{'messages':{},'currentId':None},'models':['fixture-chat']}})
    assert r.status_code==200,r.text[:500]
    Path('/tmp/owui-persistence-fixture.json').write_text(json.dumps({'file_url':item['url'],'chat_id':r.json()['id']}))
    with httpx.Client(base_url=BASE) as anonymous:
        assert anonymous.get(item['url']).status_code==401
        assert anonymous.get('/api/v1/chats/'+r.json()['id']).status_code==401
    print('PASS: authentication, saved references, verification, chat/SSE, image catalog/generation/edit, private file download, chat persistence fixture')
