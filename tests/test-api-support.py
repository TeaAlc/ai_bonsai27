#!/usr/bin/env -S python3 -B
"""A slow/unavailable API must not turn readiness into hours of retries."""
import sys
sys.dont_write_bytecode = True
import os
import tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory(dir='/tmp/bonsai27',prefix='api-support.') as directory:
    os.environ['BONSAI_TEST_RUN_DIR']=directory
    os.environ['BONSAI_TEST_SUITE_ID']='fixture'
    import api_support
    clock=[0.0]
    attempts=[]
    def failed_call(path, timeout):
        attempts.append(timeout)
        clock[0]+=timeout
        raise TimeoutError('slow fixture')
    with patch.object(api_support,'call',side_effect=failed_call), patch.object(api_support.time,'monotonic',side_effect=lambda:clock[0]), patch.object(api_support.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)):
        try:api_support.wait_ready(seconds=6)
        except RuntimeError:pass
        else:raise AssertionError('unavailable API passed readiness')
    assert clock[0]<=6.5 and all(timeout<=3 for timeout in attempts)
print('Passed bounded readiness deadline and short health request timeouts.')
