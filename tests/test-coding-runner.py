#!/usr/bin/env -S python3 -B
"""Actual restricted containers must reject early exit and timeouts."""
import sys
sys.dont_write_bytecode = True
import tempfile
from pathlib import Path
from coding_runner import run_generated

with tempfile.TemporaryDirectory(dir='/tmp/bonsai27',prefix='coding-runner.') as directory:
    root=Path(directory)
    assert run_generated('def value(): return 42','assert value() == 42',root/'valid.py')['passed']
    assert not run_generated('import sys; sys.exit(0)','assert False',root/'early.py')['passed']
    assert not run_generated('while True: pass','assert False',root/'timeout.py',timeout=3)['passed']
print('Passed actual coding harness completion and timeout cleanup checks.')
