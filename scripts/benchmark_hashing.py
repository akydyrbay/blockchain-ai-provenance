#!/usr/bin/env python3
"""Benchmark off-chain SHA-256 performance at controlled file sizes."""
import argparse
import csv
import hashlib
import os
import statistics
import tempfile
import time
from pathlib import Path


def digest_file(path: Path) -> bytes:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.digest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sizes-mib', nargs='+', type=int, default=[1, 10, 50])
    p.add_argument('--repeats', type=int, default=10)
    p.add_argument('--output', type=Path, default=Path('results/hash_benchmark.csv'))
    args = p.parse_args()
    if args.repeats < 1 or not args.sizes_mib or any(s < 1 for s in args.sizes_mib):
        p.error('Require positive --sizes-mib and --repeats')
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'generated.bin'
        for mib in args.sizes_mib:
            # Public deterministic artificial bytes; not sensitive data.
            block = hashlib.sha256(b'ai-provenance-experiment').digest() * (1024 * 1024 // 32)
            with path.open('wb') as f:
                for _ in range(mib):
                    f.write(block)
            measurements = []
            for _ in range(args.repeats):
                start = time.perf_counter()
                digest_file(path)
                measurements.append((time.perf_counter() - start) * 1000)
            for i, elapsed_ms in enumerate(measurements, 1):
                rows.append({'size_mib': mib, 'repeat': i, 'hash_time_ms': f'{elapsed_ms:.3f}'})
            print(f'{mib} MiB: median {statistics.median(measurements):.3f} ms ({args.repeats} repeats)')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['size_mib', 'repeat', 'hash_time_ms'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Raw measurements written to {args.output}')


if __name__ == '__main__':
    main()
