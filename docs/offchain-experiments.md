# Off-chain provenance experiments

## Scope

This experiment generates two Iris logistic-regression model versions,
preserves their artifacts and metadata, and evaluates file-integrity
checking and SHA-256 hashing performance.

The models are trained independently with C=1.0 and C=0.25.
The parent_version field describes their registry version order;
it does not establish fine-tuning ancestry.

## Reproduction

Use Python 3.11 and install requirements-lock.txt in a virtual environment.

Run:
1. python scripts/train_demo.py
2. python scripts/experiment_integrity.py data/iris_train.csv models/v1/model.joblib models/v1/metadata.json models/v2/model.joblib models/v2/metadata.json --trials 30 --seed 42 --output results/integrity.csv
3. python scripts/benchmark_hashing.py --sizes-mib 1 10 50 --repeats 10 --output results/hash_benchmark.csv
4. python scripts/plot_results.py

Retraining may change serialized bytes. Preserve the committed originals
when comparing against their hashes or future blockchain records.

## Evidence

- results/artifact_hashes.txt: hashes of preserved artifacts.
- results/integrity.csv: individual clean and tampered observations.
- results/integrity_summary.log: observed detection totals.
- results/hash_benchmark.csv: individual hashing measurements.
- figures/hash_time.png: median hashing time by file size.
- results/environment.json: ex- results/environment.json: ex- results/
- requirements-lock.t- requirements-lock.t- requirements-lock.t- requirements-lock.t- requirepare against locally computed baseline has- requirements-lock.t- requirements-lock.t- requirements-lock.t- requirements-lock.t- requirepare against locally computed baseline has- requirements-lock.t- requirements-lock.t- requirements-lock.t- requireon- requirements-lock.t- requirements-lock.t- rurements remain pending contract integration.
