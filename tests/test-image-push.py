#!/usr/bin/env -S python3 -B
"""Exercise publication selection and credentials in isolated stores/repos."""
import sys
sys.dont_write_bytecode = True
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TOKEN = 'unit-test-secret'
IMAGE_ID = 'sha256:' + 'a'*64
STUB = r'''#!/usr/bin/env bash
set -euo pipefail
engine=$(basename "$0")
printf '%s|%s\n' "$engine" "$*" >> "$MOCK_LOG"
if [[ ${1:-} == --config ]]; then shift 2; fi
case "${1:-}" in
    info) [[ "$engine" != podman || ${MOCK_PODMAN_READY:-true} == true ]] ;;
    image)
        if [[ "$engine" == docker && ${MOCK_DOCKER_HAS_SOURCE:-false} == false && ! -f "$MOCK_IMPORTED" ]]; then exit 1; fi
        cat "$MOCK_IMAGE_JSON" ;;
    save)
        while (( $# )); do
            if [[ "$1" == --output ]]; then touch "$2"; break; fi
            shift
        done ;;
    load) touch "$MOCK_IMPORTED" ;;
    login) [[ $(cat) == unit-test-secret ]] ;;
    tag) ;;
    push) [[ ${MOCK_FAIL_PUSH:-false} == false ]] ;;
    *) exit 2 ;;
esac
'''


def run_case(name, changes=None, parameter=False, success=True, dirty=False, invalid=False, tag_mode='matching'):
    with tempfile.TemporaryDirectory(dir='/tmp/bonsai27', prefix='push-test.') as directory:
        root = Path(directory)
        repo=root/'repo'; (repo/'tools').mkdir(parents=True); (repo/'results').mkdir()
        for filename in ('image_push.sh','tools/project.sh','tools/registry.py'):
            shutil.copy2(PROJECT/filename, repo/filename)
        def git(*args): return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
        git('init','--quiet','--initial-branch=main');git('config','user.name','Test');git('config','user.email','test@example.invalid');git('add','.');git('commit','--quiet','-m','feat: fixture')
        tag_revision=git('rev-parse','HEAD')
        if tag_mode=='different':git('commit','--quiet','--allow-empty','-m','docs: later build')
        revision=git('rev-parse','HEAD')
        if tag_mode!='missing':git('tag','v1.2.3',tag_revision)
        receipt={'schema':1,'image_id':IMAGE_ID,'version':'1.2.3','revision':revision,'source':'https://github.com/TeaAlc/ai_bonsai27','dirty':dirty}
        (repo/'results/last-build.json').write_text(json.dumps(receipt))
        image={'Id':IMAGE_ID.removeprefix('sha256:'),'Config':{'Labels':{'org.opencontainers.image.version':'1.2.3','org.opencontainers.image.revision':revision,'org.opencontainers.image.source':receipt['source'],'io.bonsai.git.dirty':str(dirty).lower()}}}
        if invalid: image['Config']['Labels']['org.opencontainers.image.source']='wrong'
        image_file=root/'image.json';image_file.write_text(json.dumps([image]))
        binaries=root/'bin';binaries.mkdir()
        for engine in ('podman','docker'):
            path=binaries/engine;path.write_text(STUB);path.chmod(0o755)
        wrapper=binaries/'python3'
        wrapper.write_text('''#!/usr/bin/env bash
if [[ "$*" == *tools/registry.py* ]]; then
    echo "registry|$3" >> "$MOCK_LOG"
    [[ "$3" == promote ]] || exit 2
    [[ ${MOCK_PROMOTE_FAIL:-false} == false ]] || exit 2
    echo sha256:fixture-manifest
else
    exec "$MOCK_PYTHON" "$@"
fi
''');wrapper.chmod(0o755)
        log=root/'commands.log'
        environment=dict(os.environ, PATH=str(binaries)+':'+os.environ['PATH'], TMPDIR=str(root), MOCK_LOG=str(log), MOCK_IMPORTED=str(root/'imported'), MOCK_IMAGE_JSON=str(image_file), MOCK_PYTHON=sys.executable, BONSAI_PUSH_ENGINE='auto')
        environment.update(changes or {})
        command=[str(repo/'image_push.sh')]+(['--token',TOKEN] if parameter else [])
        result=subprocess.run(command,input='' if parameter else TOKEN+'\n',text=True,capture_output=True,env=environment)
        trace=log.read_text() if log.exists() else ''
        assert (result.returncode==0)==success,(name,result.stderr)
        assert TOKEN not in result.stdout+result.stderr+trace
        assert not list(root.glob('ghcr-push.*'))
        if success:
            assert 'registry|promote' in trace
            assert ('podman|push ' in trace or ' push ghcr.io/' in trace), 'build was not pushed'
        if tag_mode!='missing':assert git('rev-parse','v1.2.3^{commit}')==tag_revision, 'push moved a Git tag'
        print('PASS:',name)
        return trace,result


Path('/tmp/bonsai27').mkdir(exist_ok=True)
trace,result=run_case('Podman preferred, hidden prompt')
assert 'podman|push ' in trace and 'docker|' not in trace and 'input hidden' in result.stderr
trace,result=run_case('Explicit token',parameter=True)
assert 'input hidden' not in result.stderr
trace,_=run_case('Docker imports exact source despite stale latest',{'BONSAI_PUSH_ENGINE':'docker'})
assert 'podman|save ' in trace and ' load --input ' in trace
trace,_=run_case('Docker fallback with exact image',{'MOCK_PODMAN_READY':'false','MOCK_DOCKER_HAS_SOURCE':'true'})
assert ' push ghcr.io/' in trace
run_case('Dirty build can be published',dirty=True)
run_case('Build without release tag can be published',tag_mode='missing')
run_case('Docs rebuild after existing release tag can be published',tag_mode='different')
trace,_=run_case('Wrong source rejected before login',success=False,invalid=True)
assert 'login' not in trace
trace,_=run_case('Failed version push never promotes latest',{'MOCK_FAIL_PUSH':'true'},success=False)
assert 'registry|promote' not in trace
run_case('Failed promotion reports partial publication',{'MOCK_PROMOTE_FAIL':'true'},success=False)
