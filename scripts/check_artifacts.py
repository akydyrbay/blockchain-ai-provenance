#!/usr/bin/env python3
"""Check the preserved Iris demo files against the hash manifest and metadata.

Checks, without retraining anything:
  1. every file in results/artifact_hashes.txt still has its recorded SHA-256;
  2. each metadata.json points at the right dataset, model artifact and training
     script hashes, and has the expected version and hyperparameters;
  3. the training CSV has the documented shape (120 rows, 4 features, 40 per class).

Exits 0 if every check passes and 1 otherwise. A missing file counts as a failure.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hash_file import sha256_bytes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'results' / 'artifact_hashes.txt'
DATA = ROOT / 'data' / 'iris_train.csv'
TRAINING_SCRIPT = ROOT / 'scripts' / 'train_demo.py'
EXPECTED_VERSIONS = {1: 1.0, 2: 0.25}  # version -> regularization C
EXPECTED_HEADER = ['sepal length (cm)', 'sepal width (cm)', 'petal length (cm)',
                   'petal width (cm)', 'target']


def digest(path: Path) -> str:
    return '0x' + sha256_bytes(path).hex()


def check_manifest(results: list) -> None:
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        rel, expected = line.split()
        path = ROOT / rel
        if not path.exists():
            results.append((f'manifest: {rel}', False, 'file missing'))
            continue
        actual = digest(path)
        results.append((f'manifest: {rel}', actual == expected, actual))


def check_metadata(results: list) -> None:
    data_hash = digest(DATA)
    script_hash = digest(TRAINING_SCRIPT)
    for version, c_value in EXPECTED_VERSIONS.items():
        folder = ROOT / 'models' / f'v{version}'
        meta = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
        checks = {
            'version': meta.get('version') == version,
            'parent_version': meta.get('parent_version') == version - 1,
            'training_data_sha256': meta.get('training_data_sha256') == data_hash,
            'artifact_sha256': meta.get('artifact_sha256') == digest(folder / 'model.joblib'),
            'training_code_sha256': meta.get('training_code_sha256') == script_hash,
            'hyperparameters': meta.get('hyperparameters') == {
                'C': c_value, 'max_iter': 1000, 'random_state': 42, 'solver': 'lbfgs'},
        }
        for field, ok in checks.items():
            results.append((f'v{version} metadata: {field}', ok, ''))


def check_dataset(results: list) -> None:
    with DATA.open(newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    classes = Counter(row[-1] for row in body)
    results.append(('dataset: header', header == EXPECTED_HEADER, ','.join(header)))
    results.append(('dataset: 120 rows', len(body) == 120, str(len(body))))
    results.append(('dataset: 5 columns per row', all(len(r) == 5 for r in body), ''))
    results.append(('dataset: 40 rows per class', classes == {'0': 40, '1': 40, '2': 40},
                    str(dict(sorted(classes.items())))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, help='also write the report to this file')
    args = parser.parse_args()

    results: list = []
    check_manifest(results)
    check_metadata(results)
    check_dataset(results)

    lines = [f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  {detail}' if detail else '')
             for name, ok, detail in results]
    passed = sum(ok for _, ok, _ in results)
    lines.append(f'{passed}/{len(results)} checks passed')
    report = '\n'.join(lines)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + '\n', encoding='utf-8')
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
