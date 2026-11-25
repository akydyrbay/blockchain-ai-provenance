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
| `forge_test/` | Foundry contract tests |
| `scripts/` | Training, hashing, verification, and experiment tools |
| `data/`, `models/` | Preserved Iris training data, model artifacts, and metadata |
| `results/`, `figures/` | Experiment logs, raw measurements, and plots |
| `docs/`, `literature/` | Conventions, research proposal, and reference material |

## Setup

Requires Python 3.11 and Foundry (`forge`, `cast`, and optionally `anvil`). Run commands from the repository root.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Retrieve the exact Solidity test dependency pinned by this repository.
git submodule update --init --recursive
forge build
forge test -vv
```

`requirements.txt` pins the Python dependencies for training, verification, plotting, and static analysis. The Foundry configuration uses Solidity 0.8.24 and discovers tests in `forge_test/`. Building produces the verifier ABI at `out/ModelRegistry.sol/AIModelRegistry.json`. See [validation and deployment notes](docs/notes.md) for coverage, gas reports, and static analysis.

## Off-chain experiments

The repository includes the training CSV, both model versions, and their metadata. Use those preserved files for verification. `python scripts/train_demo.py` regenerates them and may change their hashes.

```bash
python scripts/check_artifacts.py      # preserved files still match their hashes
python scripts/record_environment.py   # writes results/validation/environment.json
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

How the data and models were produced is documented in [docs/iris-dataset.md](docs/iris-dataset.md). These commands compare against local baseline hashes and regenerate experiment outputs. They do not query the blockchain. The committed integrity run detected 150/150 modifications and accepted 5/5 original files; environment details are in [results/environment.json](results/environment.json).

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

## Hugging Face lineage data

The comparative study replays the Hub family tree of `TinyLlama/TinyLlama-1.1B-Chat-v1.0`. The rules (hashes, exclusions, policy configuration) are fixed in the [measurement plan](docs/measurement_plan.md). The pulled tree is committed, so experiments never read the live Hub.

```bash
python scripts/hf_lineage.py            # Hub walk -> data/hf_tree.csv, data/hf_tree_meta.json (~1 h; set HF_TOKEN to go faster)
python scripts/registration_plan.py     # policy-clean, parents-first plan -> data/registration_plan.csv, plan_exclusions.csv
python scripts/synthetic_chain.py       # synthetic depth chain 0-20 and fan-in 1/2/4/8 -> data/synthetic_chain.csv
python scripts/weight_spot_check.py --dry-run   # show the seeded 10-model sample and its download size
python scripts/weight_spot_check.py     # download and hash it -> results/anvil/weight_spot_check.csv
```

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

## Comparative Anvil replay

Install OPA 1.4.2 alongside Foundry and the pinned Python environment.
The runner starts both services on loopback, uses fresh Anvil instances,
and derives deterministic accounts for local testing. It does not use `.env`.

```bash
opa test policy
python scripts/replay.py --mode smoke --out results/anvil/my-smoke
python scripts/replay.py --mode full --out results/anvil/my-full
python scripts/replay.py --mode synthetic --out results/anvil/my-synthetic
python scripts/summarize_replay.py results/anvil/my-full --out results/anvil/my-full/summary
```

The saved November 20 results include the [full TinyLlama benchmark](results/anvil/2026-11-20-full/summary/registrations.csv)
and the [synthetic workload](results/anvil/2026-11-20-synthetic/summary/depth_scaling.csv).
The smoke run uses a merge and all its ancestors. A completed full or synthetic run
includes receipt gas and storage diffs, policy and lineage timings, an in-contract
verification gas probe, and five full audit passes. The manifest records the
input, source file hashes, tools and run parameters. Registration gas excludes
deployment and policy configuration, which get their own rows. The D1/D2 probe
times the on-chain lineage query. The D3 probe times the inclusion and signature
checks. Use the wall-clock results for end-to-end verification.

The D3 attester is driven by a single local replay process with an in-memory index.
A persistent audit data store and publisher authentication are deployment concerns.
The licence policy compares the declared classes from the benchmark plan.

The manuscript is maintained on Overleaf. Its generated table inputs and
Figure 1 (`synthetic_scaling.pdf`) are in [docs/paper-tables](docs/paper-tables).

Use `python scripts/replay.py --mode checks --out results/anvil/my-checks` to
check altered weights, dataset references and parent links against a local
replay of the full workload. Each applicable case compares an altered input
with the original registration. Use
`python scripts/integration_demo.py --out results/anvil/my-iris` for the
preserved Iris byte checks through the D1/D2 version interface.

## License

[MIT](LICENSE).
