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
    for name in ('data/logging.sh','image_build.sh','tools/project.sh','tools/backend-artifacts.sh','tools/verify-backend.py','tools/build-receipt.py','tools/semrel/artifacts.sh','data/models/download.sh'):
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
    pathlib.Path(os.environ['FIXTURE_IMAGE']).write_text(json.dumps([{'Id':'a'*64,'Config':{'Labels':labels}}]))
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
    # The same project lock is honored by independent processes.
    command=['bash','-c','cd "$1"; source tools/project.sh; lock_project; echo start >> "$2"; sleep .2; echo end >> "$2"','test',str(repo),str(root/'events')]
    one=subprocess.Popen(command,env=env);two=subprocess.Popen(command,env=env)
    assert one.wait(timeout=10)==0 and two.wait(timeout=10)==0
    assert (root/'events').read_text().splitlines()==['start','end','start','end']
print('Passed immutable committed snapshot, original revision receipt, and shared operation lock.')
