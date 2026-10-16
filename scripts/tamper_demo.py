#!/usr/bin/env python3
"""Demonstrate a single-byte modification invalidating a registered digest."""
import argparse
import tempfile
from pathlib import Path
from hash_file import sha256_bytes


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    args = p.parse_args()
    baseline = sha256_bytes(args.file)
    with tempfile.TemporaryDirectory() as work:
        modified = Path(work) / args.file.name
        modified.write_bytes(args.file.read_bytes() + b'\x01')
        tampered = sha256_bytes(modified)
    print(f'Original: 0x{baseline.hex()}')
    print(f'Modified: 0x{tampered.hex()}')
    print(f'Tampering detected: {baseline != tampered}')
    if baseline == tampered:
        raise RuntimeError('Unexpected identical digests after modification')


if __name__ == '__main__':
    main()
