#!/usr/bin/env -S python3 -B
"""Check explicit Desktop image defaults against the shared shell policy."""
import sys
sys.dont_write_bytecode = True
import re
import subprocess
from pathlib import Path
root = Path(__file__).resolve().parents[1]
values = subprocess.check_output(['bash', '-c', 'source data/config.sh; printf "%s %s" "$BONSAI_DEFAULT_CTX_SIZE" "$BONSAI_DEFAULT_REASONING_EFFORT"'], cwd=root, text=True).split()
image = (root / 'Containerfile').read_text()
assert re.search(r'BONSAI_CTX_SIZE=' + values[0] + r'\b', image)
assert re.search(r'BONSAI_REASONING_EFFORT=' + values[1] + r'\b', image)
assert '!data/config.sh' in (root / '.containerignore').read_text()
assert 'COPY data/config.sh /opt/bonsai/config.sh' in image
assert values == ['32000', 'medium']
print('Shared and image defaults agree.')
