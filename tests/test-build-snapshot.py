#!/usr/bin/env -S python3 -B
"""A real Git snapshot must remain stable when the checkout changes mid-build."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir='/tmp/bonsai27',prefix='snapshot-test.') as directory:
    root=Path(directory);repo=root/'repo';repo.mkdir()
    for name in ('data/logging.sh','image_build.sh','tools/project.sh','tools/backend-artifacts.sh','tools/verify-backend.py','tools/verify-ada-source.py','tools/verify-blackwell-source.py','tools/verify-source.py','tools/backend_profile.py','tools/backend-profiles.json','tools/build-receipt.py','tools/semrel/artifacts.sh','data/models/download.sh'):
        destination=repo/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/name,destination)
    (repo/'tools/version.sh').write_text('#!/bin/sh\necho 1.0.0\n');(repo/'tools/version.sh').chmod(0o755)
    (repo/'Containerfile').write_text('FROM fixture\n')
    (repo/'entrypoint.sh').write_text('original committed content\n')
    pins=(repo/'tools/backend-artifacts.sh').read_text()
    import re
    for backend,prefix in [('blackwell','BLACKWELL'),('ampere-ada','AMPERE_ADA')]:
        runtime=repo/'data/backends'/backend/'runtime';runtime.mkdir(parents=True)
        (runtime/'payload').write_text('fixture')
        manifest=hashlib.sha256(b'fixture').hexdigest()+'  ./payload\n'
        (runtime/'SHA256SUMS').write_text(manifest)
        pins=re.sub(r'readonly '+prefix+r'_MANIFEST_SHA=[a-f0-9]+','readonly '+prefix+'_MANIFEST_SHA='+hashlib.sha256(manifest.encode()).hexdigest(),pins)
    # Prepared architecture-specific builds must survive ordinary image rebuilds.
    import importlib.util
    for backend, architecture in [('ada', '89-real'), ('blackwell', '120-real')]:
        spec=importlib.util.spec_from_file_location(backend, PROJECT/f'tools/verify-{backend}-source.py')
        verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
        runtime=repo/'data/backends'/f'{backend}-source'/'runtime';runtime.mkdir(parents=True)
        for name in ('bin/llama-server','lib/libggml-cuda.so.0','lib/libnccl.so.2',
                     'LICENSES/llama.cpp-LICENSE.txt','LICENSES/NCCL-copyright.txt'):
            path=runtime/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
        record={'source_revision':verifier.SOURCE_REVISION,'source_sha256':verifier.SOURCE_SHA256,
                'compiler_image':verifier.COMPILER_IMAGE,'architectures':[architecture], 'cmake_cache':f'CMAKE_CUDA_ARCHITECTURES:STRING={architecture}\nGGML_CUDA:BOOL=ON\nGGML_CUDA_FA:BOOL=ON\nGGML_CUDA_GRAPHS:BOOL=ON\n'}
        record['cmake_cache'] = ''.join(f'{key}:STRING={value}\n' for key,value in verifier.PROFILE['cmake_options'].items())
        for license_name in verifier.PROFILE['licenses']:
            (runtime/'LICENSES'/license_name).write_text('fixture')
        (runtime/'build.json').write_text(json.dumps(record))
        entries=[hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(runtime))
                 for path in sorted(runtime.rglob('*')) if path.is_file()]
        (runtime/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
    (repo/'tools/backend-artifacts.sh').write_text(pins)
    (repo/'.gitignore').write_text('data/backends/\nresults/\n')
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    git('init','--quiet','--initial-branch=main');git('config','user.name','Test');git('config','user.email','test@example.invalid');git('add','.');git('commit','--quiet','-m','feat: fixture');original=git('rev-parse','HEAD')
    binaries=root/'bin';binaries.mkdir();stub=binaries/'podman'
    stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
args=sys.argv[1:]
if args[0]=='build':
    stage=pathlib.Path(args[-1])
    assert (stage/'entrypoint.sh').read_text()=='original committed content\\n'
    labels={}
    for index,arg in enumerate(args):
        if arg=='--label':
            key,value=args[index+1].split('=',1);labels[key]=value
    variant=os.environ.get('FIXTURE_VARIANT','ptq1_0')
    assert labels['io.bonsai.model.variant']==variant
    repository='localhost/bonsai2-27b-pq2-0' if variant=='pq2_0' else 'localhost/bonsai2-27b'
    assert [args[i+1] for i,arg in enumerate(args) if arg=='--tag']==[repository+':1.0.0',repository+':latest']
    model_file='Bonsai-2-27B-PQ2_0-MTP.gguf' if variant=='pq2_0' else 'Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf'
    assert [args[i+1] for i,arg in enumerate(args) if arg=='--build-arg']==['BONSAI_MODEL_VARIANT='+variant,'BONSAI_MODEL_FILE='+model_file]
    assert labels['io.bonsai.model.file']==model_file
    pathlib.Path(os.environ['FIXTURE_IMAGE']).write_text(json.dumps([{'Id':'a'*64,'Config':{'Labels':labels}}]))
    original_profile=(stage/'tools/backend-profiles.json').read_bytes()
    pathlib.Path('tools/backend-profiles.json').write_text('{}')
    assert (stage/'tools/backend-profiles.json').read_bytes()==original_profile
    pathlib.Path('entrypoint.sh').write_text('changed during build\\n')
    subprocess.run(['git','add','entrypoint.sh'],check=True)
    subprocess.run(['git','commit','--quiet','-m','fix: concurrent edit'],check=True)
    assert (stage/'entrypoint.sh').read_text()=='original committed content\\n'
elif args[:2]==['image','inspect']:print(pathlib.Path(os.environ['FIXTURE_IMAGE']).read_text())
elif args[0]=='run':print('fixture-package\\t1.0')
else:sys.exit(2)
''');stub.chmod(0o755)
    env=dict(os.environ,PATH=str(binaries)+':'+os.environ['PATH'],TMPDIR=str(root/'tmp'),FIXTURE_IMAGE=str(root/'image.json'),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([str(repo/'image_build.sh')],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    receipt=json.loads((repo/'results/last-build.json').read_text())
    assert receipt['revision']==original and receipt['dirty'] is False
    assert git('rev-parse','HEAD')!=original
    assert receipt['image_id']=='sha256:'+'a'*64
    assert receipt['source_verifier_inputs']['tools/backend-profiles.json'] != hashlib.sha256((repo/'tools/backend-profiles.json').read_bytes()).hexdigest()
    assert set(receipt['inputs'])=={'blackwell','ampere-ada','ada-source','blackwell-source'}
    assert receipt['ada_source_build']['architectures']==['89-real']
    assert receipt['blackwell_source_build']['architectures']==['120-real']
    assert receipt['model_variant']=='ptq1_0'
    # PQ2 uses separate image tags and pins without losing prepared runtimes.
    shutil.copy2(PROJECT/'tools/backend-profiles.json',repo/'tools/backend-profiles.json')
    (repo/'entrypoint.sh').write_text('original committed content\n')
    git('add','entrypoint.sh');git('commit','--quiet','-m','fix: restore fixture source')
    env['FIXTURE_VARIANT']='pq2_0'
    result=subprocess.run([str(repo/'image_build.sh'),'--pq2'],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    variant_receipt=json.loads((repo/'results/last-build.json').read_text())
    assert variant_receipt['model_variant']=='pq2_0'
    assert variant_receipt['model_file']=='Bonsai-2-27B-PQ2_0-MTP.gguf'
    assert variant_receipt['model_revision']=='5edf5f552d45e40b81f0255a8bb443af35850722'
    assert variant_receipt['model_sha256']=='78df4279d40ebebdccfd2dae0e9d4847afee52e94f48f3542ae9437220dbd847'
    assert set(variant_receipt['inputs'])==set(receipt['inputs'])
    # The same project lock is honored by independent processes.
    command=['bash','-c','cd "$1"; source tools/project.sh; lock_project; echo start >> "$2"; sleep .2; echo end >> "$2"','test',str(repo),str(root/'events')]
    one=subprocess.Popen(command,env=env);two=subprocess.Popen(command,env=env)
    assert one.wait(timeout=10)==0 and two.wait(timeout=10)==0
    assert (root/'events').read_text().splitlines()==['start','end','start','end']
print('Passed immutable committed snapshot, original revision receipt, and shared operation lock.')
