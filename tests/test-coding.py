#!/usr/bin/env -S python3 -B

# Keep imports from writing bytecode caches, including when run via python3.
import sys
sys.dont_write_bytecode = True

import json, re, subprocess, sys, time, urllib.request
from pathlib import Path
out=Path(__file__).resolve().parent.parent / 'results/coding'; out.mkdir(parents=True, exist_ok=True)
cases=[
 ('prime', 'Implement is_prime(n: int) -> bool in Python. Negative numbers, zero and one are not prime. Use trial division up to the integer square root.', '''assert not is_prime(-7)
assert not is_prime(0)
assert not is_prime(1)
assert is_prime(2)
assert is_prime(3)
assert not is_prime(4)
assert not is_prime(49)
assert is_prime(97)
assert is_prime(104729)
assert not is_prime(104730)'''),
 ('intervals', 'Implement merge_intervals(intervals) in Python: accept unsorted pairs [start,end], merge overlapping or touching closed intervals, return sorted list of lists, do not mutate input. Empty input returns [].', '''assert merge_intervals([])==[]
assert merge_intervals([[5,7],[1,3],[2,6]])==[[1,7]]
assert merge_intervals([[1,2],[2,3],[8,9]])==[[1,3],[8,9]]
assert merge_intervals([[1,10],[2,3],[4,8]])==[[1,10]]
a=[[5,6],[1,2]]
b=[x[:] for x in a]
assert merge_intervals(a)==[[1,2],[5,6]]
assert a==b'''),
 ('brackets', 'Implement balanced_brackets(text: str) -> bool in Python for (), [] and {}. Ignore all other characters. Reject mismatched ordering or unmatched brackets. Empty string is balanced.', '''assert balanced_brackets('')
assert balanced_brackets('abc')
assert balanced_brackets('a{b[c(d)e]f}g')
assert not balanced_brackets('([)]')
assert not balanced_brackets(']')
assert not balanced_brackets('(()')
assert balanced_brackets('()[]{}')''')]
summary=[]
for name,task,tests in cases:
 data={'model':'bonsai2-27b','messages':[{'role':'system','content':'Return only executable Python code, no explanations. Use only the Python standard library. Do not include tests or input/output calls.'},{'role':'user','content':task}], 'temperature':0,'max_tokens':2048,'chat_template_kwargs':{'enable_thinking':False}}
 req=urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 start=time.monotonic()
 with urllib.request.urlopen(req,timeout=600) as r: response=json.load(r)
 (out/(name+'.json')).write_text(json.dumps(response,ensure_ascii=False,indent=2))
 code=response['choices'][0]['message']['content']
 blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',code,re.S)
 if blocks: code='\n'.join(blocks)
 source=out/(name+'.py'); source.write_text(code+'\n\n'+tests+'\nprint("PASS")\n')
 # Generated code runs isolated, with time and memory limits and no network.
 proc=subprocess.run(['podman','run','--rm','--network','none','--read-only','--memory','128m','--cpus','1','--pids-limit','32','--cap-drop','all','--security-opt','no-new-privileges','-v',str(source.resolve())+':/test.py:ro','docker.io/library/python:3.12-slim','python','-I','-B','/test.py'],capture_output=True,text=True,timeout=45)
 item={'task':name,'passed':proc.returncode==0,'elapsed_seconds':time.monotonic()-start,'usage':response.get('usage'),'timings':response.get('timings'),'stdout':proc.stdout,'stderr':proc.stderr}
 summary.append(item); print(json.dumps(item),flush=True)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
assert all(x['passed'] for x in summary), 'Coding test failed'
