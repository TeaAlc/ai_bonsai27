#!/usr/bin/env -S python3 -B
"""Use tiny pinned bundles to validate staged preparation and exact inventories."""
import sys
sys.dont_write_bytecode = True
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='prepare-test.',dir='/tmp/bonsai27') as directory:
    root=Path(directory);repo=root/'repo';repo.mkdir()
    for name in ('data/logging.sh','prepare.sh','download_models.sh','tools/project.sh','tools/backend-artifacts.sh','tools/verify-backend.py','data/models/download.sh'):
        destination=repo/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/name,destination)
    cache=root/'cache';cache.mkdir()
    for name in ('Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf','Ternary-Bonsai-2-27B-mmproj-BF16.gguf'):(cache/name).write_text('existing fixture')
    archive_dir=root/'archives';archive_dir.mkdir()
    pins=(repo/'tools/backend-artifacts.sh').read_text()
    for backend,prefix in [('blackwell','BLACKWELL'),('ampere-ada','AMPERE_ADA')]:
        bundle=root/backend;bundle.mkdir();(bundle/'payload').write_text(backend)
        digest=hashlib.sha256((bundle/'payload').read_bytes()).hexdigest()
        (bundle/'SHA256SUMS').write_text(digest+'  ./payload\n')
        archive=archive_dir/(backend+'.tar.gz')
        with tarfile.open(archive,'w:gz') as stream:stream.add(bundle,arcname='bundle')
        import re
        pins=re.sub(r'readonly '+prefix+r'_SHA=[a-f0-9]+', 'readonly '+prefix+'_SHA='+hashlib.sha256(archive.read_bytes()).hexdigest(),pins)
    (repo/'tools/backend-artifacts.sh').write_text(pins)
    binaries=root/'bin';binaries.mkdir();curl=binaries/'curl'
    curl.write_text('''#!/usr/bin/env bash
set -euo pipefail
output=''
for ((i=1;i<=$#;i++)); do
    if [[ ${!i} == --output ]]; then j=$((i+1)); output=${!j}; fi
done
url=${!#}
backend=blackwell
[[ "$url" != *sm86-sm89* ]] || backend=ampere-ada
cp "$FIXTURE_ARCHIVES/$backend.tar.gz" "$output"
echo called >> "$FIXTURE_CALLS"
''');curl.chmod(0o755)
    environment=dict(os.environ,PATH=str(binaries)+':'+os.environ['PATH'],TMPDIR=str(root/'tmp'),BONSAI_MODEL_DIR=str(cache),FIXTURE_ARCHIVES=str(archive_dir),FIXTURE_CALLS=str(root/'calls'))
    def prepare():return subprocess.run([str(repo/'prepare.sh')],env=environment,capture_output=True,text=True)
    first=prepare();assert first.returncode==0,first.stderr
    runtime=repo/'data/backends/blackwell/runtime'
    (runtime/'old-extra').write_text('must disappear')
    second=prepare();assert second.returncode==0,second.stderr
    assert not (runtime/'old-extra').exists()
    assert len((root/'calls').read_text().splitlines())==2,'verified cache used network'
    # An archive that matches its pin but has an invalid internal manifest must
    # never replace the previous verified runtime.
    bundle=root/'bad';bundle.mkdir();(bundle/'payload').write_text('damaged');(bundle/'SHA256SUMS').write_text('0'*64+'  ./payload\n')
    archive=archive_dir/'blackwell.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:stream.add(bundle,arcname='bundle')
    pins=re.sub(r'readonly BLACKWELL_SHA=[a-f0-9]+','readonly BLACKWELL_SHA='+hashlib.sha256(archive.read_bytes()).hexdigest(),pins)
    (repo/'tools/backend-artifacts.sh').write_text(pins)
    failed=prepare();assert failed.returncode!=0
    assert (runtime/'payload').read_text()=='blackwell'
    # Extra files and symlinks must fail build verification.
    (runtime/'extra').write_text('extra')
    assert subprocess.run([sys.executable,'-B',str(PROJECT/'tools/verify-backend.py'),str(runtime)],capture_output=True).returncode!=0
    (runtime/'extra').unlink();(runtime/'link').symlink_to('payload')
    assert subprocess.run([sys.executable,'-B',str(PROJECT/'tools/verify-backend.py'),str(runtime)],capture_output=True).returncode!=0
print('Passed offline archive reuse, clean replacement, failed extraction preservation, and exact file inventory.')
