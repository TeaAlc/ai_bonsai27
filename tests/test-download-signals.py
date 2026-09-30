#!/usr/bin/env -S python3 -B
"""Verify download cancellation, resume fallback, and failed repair isolation."""
import sys
sys.dont_write_bytecode = True
import hashlib
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir='/tmp/bonsai27', prefix='signals.') as directory:
    root = Path(directory)
    binaries = root / 'bin'; binaries.mkdir()
    curl = binaries / 'curl'
    curl.write_text('''#!/usr/bin/env bash
set -euo pipefail
output=''
resume=false
while (( $# )); do
    case "$1" in
        --output) output=$2; shift 2 ;;
        --continue-at) resume=true; shift 2 ;;
        *) shift ;;
    esac
done
if [[ ${FIXTURE_MODE:-} == range && "$resume" == true ]]; then printf 416; exit 22; fi
if [[ ${FIXTURE_MODE:-} == range ]]; then printf fixture > "$output"; exit 0; fi
if [[ ${FIXTURE_MODE:-} == failure ]]; then printf partial > "$output"; exit 7; fi
printf '%s' "$$" > "$FIXTURE_PID"
exec sleep 30
''')
    curl.chmod(0o755)
    environment = dict(os.environ, PATH=str(binaries)+':'+os.environ['PATH'], FIXTURE_PID=str(root/'pid'))
    digest = hashlib.sha256(b'fixture').hexdigest()
    def command(name, mode='reuse'):
        return ['bash', '-c', '''source "$1/data/models/download.sh"; download_missing_model fixture "$2" "$3" "$4" & active=$!; trap 'kill -TERM "$active" 2>/dev/null || true; wait "$active" 2>/dev/null || true; exit 143' TERM; wait "$active"''', 'test', str(ROOT), str(root/name), digest, mode]
    process = subprocess.Popen(command('model.gguf'), env=environment, start_new_session=True)
    deadline = time.monotonic()+5
    while not (root/'pid').exists() and time.monotonic()<deadline: time.sleep(.05)
    assert (root/'pid').exists()
    child = int((root/'pid').read_text())
    # Signal the supervising parent; it forwards TERM to the downloader.
    process.terminate()
    assert process.wait(timeout=5) != 0
    assert not (root/'model.gguf.lock.d').exists()
    try: os.kill(child, 0)
    except ProcessLookupError: pass
    else: raise AssertionError('download child survived cancellation')
    environment['FIXTURE_MODE']='range'
    (root/'range.gguf.part').write_bytes(b'partial')
    subprocess.run(command('range.gguf'), env=environment, check=True)
    assert (root/'range.gguf').read_bytes() == b'fixture'
    environment['FIXTURE_MODE']='failure'
    (root/'repair.gguf').write_bytes(b'old file')
    assert subprocess.run(command('repair.gguf', 'repair'), env=environment).returncode != 0
    assert (root/'repair.gguf').read_bytes() == b'old file'
    assert (root/'repair.gguf.part').exists()
print('Passed cancellation, Range fallback, and failed repair preservation.')
