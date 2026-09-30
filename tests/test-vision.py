#!/usr/bin/env -S python3 -B

# Keep imports from writing bytecode caches, including when run via python3.
import sys
sys.dont_write_bytecode = True

import base64,json,struct,time,urllib.request,zlib
from pathlib import Path
out=Path(__file__).resolve().parent.parent / 'results/vision';out.mkdir(parents=True,exist_ok=True)
def chunk(t,b): return struct.pack('!I',len(b))+t+b+struct.pack('!I',zlib.crc32(t+b)&0xffffffff)
def fixture(name):
 w=h=384; rows=[]
 for y in range(h):
  row=bytearray()
  for x in range(w):
   if name=='red-square': inside=90<=x<294 and 90<=y<294; color=(230,20,20)
   else: inside=(x-192)**2+(y-192)**2<105**2; color=(20,40,230)
   row.extend(color if inside else (255,255,255))
  rows.append(b'\x00'+row)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
summary=[]
for name,expected in [('red-square',('red','square')),('blue-circle',('blue','circle'))]:
 png=fixture(name);(out/(name+'.png')).write_bytes(png)
 data={'model':'bonsai2-27b','messages':[{'role':'user','content':[{'type':'text','text':'Identify the single colored shape in this image. Answer in English with just its color and shape.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(png).decode()}}]}],'temperature':0,'max_tokens':128,'chat_template_kwargs':{'enable_thinking':False}}
 req=urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 start=time.monotonic()
 with urllib.request.urlopen(req,timeout=600) as r: response=json.load(r)
 (out/(name+'.json')).write_text(json.dumps(response,indent=2))
 answer=response['choices'][0]['message']['content'];passed=all(x in answer.lower() for x in expected)
 item={'fixture':name,'answer':answer,'passed':passed,'wall_seconds':time.monotonic()-start,'timings':response.get('timings')}
 summary.append(item);print(json.dumps(item),flush=True)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
assert all(x['passed'] for x in summary)
