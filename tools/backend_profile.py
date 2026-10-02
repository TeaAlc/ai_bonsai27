#!/usr/bin/env -S python3 -B
"""Read only the two pinned native compilation profiles."""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path


def load(name):
    if name not in ('ada', 'blackwell'):
        raise ValueError('Unknown backend profile')
    return json.loads(Path(__file__).with_name('backend-profiles.json').read_text())[name]


if __name__ == '__main__':
    profile = load(sys.argv[1])
    field = sys.argv[2]
    print(profile['architectures'][0] if field == 'architecture' else profile[field])
