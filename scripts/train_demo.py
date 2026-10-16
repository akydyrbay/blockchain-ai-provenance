#!/usr/bin/env python3
"""Generate real, small ML models and immutable metadata for registry experiments."""
import csv
import json
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hash_file import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    (ROOT / 'data').mkdir(exist_ok=True)
    source = load_iris()
    X = source.data
    y = source.target
    indices = np.arange(len(y))
    train_idx, _ = train_test_split(
        indices, test_size=0.2, random_state=42, stratify=y
    )
    train_idx = np.sort(train_idx)
    # The exact CSV bytes are what the registry will attest to.
    data_file = ROOT / 'data' / 'iris_train.csv'
    with data_file.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow([*source.feature_names, 'target'])
        for i in train_idx:
            writer.writerow([*(format(float(value), '.8g') for value in X[i]), int(y[i])])

    for version, C in [(1, 1.0), (2, 0.25)]:
        output_dir = ROOT / 'models' / f'v{version}'
        output_dir.mkdir(parents=True, exist_ok=True)
        model = LogisticRegression(C=C, max_iter=1000, random_state=42, solver='lbfgs')
        model.fit(X[train_idx], y[train_idx])
        artifact_file = output_dir / 'model.joblib'
        joblib.dump(model, artifact_file, compress=3)

        metadata = {
            'name': 'iris-logistic-regression',
            'version': version,
            'parent_version': version - 1,
            'training_data_sha256': '0x' + sha256_bytes(data_file).hex(),
            'artifact_sha256': '0x' + sha256_bytes(artifact_file).hex(),
            'training_code_sha256': '0x' + sha256_bytes(Path(__file__)).hex(),
            'algorithm': 'sklearn.linear_model.LogisticRegression',
            'hyperparameters': {'C': C, 'max_iter': 1000, 'random_state': 42, 'solver': 'lbfgs'},
            'python_version': platform.python_version(),
            'scikit_learn_version': sklearn.__version__,
        }
        metadata_file = output_dir / 'metadata.json'
        metadata_file.write_text(
            json.dumps(metadata, sort_keys=True, indent=2, ensure_ascii=False) + '\n',
            encoding='utf-8'
        )
        print(f'v{version}:')
        for label, file in [('data', data_file), ('artifact', artifact_file), ('metadata', metadata_file)]:
            print(f'  {label:9s} 0x{sha256_bytes(file).hex()}  {file.relative_to(ROOT)}')
    print('Files created. Keep the exact registered artifact and metadata files for later verification.')


if __name__ == '__main__':
    main()
