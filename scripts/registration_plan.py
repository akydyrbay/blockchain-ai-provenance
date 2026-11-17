#!/usr/bin/env python3
"""Build the policy-clean, parents-first registration plan from a pulled model tree.

Reads data/hf_tree.csv (written by hf_lineage.py) and applies the policy configuration
of docs/measurement_plan.md §3 in Python, as the reference that D2 (Solidity) and D3
(Rego) must agree with:

  P1  every parent is in the plan (no revocations in the main replay)
  P2  weights and dataset hashes are non-zero; duplicates were already excluded
  P3  allowlist = every dataset hash in the plan, so it holds by construction
  P4  every Hub namespace gets a publisher account with the role, so it holds
  P5  the licence is compatible with every parent's licence (classes below)

Writes:
  <out>/registration_plan.csv       policy-clean models in topological order (all
                                    parents first, ties broken by hf_tree.csv order)
  <out>/plan_exclusions.csv         every model left out, with stage, reason and detail
  <out>/registration_plan_meta.json input hash, counts per reason, plan profile
"""
import argparse
import collections
import csv
import hashlib
import heapq
import json
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO = '0x' + '00' * 32

PLAN_FIELDS = ['plan_index', 'model_id', 'depth', 'n_parents', 'parents', 'parent_indices',
               'relations', 'license', 'licence_class', 'datasets', 'data_ref_hash',
               'weights_hash', 'meta_hash', 'repo_sha', 'publisher']
EXCLUSION_FIELDS = ['model_id', 'depth', 'n_parents', 'parents', 'license', 'stage',
                    'reason', 'detail']

# Licence classes from docs/measurement_plan.md §3, checked in this order (the first
# match wins, so the no-derivatives patterns come before the non-commercial ones).
LICENCE_CLASSES = [
    ('no-derivatives', ['cc-by-nd-*', 'cc-by-nc-nd-*']),
    ('unknown', ['', 'unknown']),
    ('permissive', ['apache-2.0', 'mit', 'bsd', 'bsd-2-clause', 'bsd-3-clause', 'isc',
                    'afl-3.0', 'wtfpl', 'unlicense', 'zlib', 'bsl-1.0', 'artistic-2.0',
                    'ecl-2.0', 'postgresql', 'ms-pl', 'cc0-1.0', 'pddl', 'odc-by',
                    'cc-by-2.0', 'cc-by-2.5', 'cc-by-3.0', 'cc-by-4.0']),
    ('copyleft', ['gpl', 'gpl-2.0', 'gpl-3.0', 'lgpl-*', 'agpl-3.0', 'mpl-2.0', 'epl-*',
                  'eupl-1.1', 'osl-3.0', 'odbl', 'gfdl', 'cc-by-sa-*']),
    ('restricted-use', ['openrail', 'openrail++', '*-openrail-m',
                        'bigscience-bloom-rail-1.0', 'llama2', 'llama3*', 'gemma',
                        'deepfloyd-if-license', 'apple-ascl', 'other']),
    ('non-commercial', ['cc-by-nc-*', 'cc-by-nc-sa-*']),
]
# Strictness rank; a child may not rank below its strictest parent. A no-derivatives
# licence on the child itself is the strictest; as a parent it refuses every child.
RANK = {'permissive': 0, 'copyleft': 1, 'restricted-use': 2, 'non-commercial': 3,
        'no-derivatives': 4}
UNLISTED_CLASS = 'restricted-use'


def licence_class(licence: str) -> tuple[str, bool]:
    """Return (class, listed). Licences not in the table are restricted-use."""
    for name, patterns in LICENCE_CLASSES:
        if any(fnmatchcase(licence, p) for p in patterns):
            return name, True
    return UNLISTED_CLASS, False


def p5_violation(child_class: str, parent_classes: dict[str, str]) -> str | None:
    """Return a reason string if P5 fails, else None."""
    for parent, cls in parent_classes.items():
        if cls == 'no-derivatives':
            return f'parent {parent} is no-derivatives'
    if child_class == 'unknown':
        return None  # cannot be checked; allowed and counted separately
    known = {p: c for p, c in parent_classes.items() if c != 'unknown'}
    if not known:
        return None
    strictest = max(known, key=lambda p: RANK[known[p]])
    if RANK[child_class] < RANK[known[strictest]]:
        return f'{child_class} child of {known[strictest]} parent {strictest}'
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tree(path: Path) -> tuple[list[str], dict[str, dict]]:
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    order = [r['model_id'] for r in rows]
    tree = {}
    for r in rows:
        r['_parents'] = r['parents'].split(';') if r['parents'] else []
        r['_relations'] = r['relations'].split(';') if r['parents'] else []
        tree[r['model_id']] = r
    return order, tree


def topological(models: list[str], tree: dict[str, dict], position: dict[str, int]) -> list[str]:
    """Kahn's algorithm; among ready models the one earliest in hf_tree.csv goes first."""
    selected = set(models)
    waiting = {m: sum(p in selected for p in tree[m]['_parents']) for m in models}
    children = collections.defaultdict(list)
    for m in models:
        for p in tree[m]['_parents']:
            children[p].append(m)
    ready = [(position[m], m) for m in models if waiting[m] == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        _, m = heapq.heappop(ready)
        result.append(m)
        for c in children[m]:
            waiting[c] -= 1
            if waiting[c] == 0:
                heapq.heappush(ready, (position[c], c))
    if len(result) != len(models):
        raise RuntimeError('plan contains a cycle')
    return result


def build(order: list[str], tree: dict[str, dict]):
    position = {m: i for i, m in enumerate(order)}
    classes, unlisted = {}, collections.Counter()
    for m in order:
        cls, listed = licence_class(tree[m]['license'])
        classes[m] = cls
        if not listed:
            unlisted[tree[m]['license']] += 1

    # Parents-first pass in longest-path depth order, as in hf_lineage.classify.
    ranked = sorted((m for m in order if tree[m]['depth'] != ''),
                    key=lambda m: (int(tree[m]['depth']), position[m]))
    clean, exclusions = set(), {}
    for m in ranked:
        row = tree[m]
        if row['status'] != 'ok':
            exclusions[m] = ('hub', row['status'], '')
            continue
        if ZERO in (row['weights_hash'], row['data_ref_hash']):
            exclusions[m] = ('hub', 'zero_hash', '')  # P2; hf_lineage should prevent this
            continue
        blocked = [p for p in row['_parents'] if p not in clean]
        if blocked:
            exclusions[m] = ('policy', 'ancestor_violation', ';'.join(blocked))
            continue
        reason = p5_violation(classes[m], {p: classes[p] for p in row['_parents']})
        if reason:
            exclusions[m] = ('policy', 'P5_licence', reason)  # a natural violation
            continue
        clean.add(m)
    for m in order:
        if tree[m]['depth'] == '':
            exclusions[m] = ('hub', tree[m]['status'], '')  # cycle
    plan = topological([m for m in order if m in clean], tree, position)
    return plan, exclusions, classes, unlisted


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def plan_rows(plan: list[str], tree: dict[str, dict], classes: dict[str, str]) -> list[dict]:
    index = {m: i for i, m in enumerate(plan)}
    rows = []
    for m in plan:
        r = tree[m]
        rows.append({
            'plan_index': index[m],
            'model_id': m,
            'depth': r['depth'],
            'n_parents': r['n_parents'],
            'parents': r['parents'],
            'parent_indices': ';'.join(str(index[p]) for p in r['_parents']),
            'relations': r['relations'],
            'license': r['license'],
            'licence_class': classes[m],
            'datasets': r['datasets'],
            'data_ref_hash': r['data_ref_hash'],
            'weights_hash': r['weights_hash'],
            'meta_hash': r['meta_hash'],
            'repo_sha': r['repo_sha'],
            'publisher': m.split('/', 1)[0],
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--tree', type=Path, default=ROOT / 'data' / 'hf_tree.csv')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()

    order, tree = read_tree(args.tree)
    plan, exclusions, classes, unlisted = build(order, tree)
    rows = plan_rows(plan, tree, classes)

    excluded = [{
        'model_id': m,
        'depth': tree[m]['depth'],
        'n_parents': tree[m]['n_parents'],
        'parents': tree[m]['parents'],
        'license': tree[m]['license'],
        'stage': stage,
        'reason': reason,
        'detail': detail,
    } for m in order if m in exclusions for stage, reason, detail in [exclusions[m]]]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / 'registration_plan.csv', PLAN_FIELDS, rows)
    write_csv(args.out_dir / 'plan_exclusions.csv', EXCLUSION_FIELDS, excluded)

    multi = [r for r in rows if int(r['n_parents']) > 1]
    meta = {
        'input': {'path': args.tree.resolve().relative_to(ROOT).as_posix()
                  if args.tree.resolve().is_relative_to(ROOT) else str(args.tree),
                  'sha256': sha256_file(args.tree), 'n_models': len(order)},
        'order_rule': 'topological (all parents first); ties broken by hf_tree.csv row order',
        'n_plan': len(rows),
        'plan_per_depth': dict(sorted(collections.Counter(r['depth'] for r in rows).items())),
        'n_multi_parent': len(multi),
        'max_parents': max((int(r['n_parents']) for r in rows), default=0),
        'n_roots': sum(r['n_parents'] == '0' for r in rows),
        'licence_classes': dict(collections.Counter(r['licence_class'] for r in rows)
                                .most_common()),
        'allowlist_size': len({r['data_ref_hash'] for r in rows}),
        'n_publishers': len({r['publisher'] for r in rows}),
        'excluded_per_reason': dict(collections.Counter(
            f"{e['stage']}:{e['reason']}" for e in excluded).most_common()),
        'n_natural_violations': sum(e['reason'] == 'P5_licence' for e in excluded),
        'unlisted_licences': dict(unlisted.most_common()),
        'fallback_rule': 'switch to microsoft/phi-2 if n_multi_parent < 30 (measurement plan §2.4)',
        'fallback_needed': len(multi) < 30,
    }
    meta_path = args.out_dir / 'registration_plan_meta.json'
    meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    main()
