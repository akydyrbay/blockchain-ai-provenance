# Off-chain hashing benchmark

## Scope

This experiment measures SHA-256 hashing time over synthetic byte sequences of
1, 10 and 50 MiB. It is separate from the comparative Anvil replay.

## Reproduction

Use Python 3.11 and install the pinned `requirements.txt` dependencies in a virtual environment.

Run from the repository root:

1. python scripts/benchmark_hashing.py --sizes-mib 1 10 50 --repeats 10 --output results/hash_benchmark.csv
2. python scripts/plot_results.py

## Evidence

- results/hash_benchmark.csv: individual hashing measurements.
- results/hash_benchmark_summary.log: median and quartile summary.
- figures/hash_time.png: median hashing time by file size.
- results/environment.json: execution environment, random seed, and source revision.
- results/validation/environment.json: output of `python scripts/record_environment.py` (Python, OS, CPU, compiler settings, Foundry/OPA, packages).

## Limitations

Hashing times include file reading and may reflect filesystem cache effects. All repetitions are retained in the CSV.
