#!/usr/bin/env python3
"""Deterministic offline single-bit tampering trials with recorded seed and raw results."""
import argparse
import csv
import hashlib
import random
from pathlib import Path


def digest(content: bytes) -> bytes:
    return hashlib.sha256(content).digest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='+', type=Path)
    p.add_argument('--trials', type=int, default=30)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--output', type=Path, default=Path('results/integrity.csv'))
    args = p.parse_args()
    if args.trials < 1:
        p.error('Trials must be at least 1')
    rng = random.Random(args.seed)
    rows = []
    for path in args.files:
        original = path.read_bytes()
        if not original:
            raise ValueError(f'Cannot flip a bit in an empty file: {path}')
        official_digest = digest(original)
        rows.append({'file': str(path), 'trial': 0, 'tampered': False,
                     'detected': digest(original) != official_digest, 'seed': args.seed})
        for trial in range(1, args.trials + 1):
            modified = bytearray(original)
            position = rng.randrange(len(modified))
            modified[position] ^= 1 << rng.randrange(8)
            detected = digest(modified) != official_digest
            rows.append({'file': str(path), 'trial': trial, 'tampered': True,
                         'detected': detected, 'seed': args.seed})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    tampered = [row for row in rows if row['tampered']]
    clean = [row for row in rows if not row['tampered']]
    print(f'{sum(row["detected"] for row in tampered)}/{len(tampered)} modifications detected')
    print(f'{sum(not row["detected"] for row in clean)}/{len(clean)} original files accepted')
    print(f'Raw trials (seed={args.seed}) written to {args.output}')


if __name__ == '__main__':
    main()
