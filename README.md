# blockchain-ai-provenance

## Research Track Project Topic 
Blockchain for AI provenance / model registry. Implement a contract that records model versions, training-data hashes and ownership on-chain, so an AI model's lineage is auditable

This is a reproducible, **hash-based AI model provenance registry** on Ethereum Sepolia. The registry stores an append-only series of versions per model, each containing SHA-256 hashes for dataset, model artifact, and metadata. It records the publisher address and timestamp, supports two-step owner transfer, and provides independent verification.

## Scope and important limitations

- The contract records **claims by an Ethereum address**; it does not prove copyright, training history, legal ownership, or training-data permission.
- SHA-256 is computed using Python's standard library. Never implement a new cryptographic primitive.
- Contract records are immutable as deployed; the current model owner may append versions, and ownership can be transferred. Under Ethereum's consensus assumptions, old records remain auditable.
- File names, paths, and model weights are **not** stored on-chain. Preserve artifact bytes off-chain so verification remains possible. Do not upload private datasets to a public repository.
- For versions 2+, predecessor is previous version of **the same model**. This starter does not model cross-project or cross-model inheritance.

## Split between two people

**Person 1**: `src/`, `test/`, `foundry.toml`, unit tests, Sepolia deployment, transaction receipts, and `results/gas.csv`.

**Person 2**: `scripts/`, `data/`, `models/`, metadata, local/chain verification, integrity and hashing experiments, `figures/`.

Each person works on a branch, creates frequent substantive commits, and reviews the other's pull requests. Both collaborate on integration and paper.

## 0. Setup

Tested Python source syntax and offline hashing/integrity experiment, but Solidity compilation and live Sepolia deployment **must be run on a computer with Foundry installed**. Use macOS/Linux, Git, Foundry, and Python **3.11**.

Install Foundry from its official source:

```bash
curl -L https://foundry.paradigm.xyz | bash
# Open a fresh shell or follow Foundry's shell PATH message.
foundryup
forge --version
cast --version
```

From the extracted project directory:

```bash
git init
forge install foundry-rs/forge-std
# forge-std will be recorded as a Git submodule and pinned by the repository commit.
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip freeze > requirements-lock.txt
forge build
forge test -vv
```

If `forge install` complains about the project state, confirm `git init` ran, Git is installed, and no `lib/forge-std` directory is left over from a failed install. If the computer lacks Python 3.11, install it before making the virtual environment.

## 1. Generate the two AI model versions (Person 2)

```bash
python scripts/train_demo.py
```

This creates `data/iris_train.csv`, `models/v1/model.joblib`, `models/v1/metadata.json`, `models/v2/model.joblib`, `models/v2/metadata.json`. The example uses sklearn's built-in Iris data, with `random_state=42` and two different logistic-regression regularization strengths (`C=1.0`, `C=0.25`). Both model versions use the same training CSV. The generated binary artifacts should be retained and committed for this public, non-sensitive demonstration. If you retrain, the serialized artifact's byte hash may change even with the same parameters: do **not** use an old blockchain record with newly generated files.

Each metadata JSON includes the code hash, training-data hash, artifact hash, hyperparameters, library version and `parent_version` (0 for v1; 1 for v2). Its SHA-256 is independently registered on-chain. Keep the original JSON bytes.

```bash
python scripts/hash_file.py data/iris_train.csv
python scripts/hash_file.py models/v1/model.joblib
python scripts/hash_file.py models/v1/metadata.json
```

Hashes print as `0x` plus 64 hexadecimal characters, matching the Solidity `bytes32` ABI.

## 2. Contract tests (Person 1)

```bash
forge build
forge test -vv
forge test --gas-report | tee results/forge-gas-report.txt
forge snapshot
```

The Solidity tests cover initial registration, owner-only append, immutable historical records, zero-hash rejection, missing records, two-step transfer, and refusal of invalid owners. Do not deploy until the entire suite passes. Add fuzz tests if time permits.

## 3. Configure Sepolia (both; deployment led by Person 1)

Sepolia chain ID is `11155111`. Obtain **test ETH only** for a fresh test-only wallet from a current Sepolia faucet; do not use a wallet that holds real assets. Never commit keys, keystores, a real `.env`, or secrets.

```bash
cast wallet import provenance-demo --interactive
# Type the private key at the protected prompt and choose an encryption password.
export SEPOLIA_RPC_URL='https://ethereum-sepolia-rpc.publicnode.com'
cast chain-id --rpc-url "$SEPOLIA_RPC_URL"
# Expected output: 11155111
```

Check wallet address printed when importing and send test ETH to that address. If the public RPC is rate-limited, get an endpoint from Alchemy or Infura. Keep its key private.

Deploy:

```bash
forge create src/ModelRegistry.sol:ModelRegistry \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-demo --broadcast
```

Read the deployed contract address from the output and record **deployed address, deployment transaction hash, block number, compiler and Foundry versions, date, and chain ID** in a README experiment log (no secrets). Set the correct address:

```bash
export REGISTRY_ADDRESS='0xREPLACE_WITH_REAL_DEPLOYED_ADDRESS'
cast call "$REGISTRY_ADDRESS" 'nextModelId()(uint256)' --rpc-url "$SEPOLIA_RPC_URL"
# Fresh registry returns 1
```

View it in https://sepolia.etherscan.io/address/YOUR_ADDRESS . Use `forge verify-contract` separately if required by your instructor; it may require an explorer API key. Contract deployment itself does not require Etherscan verification.

## 4. Register version 1 (Person 1 sends; Person 2 supplies hashes)

Run these commands from the repository root **after** model generation and deployment:

```bash
DATA_HASH=$(python scripts/hash_file.py data/iris_train.csv)
V1_ARTIFACT_HASH=$(python scripts/hash_file.py models/v1/model.joblib)
V1_METADATA_HASH=$(python scripts/hash_file.py models/v1/metadata.json)

cast send "$REGISTRY_ADDRESS" \
  'registerModel(string,bytes32,bytes32,bytes32)' \
  'iris-logistic-regression' "$DATA_HASH" "$V1_ARTIFACT_HASH" "$V1_METADATA_HASH" \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-demo
```

**Save the transaction hash.** If this was the first write to a new registry, the model ID is **1**. Otherwise look up the `ModelRegistered` event in the transaction receipt; do not assume a model ID if multiple people are registering concurrently. Confirm:

```bash
cast call "$REGISTRY_ADDRESS" \
  'getModel(uint256)(string,address,address,uint256)' 1 \
  --rpc-url "$SEPOLIA_RPC_URL"
```

## 5. Independently verify version 1 (Person 2)

```bash
python scripts/verify.py --model-id 1 --version 1 \
  --data data/iris_train.csv \
  --artifact models/v1/model.joblib \
  --metadata models/v1/metadata.json
```

The CLI reads the Solidity ABI from `out/ModelRegistry.sol/ModelRegistry.json`, queries the specified chain, hashes the three **raw file byte streams**, compares them to the on-chain records, and validates the metadata's version/parent/data/artifact/training-code fields. It exits **0 for VERIFIED** and **1 for NOT VERIFIED**. It checks the configured chain ID and contract address to avoid a false comparison against another network.

## 6. Append version 2, then verify (both)

```bash
V2_ARTIFACT_HASH=$(python scripts/hash_file.py models/v2/model.joblib)
V2_METADATA_HASH=$(python scripts/hash_file.py models/v2/metadata.json)

cast send "$REGISTRY_ADDRESS" \
  'addVersion(uint256,bytes32,bytes32,bytes32)' \
  1 "$DATA_HASH" "$V2_ARTIFACT_HASH" "$V2_METADATA_HASH" \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-demo

python scripts/verify.py --model-id 1 --version 2 \
  --data data/iris_train.csv \
  --artifact models/v2/model.joblib \
  --metadata models/v2/metadata.json

# Verify historical version 1 STILL works after updating to version 2:
python scripts/verify.py --model-id 1 --version 1 \
  --data data/iris_train.csv \
  --artifact models/v1/model.joblib \
  --metadata models/v1/metadata.json
```

**Save the v2 transaction hash.** Historical values do not change. The graph is v1 → v2, where the parent of v2 is v1.

## 7. Tamper detection (Person 2)

The following does not modify the original files:

```bash
python scripts/tamper_demo.py data/iris_train.csv
python scripts/tamper_demo.py models/v1/model.joblib
python scripts/experiment_integrity.py \
  data/iris_train.csv models/v1/model.joblib models/v1/metadata.json \
  --trials 30 --seed 42 --output results/integrity.csv
```

The experiment performs one deterministic bit flip in each file for each trial, compares against the unmodified file's hash, and saves the individual observations. For a direct **on-chain** failure test:

```bash
cp data/iris_train.csv data/iris_train_tampered.csv
printf 'X' >> data/iris_train_tampered.csv
python scripts/verify.py --model-id 1 --version 1 \
  --data data/iris_train_tampered.csv \
  --artifact models/v1/model.joblib \
  --metadata models/v1/metadata.json
# EXPECTED: NOT VERIFIED, exit status 1
```

The `printf` adds a literal character, changing the file bytes and its hash. Delete the copied file afterward. Do not replace the original registered CSV.

## 8. Measure performance and gas (both)

```bash
# Local controlled benchmark; generated files are removed automatically
python scripts/benchmark_hashing.py --sizes-mib 1 10 50 \
  --repeats 10 --output results/hash_benchmark.csv
```

The first run may include cold file-cache effects; retain all repetitions. Record CPU/OS info and Python/library versions so others can interpret the results. Never invent measurements.

To collect on-chain gas costs from successful real Sepolia receipts, substitute your **three actual transaction hashes**:

```bash
python scripts/collect_gas.py \
  --tx 'deploy:0xYOUR_DEPLOYMENT_TX_HASH' \
  --tx 'register_v1:0xYOUR_REGISTRATION_TX_HASH' \
  --tx 'append_v2:0xYOUR_VERSION2_TX_HASH' \
  --output results/gas.csv
```

Generate graphs directly from the raw files:

```bash
python scripts/plot_results.py
# Outputs figures/hash_time.png and figures/transaction_gas.png
```

`gas_used` is EVM transaction gas, **not ETH**. The payable fee is `gas_used × effective_gas_price`, and is dependent on network conditions. Never claim Sepolia test ETH has a meaningful real-money cost. Hash input file size does not affect the `bytes32` payload size; therefore the corresponding on-chain fields remain fixed-size. To demonstrate that empirically rather than asserting a measured result, register multiple models with names of equal length and data from different-size files.

## 9. Optional ownership transfer demonstration (Person 1)

With a second test wallet, propose transfer from the current owner, then accept from the proposed new owner. The original owner can no longer append; a version's recorded publisher never changes.

```bash
cast send "$REGISTRY_ADDRESS" \
  'proposeOwnershipTransfer(uint256,address)' 1 0xSECOND_WALLET_ADDRESS \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-demo

# The second test wallet's own keystore alias is called provenance-recipient:
cast send "$REGISTRY_ADDRESS" \
  'acceptOwnership(uint256)' 1 \
  --rpc-url "$SEPOLIA_RPC_URL" --account provenance-recipient
```

This is optional for the minimal end-to-end result, but unit test coverage is mandatory.

## 10. Reproducibility and paper requirements

Commit source code, generated example dataset and safe-to-share artifacts, version-specific metadata, test code, pinned dependency list, raw experiment CSVs, plots, and README. Record the **chain ID, contract address, tx hashes, block numbers, dates (UTC), compiler version, Foundry version, random seed 42, Python version, and complete pip freeze**. Regenerate plots using a single script. Avoid committing caches, `.env`, wallet keys or real private datasets.

Core experiment questions:

1. Can a verifier detect altered training data, weights and metadata for registered model versions?
2. Can the system prevent unauthorized version changes while preserving historical records?
3. What transaction gas is consumed by deployment, initial registration and version addition, and how does off-chain SHA-256 time scale with file size?

Suggested figures: **transaction gas by operation**, **off-chain hashing time vs artifact size**, and an **integrity-test result table**. These measure different things; do not combine their y axes or claim gas and hashing time are directly comparable.

Success: Solidity tests pass, one Sepolia contract deployed, v1/v2 on-chain, both verify with preserved originals, altered copy fails verification, raw receipt data and plots checked into the repo, and both students have visible Git history.

Fallback by Week 10: if Sepolia or RPC/faucets fail, use **Anvil locally** with chain ID 31337 and the exact same Solidity and Python code. Document why the testnet experiment could not complete, save local transaction logs, and be explicit that local gas is a simulation, not observed Sepolia data.
