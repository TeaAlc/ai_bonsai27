#!/usr/bin/env -S python3 -B
"""Verify the complete regular-file inventory, not only listed checksums."""
import sys
sys.dont_write_bytecode = True
import hashlib
from pathlib import Path


def verify(root):
    root = Path(root)
    expected = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or path in expected:
            raise ValueError('unsafe or duplicate checksum entry')
        expected[path] = digest
    actual = set()
    for item in root.rglob('*'):
        if item.is_symlink() or not (item.is_dir() or item.is_file()):
            raise ValueError(f'unsupported backend file type: {item}')
        if item.is_file() and item.relative_to(root) != Path('SHA256SUMS'):
            actual.add(item.relative_to(root))
    if actual != set(expected):
        raise ValueError(f'backend inventory mismatch: extra={actual-set(expected)}, missing={set(expected)-actual}')
    for path, digest in expected.items():
        with (root / path).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError(f'backend checksum mismatch: {path}')
    return hashlib.sha256((root / 'SHA256SUMS').read_bytes()).hexdigest()


if __name__ == '__main__':
    try:
        print(verify(sys.argv[1]))
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(2)
