"""Additional live fixture checks; intentionally exhausts login rate limit last."""
import asyncio
import httpx
import os
import socketio
BASE='http://127.0.0.1:17860'
async def sockets():
    client=socketio.AsyncClient()
    received=[]
    client.on('chat-events',lambda data: received.append(data))
    await client.connect(BASE,socketio_path='ws/socket.io',auth={'token':'forged'},transports=['websocket'])
    await client.emit('chat-events',{'chat_id':'private','data':{'type':'chat:completion'}})
    await client.emit('ydoc:document:state',{'document_id':'private'})
    await asyncio.sleep(.2)
    assert not received
    await client.disconnect()

with httpx.Client(base_url=BASE,timeout=60) as c:
    r=c.post('/api/v1/auths/signin',json={'email':'owner@example.com','password':'fixture-password-123'});assert r.status_code==200,r.text
    token=r.json()['token'];c.headers['Authorization']='Bearer '+token
    config=c.get('/openai/config').json()
    assert 'fixture-canary' not in str(config)
    bad=c.post('/openai/verify',json={'url':'http://mock-provider:8000/v1','key':'WEBUI_SECRET_KEY','config':{'key_source':'secret'}})
    assert bad.status_code==400,bad.text
    # Reorder carries each key/source with its config; keys never expand in saved output.
    literal={'key_source':'literal','model_ids':['fixture-chat'],'enable':True}
    reference={'key_source':'secret','model_ids':['fixture-chat'],'enable':True}
    two={'ENABLE_OPENAI_API':True,'OPENAI_API_BASE_URLS':['http://mock-provider:8000/v1','http://mock-provider:8000/v1'],
         'OPENAI_API_KEYS':['literal-fixture','SURPLUS_API_KEY'],'OPENAI_API_CONFIGS':{'0':literal,'1':reference}}
    assert c.post('/openai/config/update',json=two).status_code==200
    two['OPENAI_API_KEYS'].reverse();two['OPENAI_API_CONFIGS']={'0':reference,'1':literal}
    r=c.post('/openai/config/update',json=two);assert r.status_code==200
    assert r.json()['OPENAI_API_CONFIGS']['0']['key_source']=='secret'
    assert r.json()['OPENAI_API_KEYS'][0]=='SURPLUS_API_KEY'
    assert c.post('/openai/config/update',json=config).status_code==200
    # Native error response must not echo the key, even if fixture provider does.
    cfg=dict(config);cfg['OPENAI_API_CONFIGS']={'0':{'key_source':'secret','enable':True,'model_ids':['fixture-chat','error-model']}}
    assert c.post('/openai/config/update',json=cfg).status_code==200
    c.get('/openai/models')
    r=c.post('/openai/chat/completions',json={'model':'error-model','messages':[{'role':'user','content':'x'}]})
    assert r.status_code==402 and 'fixture-canary' not in r.text,r.text
    assert c.post('/openai/config/update',json=config).status_code==200
    c.headers['Authorization']='Bearer forged'
    assert c.get('/api/models').status_code==401
    # Public config remains sanitized even with a forged token.
    r=c.get('/api/config');assert r.status_code==200 and 'OPENAI_API_KEYS' not in r.text
    c.headers.clear();c.cookies.clear()
    statuses=[c.post('/api/v1/auths/signin',json={'email':'wrong@example.com','password':'wrong'}).status_code for _ in range(12)]
    assert 429 in statuses,statuses
asyncio.run(sockets())
print('PASS: no disclosure, rejected secret names, connection reorder, sanitized provider errors, forged tokens, login throttling, anonymous socket events')
