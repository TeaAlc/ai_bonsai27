#!/usr/bin/env -S python3 -B
"""Verify immediate signal forwarding, inherited input/env and primary exits."""
import sys
sys.dont_write_bytecode = True
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HELPER = Path(__file__).with_name('benchmark-worker.sh')


class WorkerTests(unittest.TestCase):
    def test_input_environment_and_primary_status(self):
        command = 'set -euo pipefail; source "$1"; BONSAI_FIXTURE=medium run_worker timeout 5s bash -c \'read -r value; [[ "$value" == payload && "$BONSAI_FIXTURE" == medium ]]; exit 7\''
        process = subprocess.run(['bash', '-c', command, 'fixture', str(HELPER)],
                                 input='payload\n', text=True, capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 7, process.stderr)

    def test_direct_parent_stop_releases_child_group(self):
        with tempfile.TemporaryDirectory(dir='/tmp/bonsai27') as temporary:
            root = Path(temporary)
            worker = root / 'worker.py'
            worker.write_text('''import sys
sys.dont_write_bytecode = True
import os,signal,time
from pathlib import Path
root=Path(sys.argv[1])
def stop(*_args):
    (root/'stopped').write_text('stopped')
    raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
(root/'ready').write_text(str(os.getpid()))
while True: time.sleep(.1)
''')
            command = 'set -euo pipefail; source "$1"; trap stop_worker EXIT; trap "exit 143" TERM; run_worker timeout --kill-after=2s 30s python3 -B "$2" "$3"'
            process = subprocess.Popen(['bash', '-c', command, 'fixture', str(HELPER), str(worker), str(root)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not (root / 'ready').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue((root / 'ready').exists())
                child = int((root / 'ready').read_text())
                process.terminate()  # Signal the parent only, not its whole group.
                _, error = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 143, error)
                self.assertTrue((root / 'stopped').exists())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
