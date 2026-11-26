# Blockchain AI Provenance

Research Track Project Topic:
Blockchain for AI provenance / model registry. Implement a contract that records model versions, training-data hashes and ownership on-chain, so an AI model's lineage is auditable

A research prototype that compares three ways to record and enforce AI model provenance on an Ethereum-compatible blockchain: direct on-chain storage (D1), policy enforced in Solidity (D2), and off-chain Open Policy Agent decisions anchored as attested Merkle commitments (D3). Model files and datasets stay off-chain; the registries store hashes, parent links, metadata references and publisher addresses. The designs are evaluated on the Hugging Face lineage tree of `TinyLlama/TinyLlama-1.1B-Chat-v1.0` and a synthetic depth and fan-in workload.

## Features

- Model registration with parent links, owner-only version publication and append-only version records.
- Provenance policy rules P1--P5 implemented in both Solidity and Rego.
- Merkle-DAG batch anchoring with EIP-712 attestations and independent proof-bundle audits.
- Replay, timing, tamper-detection and admission experiments on Anvil, plus a paired Sepolia sample.

The registry records claims made by an address. It does not prove that a model was trained on the declared data, establish legal ownership, or guarantee off-chain file availability.

## Project structure

| Path | Contents |
| --- | --- |
| `src/` | `AIModelRegistry` (D1), `PolicyRegistry` (D2), `DAGAnchor` (D3), the controlled placement pair in `PlacementRegistry.sol`, and `VerifyProbe` |
| `policy/` | Rego policy and OPA tests for D3 |
| `forge_test/` | Foundry contract tests |
| `scripts/` | Lineage collection, replay, verification, summary and plotting tools |
| `data/` | Hugging Face lineage snapshot, registration plan and synthetic workload |
| `results/`, `figures/` | Experiment logs, raw measurements, the architecture figure, and generated paper tables (`figures/tables/`) |
| `docs/`, `literature/` | Measurement plan, research proposal and reference material |

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

`requirements.txt` pins the Python dependencies for the replay, verification, plotting, and static analysis. The Foundry configuration uses Solidity 0.8.24 and discovers tests in `forge_test/`. Building produces the verifier ABI at `out/ModelRegistry.sol/AIModelRegistry.json`. See [validation and deployment notes](docs/notes.md) for coverage, gas reports, and static analysis. `python scripts/record_environment.py` writes the environment record to `results/validation/environment.json`.

## Hugging Face lineage data

The comparative study replays the Hub family tree of `TinyLlama/TinyLlama-1.1B-Chat-v1.0`. The rules (hashes, exclusions, policy configuration) are fixed in the [measurement plan](docs/measurement_plan.md). The pulled tree is committed, so experiments never read the live Hub.

```bash
python scripts/hf_lineage.py            # Hub walk -> data/hf_tree.csv, data/hf_tree_meta.json (~1 h; set HF_TOKEN to go faster)
python scripts/registration_plan.py     # policy-clean, parents-first plan -> data/registration_plan.csv, plan_exclusions.csv
python scripts/synthetic_chain.py       # synthetic depth chain 0-20 and fan-in 1/2/4/8 -> data/synthetic_chain.csv
python scripts/weight_spot_check.py --dry-run   # show the seeded 10-model sample and its download size
python scripts/weight_spot_check.py     # download and hash it -> results/anvil/weight_spot_check.csv
```

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
the synthetic scaling figure (`synthetic_scaling.pdf`) are in
[figures/tables](figures/tables). The architecture figure
(`figures/architecture.pdf`) is drawn by `python scripts/plot_architecture.py`.

Use `python scripts/replay.py --mode checks --out results/anvil/my-checks` to
check altered weights, dataset references and parent links against a local
replay of the full workload. Each applicable case compares an altered input
with the original registration.

## Controlled experiments

Two further runs separate policy placement from the other architectural
choices and compare verification procedures of equal scope.

```bash
# C-Sol vs C-OPA: same contract storage, one publisher transaction per model,
# same storage verifier; only the admission decision moves (Solidity vs OPA).
python scripts/placement_replay.py --mode full --out results/anvil/my-placement

# Adds the D3 full-ancestry audit (every ancestor's proof and attestation) and
# the summed gas of every call each verifier makes.
python scripts/replay.py --mode full --full-ancestry --out results/anvil/my-ancestry
python scripts/replay.py --mode synthetic --full-ancestry --batched-target --out results/anvil/my-ancestry-synthetic
# D3-only: the target check sent through the same batched JSON-RPC transport.
python scripts/replay.py --mode full --full-ancestry --batched-target --configuration D3-1 \
  --configuration D3-16 --configuration D3-128 --out results/anvil/my-target-batched

python scripts/summarize_controlled.py --placement results/anvil/my-placement \
  --ancestry results/anvil/my-ancestry --target-batched results/anvil/my-target-batched \
  --out results/anvil/my-controlled-summary \
  --csv-out results/anvil/my-controlled-summary
python scripts/plot_ancestry_scaling.py results/anvil/my-ancestry-synthetic --out ancestry_scaling.pdf
```

The saved runs are `results/anvil/2026-11-26-placement-full`,
`results/anvil/2026-11-26-ancestry-full`,
`results/anvil/2026-11-26-target-batched-full` and
`results/anvil/2026-11-26-ancestry-synthetic`. They ran on a different host
from the November 20 runs, so compare their timings only with each other.

## License

[MIT](LICENSE).
