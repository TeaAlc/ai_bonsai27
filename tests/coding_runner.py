"""Execute generated code with a trusted completion marker and cleanup."""
import sys
sys.dont_write_bytecode = True
import json
import subprocess
import uuid
from pathlib import Path


def run_generated(code, assertions, source, timeout=45):
    source = Path(source)
    source.write_text(code + '\n')
    container = 'bonsai-code-' + uuid.uuid4().hex
    marker = 'BONSAI_ASSERTIONS_COMPLETED_' + uuid.uuid4().hex
    # The trusted harness is a separate mounted file. An early exit from the
    # generated module cannot count as completion of the actual assertions.
    harness = source.with_suffix('.harness.py')
    harness.write_text('import runpy\nnamespace = runpy.run_path("/generated.py")\n'
                       + 'exec(' + repr(assertions) + ', namespace)\nprint(' + repr(marker) + ')\n')
    command = ['podman', 'run', '--rm', '--name', container, '--network', 'none',
               '--read-only', '--memory', '128m', '--cpus', '1', '--pids-limit', '32',
               '--cap-drop', 'all', '--security-opt', 'no-new-privileges',
               '-v', str(source.resolve()) + ':/generated.py:ro',
               '-v', str(harness.resolve()) + ':/harness.py:ro',
               'docker.io/library/python:3.12-slim', 'python', '-I', '-B', '/harness.py']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return {'passed': result.returncode == 0 and marker in result.stdout.splitlines(),
                'stdout': result.stdout, 'stderr': result.stderr}
    except subprocess.TimeoutExpired:
        return {'passed': False, 'stdout': '', 'stderr': 'Generated program exceeded its time limit.'}
    finally:
        subprocess.run(['podman', 'rm', '--force', container], capture_output=True, timeout=15)
