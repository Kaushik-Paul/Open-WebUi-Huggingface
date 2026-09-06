"""Run after recreating the fixture app with its existing named volume."""
import json
from pathlib import Path
import httpx
with httpx.Client(base_url='http://127.0.0.1:17860',timeout=60) as c:
    r=c.post('/api/v1/auths/signin',json={'email':'owner@example.com','password':'fixture-password-123'})
    assert r.status_code==200,r.text
    c.headers['Authorization']='Bearer '+r.json()['token']
    fixture=json.loads(Path('/tmp/owui-persistence-fixture.json').read_text())
    assert c.get(fixture['file_url']).status_code==200
    assert c.get('/api/v1/chats/'+fixture['chat_id']).json()['chat']['title']=='Persistence fixture'
    config=c.get('/openai/config').json()
    assert config['OPENAI_API_KEYS']==['SURPLUS_API_KEY']
    assert config['OPENAI_API_CONFIGS']['0']['key_source']=='secret'
    images=c.get('/api/v1/images/config').json()
    assert images['IMAGES_EDIT_OPENAI_KEY_SOURCE']=='secret'
    assert c.post('/openai/chat/completions',json={'model':'fixture-chat','messages':[{'role':'user','content':'rotation check'}]}).status_code==200
    assert c.post('/api/v1/images/generations',json={'prompt':'rotation check','n':1}).status_code==200
    print('PASS: owner/chat/reference metadata/generated file survived recreation; rotated secret used for new chat and image requests')
