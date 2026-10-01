#!/usr/bin/env -S python3 -B
"""Reject wrong answers, empty results, stale evidence, and mixed image logs."""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('qa',Path(__file__).with_name('qa.py'))
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/tmp/bonsai27',prefix='qa-fixture.')
        self.root=Path(self.temp.name)
        self.identity={'run_id':'run16','suite_id':'suite','image_id':'sha256:image','revision':'source','context':16384,'model_hashes':['1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685  /models/model.gguf','e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7  /models/vision.gguf'],'started_at':'2026-09-30T00:00:00+00:00'}
        (self.root/'identity.json').write_text(json.dumps(self.identity))
        small=self.root/'context-8192';small.mkdir()
        self.small=dict(self.identity,run_id='run8',context=8192)
        (small/'identity.json').write_text(json.dumps(self.small))
        self.write('props',{'default_generation_settings':{'n_ctx':8192}},small,self.small)
        self.write('props',{'default_generation_settings':{'n_ctx':16384}})
        self.write('models',{'data':[{'id':'bonsai2-27b'}]})
        self.write('chat',{'choices':[{'message':{'content':'42'}}]})
        self.write('context-16k',{'usage':{'prompt_tokens':15000}})
        self.write('api-test-summary',{'long_context_pass':True})
        self.write('vision/summary',[{'passed':True}]*2)
        self.write('coding/summary',[{'passed':True, 'timings':{'draft_n':10, 'draft_n_accepted':8}}]*3)
        log='''offloaded 66/66 layers to GPU
CUDA0 model buffer size
flash_attn            = enabled
flash_attn            = enabled
K (q8_0) V (q8_0)
K (q8_0) V (q8_0)
n_max=2,
speculative decoding enabled: draft-mtp
devices=[CUDA0]
CLIP using CPU backend
Ternary-Bonsai-2-27B-mmproj-BF16.gguf
'''
        (self.root/'server.log').write_text(log)
        self.write('server-log',{'sha256':hashlib.sha256(log.encode()).hexdigest()})

    def tearDown(self):self.temp.cleanup()
    def write(self,name,data,root=None,metadata=None):
        root=root or self.root;metadata=metadata or self.identity
        path=root/(name+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'run_id':metadata['run_id'],'image_id':metadata['image_id'],'recorded_at':'2026-09-30T00:01:00+00:00','data':data}))

    def test_valid(self):self.assertTrue(all(qa.audit(self.root).values()))
    def test_token_byte_log(self):
        path = self.root / 'server.log'
        raw = path.read_bytes() + b'\nverbose token fragment: \xe2\x80\n'
        path.write_bytes(raw)
        self.write('server-log', {'sha256': hashlib.sha256(raw).hexdigest()})
        self.assertTrue(all(qa.audit(self.root).values()))
        path.write_bytes(raw + b'tampered')
        with self.assertRaises(ValueError):
            qa.audit(self.root)

    def test_published_backend_mtp_log(self):
        path = self.root / 'server.log'
        log = path.read_text().replace('speculative decoding enabled: draft-mtp',
            "adding speculative implementation 'draft-mtp'\nspeculative decoding context initialized")
        path.write_text(log)
        self.write('server-log', {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.assertTrue(all(qa.audit(self.root).values()))
        path.write_text(log.replace('speculative decoding context initialized', ''))
        self.write('server-log', {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        with self.assertRaises(AssertionError):
            qa.audit(self.root)

    def test_wrong_answer(self):
        self.write('chat',{'choices':[{'message':{'content':'142'}}]})
        with self.assertRaises(AssertionError):qa.audit(self.root)
    def test_empty_summary(self):
        self.write('coding/summary',[])
        with self.assertRaises(AssertionError):qa.audit(self.root)
    def test_wrong_image(self):
        self.write('chat',{},metadata=dict(self.identity,image_id='other'))
        with self.assertRaises(ValueError):qa.audit(self.root)
    def test_stale(self):
        path=self.root/'chat.json';data=json.loads(path.read_text());data['recorded_at']='2025';path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):qa.audit(self.root)
    def test_replaced_log(self):
        with (self.root/'server.log').open('a') as stream:stream.write('different log')
        with self.assertRaises(ValueError):qa.audit(self.root)
    def test_unrelated_small_run(self):
        (self.root/'context-8192/identity.json').write_text(json.dumps(dict(self.small,suite_id='other')))
        with self.assertRaises(ValueError):qa.audit(self.root)


if __name__=='__main__':unittest.main()
