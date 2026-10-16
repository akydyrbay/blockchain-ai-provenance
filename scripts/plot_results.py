#!/usr/bin/env python3
"""Produce publication-ready graphs from raw experiment CSVs."""
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    folder = ROOT / 'figures'
    folder.mkdir(exist_ok=True)
    hash_csv = ROOT / 'results' / 'hash_benchmark.csv'
    if hash_csv.is_file():
        grouped = {}
        with hash_csv.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                grouped.setdefault(int(row['size_mib']), []).append(float(row['hash_time_ms']))
        sizes = sorted(grouped)
        medians = [statistics.median(grouped[s]) for s in sizes]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(sizes, medians, 'o-')
        ax.set(xlabel='Artifact size (MiB)', ylabel='Median hashing time (ms)',
               title='Off-chain SHA-256 hashing time')
        fig.tight_layout()
        fig.savefig(folder / 'hash_time.png', dpi=180)
        plt.close(fig)
        print('Generated figures/hash_time.png')
    gas_csv = ROOT / 'results' / 'gas.csv'
    if gas_csv.is_file():
        with gas_csv.open(newline='', encoding='utf-8') as f:
            records = list(csv.DictReader(f))
        labels = [r['operation'] for r in records]
        vals = [int(r['gas_used']) for r in records]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(labels, vals)
        ax.set(xlabel='Transaction', ylabel='Gas used', title='Observed transaction gas on Sepolia')
        ax.tick_params(axis='x', rotation=25)
        fig.tight_layout()
        fig.savefig(folder / 'transaction_gas.png', dpi=180)
        plt.close(fig)
        print('Generated figures/transaction_gas.png')


if __name__ == '__main__':
    main()
