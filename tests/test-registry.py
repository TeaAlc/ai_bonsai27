#!/usr/bin/env -S python3 -B
import sys
sys.dont_write_bytecode = True
import importlib.util
import hashlib
import json
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('registry',Path(__file__).resolve().parents[1]/'tools/registry.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.receipt={'version':'1.2.3','revision':'a'*40,'image_id':'sha256:'+'b'*64,'dirty':False,'source':module.SOURCE}
        self.registry=object.__new__(module.Registry)
        self.images={}
        self.registry.image=lambda tag:self.images.get(tag)

    def test_new_and_idempotent(self):
        self.assertEqual(self.registry.guard(self.receipt),'new')
        self.images['1.2.3']=dict(self.receipt)
        self.assertEqual(self.registry.guard(self.receipt),'existing')

    def test_published_conflicts_and_rollback(self):
        for key,value in [('image_id','sha256:'+'c'*64),('revision','c'*40),('version','1.2.4')]:
            self.images['1.2.3']=dict(self.receipt,**{key:value})
            with self.assertRaises(ValueError):self.registry.guard(self.receipt)
        self.images={'latest':dict(self.receipt,version='2.0.0')}
        with self.assertRaises(ValueError):self.registry.guard(self.receipt)
        self.images={'latest':dict(self.receipt,image_id='sha256:'+'c'*64)}
        with self.assertRaises(ValueError):self.registry.guard(self.receipt)

    def test_dirty_invalid_wrong_source(self):
        for key,value in [('dirty',True),('version','invalid'),('source','wrong'),('image_id','wrong')]:
            with self.assertRaises(ValueError):module.validate_receipt(dict(self.receipt,**{key:value}))

    def test_exact_manifest_promotion_and_verification(self):
        image=dict(self.receipt,raw=b'fixture',manifest={'mediaType':'fixture'},digest='sha256:manifest')
        self.images={'1.2.3':image}
        def request(path,data,content_type):
            self.assertEqual((path,data,content_type),('manifests/latest',b'fixture','fixture'))
            self.images['latest']=image
        self.registry.request=request
        self.assertEqual(self.registry.promote(self.receipt),'sha256:manifest')

    def test_manifest_config_digest_and_labels(self):
        labels={'org.opencontainers.image.version':'1.2.3','org.opencontainers.image.revision':'a'*40,
                'org.opencontainers.image.source':module.SOURCE,'io.bonsai.git.dirty':'false'}
        config=json.dumps({'config':{'Labels':labels}}).encode()
        digest='sha256:'+hashlib.sha256(config).hexdigest()
        raw=json.dumps({'mediaType':'application/vnd.oci.image.manifest.v1+json','config':{'digest':digest}}).encode()
        responses={'manifests/1.2.3':raw,'blobs/'+digest:config}
        self.registry.request=lambda path:responses[path]
        image=module.Registry.image(self.registry,'1.2.3')
        self.assertEqual(image['image_id'],digest)
        self.assertEqual(image['digest'],'sha256:'+hashlib.sha256(raw).hexdigest())
        responses['blobs/'+digest]=b'tampered'
        with self.assertRaises(ValueError):module.Registry.image(self.registry,'1.2.3')

    def test_index_preserves_top_manifest(self):
        labels={'org.opencontainers.image.version':'1.2.3','org.opencontainers.image.revision':'a'*40,
                'org.opencontainers.image.source':module.SOURCE,'io.bonsai.git.dirty':'false'}
        config=json.dumps({'config':{'Labels':labels}}).encode()
        config_id='sha256:'+hashlib.sha256(config).hexdigest()
        child=json.dumps({'config':{'digest':config_id}}).encode()
        child_id='sha256:'+hashlib.sha256(child).hexdigest()
        top=json.dumps({'mediaType':'application/vnd.oci.image.index.v1+json','manifests':[{'digest':child_id,'platform':{'os':'linux','architecture':'amd64'}}]}).encode()
        responses={'manifests/1.2.3':top,'manifests/'+child_id:child,'blobs/'+config_id:config}
        self.registry.request=lambda path:responses[path]
        image=module.Registry.image(self.registry,'1.2.3')
        self.assertEqual(image['raw'],top)
        self.assertEqual(image['image_id'],config_id)


if __name__=='__main__':unittest.main()
