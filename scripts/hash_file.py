#!/usr/bin/env python3
"""Print the Ethereum bytes32 representation of SHA-256(raw file bytes)."""
import argparse
import hashlib
from pathlib import Path


def sha256_bytes(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.digest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print('0x' + sha256_bytes(args.path).hex())


if __name__ == '__main__':
    main()
