"""Deterministic OpenAI-compatible fixture. Bind only inside the test Docker network."""
import base64
import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image

output=io.BytesIO();Image.new('RGB',(16,16),'#3366cc').save(output,format='PNG')
PNG=base64.b64encode(output.getvalue()).decode()
RECORDS=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,value,status=200):
        data=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/audit': return self.reply(RECORDS)
        self.reply({'object':'list','data':[
            {'id':'fixture-chat','object':'model','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_features':['tools','streaming']},
            {'id':'fixture-image','object':'model','architecture':{'input_modalities':['text'],'output_modalities':['image']}},
            {'id':'fixture-edit','object':'model','supported_features':['image_edit'],'architecture':{'input_modalities':['text','image'],'output_modalities':['image']}}
        ]})
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        RECORDS.append({'path':self.path,'auth_matches':self.headers.get('Authorization')=='Bearer '+os.environ.get('SURPLUS_API_KEY','fixture-canary'),
                        'json':True, 'model':data.get('model'), 'has_image':bool(data.get('image') or data.get('input_images'))})
        if data.get('model')=='error-model':return self.reply({'error':self.headers.get('Authorization')},402)
        if self.path.endswith('/images/generations') or self.path.endswith('/images/edits'):return self.reply({'data':[{'b64_json':PNG}]})
        if self.path.endswith('/embeddings'):return self.reply({'data':[{'embedding':[0.1,0.2,0.3],'index':0}],'model':data.get('model'),'usage':{'total_tokens':1}})
        if data.get('stream'):
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            for event in [{'id':'fixture','object':'chat.completion.chunk','choices':[{'index':0,'delta':{'role':'assistant','content':'Mock reply.'},'finish_reason':None}]},
                          {'id':'fixture','object':'chat.completion.chunk','choices':[{'index':0,'delta':{},'finish_reason':'stop'}]},
                          {'id':'fixture','choices':[],'usage':{'prompt_tokens':1,'completion_tokens':2,'total_tokens':3}}]:
                self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode());self.wfile.flush()
            # Deliberately omit DONE: a live Surplus seller also ended on EOF.
            self.close_connection=True
        else:self.reply({'id':'fixture','object':'chat.completion','model':data.get('model'),'choices':[{'index':0,'message':{'role':'assistant','content':'Mock reply.'},'finish_reason':'stop'}],'usage':{'total_tokens':3}})

if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
