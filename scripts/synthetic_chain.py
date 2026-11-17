#!/usr/bin/env python3
"""Write the synthetic workloads used for depth and fan-in scaling (hash-only, no files).

  chain  a linear chain of depth 0-20 (21 models), each model the finetune of the last
  fanin  8 roots and four children with 1, 2, 4 and 8 of those roots as parents

Every model ID starts with "synthetic/" and every row carries workload = chain or fanin,
so the data can never be mistaken for the real tree. Hashes follow the same rules as
hf_lineage.py; weights hashes are derived from the model ID, so they are unique and the
output is identical on every run.

Writes <out>/synthetic_chain.csv with the registration-plan columns plus `workload`.
"""
import argparse
import csv
from pathlib import Path

from hf_lineage import data_ref_hash, meta_hash, sha256_hex
from registration_plan import PLAN_FIELDS, licence_class

ROOT = Path(__file__).resolve().parents[1]
CHAIN_DEPTH = 20
FANIN_SIZES = (1, 2, 4, 8)
LICENCE = 'apache-2.0'
DATASETS = ['synthetic/dataset']
PUBLISHER = 'synthetic'


def model(workload: str, model_id: str, depth: int, parents: dict[str, str]) -> dict:
    return {
        'workload': workload,
        'model_id': model_id,
        'depth': depth,
        'n_parents': len(parents),
        'parents': ';'.join(parents),
        'relations': ';'.join(parents.values()),
        'license': LICENCE,
        'licence_class': licence_class(LICENCE)[0],
        'datasets': ';'.join(DATASETS),
        'data_ref_hash': data_ref_hash(DATASETS),
        'weights_hash': sha256_hex(f'synthetic:weights:{model_id}'),
        'meta_hash': meta_hash(model_id, '', LICENCE, parents),
        'repo_sha': '',
        'publisher': PUBLISHER,
    }


def workloads() -> list[dict]:
    rows = []
    previous = None
    for d in range(CHAIN_DEPTH + 1):
        mid = f'synthetic/chain-d{d:02d}'
        rows.append(model('chain', mid, d, {previous: 'finetune'} if previous else {}))
        previous = mid
    roots = [f'synthetic/fanin-root-{i}' for i in range(max(FANIN_SIZES))]
    rows.extend(model('fanin', r, 0, {}) for r in roots)
    for k in FANIN_SIZES:
        relation = 'finetune' if k == 1 else 'merge'
        rows.append(model('fanin', f'synthetic/fanin-{k}', 1, {r: relation for r in roots[:k]}))

    index = {r['model_id']: i for i, r in enumerate(rows)}
    for i, r in enumerate(rows):
        r['plan_index'] = i
        r['parent_indices'] = ';'.join(str(index[p]) for p in r['parents'].split(';') if p)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, default=ROOT / 'data' / 'synthetic_chain.csv')
    args = parser.parse_args()
    rows = workloads()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['workload'] + PLAN_FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} synthetic models to {args.out}')


if __name__ == '__main__':
    main()
