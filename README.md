# Blockchain AI Provenance

Research Track Project Topic:
Blockchain for AI provenance / model registry. Implement a contract that records model versions, training-data hashes and ownership on-chain, so an AI model's lineage is auditable

A research prototype for recording and verifying AI model versions on an Ethereum-compatible blockchain. Model files and datasets stay off-chain; a Solidity registry stores their hashes, metadata references, publisher addresses, and timestamps.

The demo uses the real Iris dataset bundled with scikit-learn and two independently trained logistic-regression models. It demonstrates file integrity and version history, not fine-tuning ancestry.

## Features

- Model registration and owner-only version publication.
- Append-only version records and one-step ownership transfer.
- SHA-256 verification of datasets, model artifacts, metadata, and the referenced training script.
- Offline tamper-detection experiments and hashing benchmarks.
- Transaction gas collection for deployment and registration experiments.

The registry records claims made by an address. It does not prove that a model was trained on the declared data, establish legal ownership, or guarantee off-chain file availability.

## Project structure

| Path | Contents |
| --- | --- |
| `src/ModelRegistry.sol` | `AIModelRegistry` contract |
| `test/` | Foundry contract tests |
| `scripts/` | Training, hashing, verification, and experiment tools |
| `data/`, `models/` | Preserved Iris training data, model artifacts, and metadata |
| `results/`, `figures/` | Experiment logs, raw measurements, and plots |
| `docs/`, `literature/` | Conventions, research proposal, and reference material |

## Setup

Requires Python 3.11 and Foundry (`forge`, `cast`, and optionally `anvil`). Run commands from the repository root.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt

# Install the Solidity test dependency if lib/forge-std is absent.
forge install foundry-rs/forge-std
forge build
forge test -vv
```

The Foundry configuration uses Solidity 0.8.24. Building produces the verifier ABI at `out/ModelRegistry.sol/AIModelRegistry.json`.

## Off-chain experiments

The repository includes the training CSV, both model versions, and their metadata. Use those preserved files for verification. `python scripts/train_demo.py` regenerates them and may change their hashes.

```bash
python scripts/hash_file.py models/v1/model.joblib
python scripts/tamper_demo.py data/iris_train.csv
python scripts/experiment_integrity.py \
  data/iris_train.csv \
  models/v1/model.joblib models/v1/metadata.json \
  models/v2/model.joblib models/v2/metadata.json \
  --trials 30 --seed 42 --output results/integrity.csv
python scripts/benchmark_hashing.py \
  --sizes-mib 1 10 50 --repeats 10 --output results/hash_benchmark.csv
python scripts/plot_results.py
```

These commands compare against local baseline hashes and regenerate experiment outputs. They do not query the blockchain. The committed integrity run detected 150/150 modifications and accepted 5/5 original files; environment details are in [results/environment.json](results/environment.json).

## Blockchain workflow

Read the [registry conventions](docs/registry-conventions.md) before registering files. They define hash placement, metadata fields, and version numbering.

1. Run the contract tests, then deploy `src/ModelRegistry.sol:AIModelRegistry` to local Anvil or Sepolia.
2. Call `registerModel(name, metadataURI)` and obtain the model ID from the `ModelRegistered` event. Registration creates an empty model; IDs start at **0**.
3. As the owner, call `registerVersion(modelId, weightsHash, trainingDataHash, versionURI, artifactHashes)` for each preserved version. Put its metadata hash in `artifactHashes[0]`.
4. Verify both versions, then verify altered copies to demonstrate failure. Recheck v1 after adding v2 to demonstrate historical preservation.

For Sepolia, configure an RPC endpoint and import a test wallet into an encrypted keystore. Use test ETH and keep keys and RPC credentials out of Git.

```bash
export SEPOLIA_RPC_URL='https://YOUR_SEPOLIA_RPC_ENDPOINT'
cast wallet import provenance-demo --interactive
forge create src/ModelRegistry.sol:AIModelRegistry \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-demo --broadcast
export REGISTRY_ADDRESS='0xYOUR_DEPLOYED_CONTRACT_ADDRESS'
```

After registration, verify v1 using the actual model ID:

```bash
python scripts/verify.py --model-id 0 --version 1 \
  --data data/iris_train.csv \
  --artifact models/v1/model.joblib \
  --metadata models/v1/metadata.json
```

For v2, use `--version 2` and the files in `models/v2/`. The CLI uses human version numbers: v1 maps to contract index 0. It checks file hashes and metadata consistency, returning `VERIFIED` (exit 0) or `NOT VERIFIED` (exit 1) for completed comparisons. Connection, configuration, and lookup errors also cause failure.

For Anvil, pass `--rpc-url http://127.0.0.1:8545 --chain-id 31337` to the verifier. Its default chain is Sepolia (`11155111`). The verifier reads local files; it does not download metadata from registered URIs.

## Transaction measurements

Save the contract address, chain ID, transaction hashes, block numbers, UTC dates, and tool versions. Deployment, model registration, v1 registration, and v2 registration are separate transactions.

```bash
python scripts/collect_gas.py \
  --tx 'deploy:0xDEPLOYMENT_TX_HASH' \
  --tx 'register_model:0xMODEL_TX_HASH' \
  --tx 'register_v1:0xV1_TX_HASH' \
  --tx 'register_v2:0xV2_TX_HASH' \
  --output results/gas.csv
python scripts/plot_results.py
```

The plotter creates `figures/hash_time.png` and, when `results/gas.csv` exists, `figures/transaction_gas.png`. The gas chart is labeled for Sepolia; keep local simulation results separate. Gas used and hashing time measure different costs.

## License

[MIT](LICENSE).
