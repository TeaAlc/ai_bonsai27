#!/usr/bin/env -S python3 -B
"""Compatible profile-specific entry point for shared provenance validation."""
import sys
sys.dont_write_bytecode = True
import runpy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend_profile import load
PROFILE = load('blackwell')
SOURCE_REVISION = PROFILE['source_revision']
SOURCE_SHA256 = PROFILE['source_sha256']
COMPILER_IMAGE = PROFILE['compiler_image']


def verify(root):
    return runpy.run_path(str(Path(__file__).with_name('verify-source.py')))['verify'](root, 'blackwell')


if __name__ == '__main__':
    try:
        print(verify(sys.argv[1]))
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(2)
