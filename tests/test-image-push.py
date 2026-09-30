#!/usr/bin/env -S python3 -B

# Keep all fixture execution free of Python bytecode caches.
import sys
sys.dont_write_bytecode = True

import os
import subprocess
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TOKEN = 'unit-test-secret'

# Stub only the external container commands. The actual push script runs with
# isolated image stores, credential files, and command traces for each fixture.
ENGINE_STUB = r'''#!/usr/bin/env bash
set -euo pipefail
engine=$(basename -- "$0")
printf '%s|%s\n' "$engine" "$*" >> "$MOCK_LOG"
config_dir=''
if [[ ${1:-} == --config ]]; then
    config_dir=$2
    shift 2
fi
case "${1:-}" in
    info)
        if [[ "$engine" == podman && ${MOCK_PODMAN_READY:-true} == false ]]; then
            exit 1
        fi
        ;;
    image)
        if [[ "$engine" == docker && ${MOCK_DOCKER_HAS_IMAGE:-true} == false && ! -f "$MOCK_IMPORTED" ]]; then
            exit 1
        fi
        if [[ "$*" == *org.opencontainers.image.version* ]]; then
            printf '%s\n' "${MOCK_VERSION:-1.2.3}"
        else
            echo 'sha256:fixture-image'
        fi
        ;;
    save)
        while (( $# > 0 )); do
            if [[ "$1" == --output ]]; then
                printf 'fixture archive' > "$2"
                break
            fi
            shift
        done
        ;;
    load)
        touch "$MOCK_IMPORTED"
        ;;
    login)
        received=$(cat)
        [[ "$received" == unit-test-secret ]] || exit 1
        if [[ "$engine" == docker ]]; then
            printf 'fixture credentials' > "$config_dir/config.json"
        else
            while (( $# > 0 )); do
                if [[ "$1" == --authfile ]]; then
                    printf 'fixture credentials' > "$2"
                    break
                fi
                shift
            done
        fi
        echo 'Login succeeded'
        ;;
    tag) ;;
    push)
        if [[ ${MOCK_FAIL_PUSH:-false} == true ]]; then
            echo 'Fixture registry rejected the push' >&2
            exit 1
        fi
        while (( $# > 0 )); do
            if [[ "$1" == --digestfile ]]; then
                echo 'sha256:fixture-manifest' > "$2"
                break
            fi
            shift
        done
        echo 'Push succeeded'
        ;;
    *) exit 1 ;;
esac
'''


def run_case(name, changes=None, parameter=False, success=True):
    with tempfile.TemporaryDirectory(prefix='image-push-test.', dir='/tmp/bonsai27') as directory:
        root = Path(directory)
        binaries = root / 'bin'
        binaries.mkdir()
        for engine in ('podman', 'docker'):
            stub = binaries / engine
            stub.write_text(ENGINE_STUB)
            stub.chmod(0o755)
        log = root / 'commands.log'
        environment = dict(
            os.environ,
            PATH=str(binaries) + os.pathsep + os.environ['PATH'],
            TMPDIR=str(root),
            MOCK_LOG=str(log),
            MOCK_IMPORTED=str(root / 'imported'),
            BONSAI_PUSH_ENGINE='auto',
        )
        environment.update(changes or {})
        command = [str(PROJECT / 'image_push.sh')]
        if parameter:
            command += ['--token', TOKEN]
        result = subprocess.run(
            command,
            input='' if parameter else TOKEN + '\n',
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        trace = log.read_text()
        assert (result.returncode == 0) == success, result.stderr
        assert TOKEN not in result.stdout + result.stderr + trace
        assert not list(root.glob('ghcr-push.*')), 'Temporary credentials were not removed'
        if success:
            pushes = [line for line in trace.splitlines() if '|push ' in line or '|--config ' in line and ' push ' in line]
            assert len(pushes) == 2, trace
            assert pushes[0].endswith('ghcr.io/teaalc/ai_bonsai27:1.2.3'), trace
            assert pushes[1].endswith('ghcr.io/teaalc/ai_bonsai27:latest'), trace
        print('PASS:', name)
        return trace, result


Path('/tmp/bonsai27').mkdir(exist_ok=True)
trace, result = run_case('Podman preferred; token prompted')
assert 'podman|push ' in trace and 'docker|' not in trace
assert 'input hidden' in result.stderr

trace, result = run_case('Token parameter skips prompt', parameter=True)
assert 'input hidden' not in result.stderr

trace, _ = run_case('Unavailable Podman falls back to Docker', {'MOCK_PODMAN_READY': 'false'})
assert 'docker|--config ' in trace and ' push ghcr.io/' in trace

trace, _ = run_case('Explicit Docker imports a Podman image', {
    'BONSAI_PUSH_ENGINE': 'docker', 'MOCK_DOCKER_HAS_IMAGE': 'false',
})
assert 'podman|save ' in trace and ' load --input ' in trace

trace, _ = run_case('Invalid image version rejected before login', {'MOCK_VERSION': 'invalid'}, success=False)
assert ' login ' not in trace and '|login ' not in trace

trace, _ = run_case('Failed version push does not update latest', {'MOCK_FAIL_PUSH': 'true'}, success=False)
assert 'docker://ghcr.io/teaalc/ai_bonsai27:latest' not in trace
