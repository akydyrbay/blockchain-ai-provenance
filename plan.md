# Project completion and paper plan

Status reviewed: 20 November 2026. Scope revised on 17 November 2026. The current workload and measurement protocol are in the [dated measurement plan](docs/measurement_plan.md). The checked items below have repository evidence. The original Sepolia deployment predates the comparison contracts.

The five comparison configurations completed the full TinyLlama and synthetic Anvil workloads. See the [full benchmark summary](results/anvil/2026-11-20-full/summary/registrations.csv) and [synthetic scaling results](results/anvil/2026-11-20-synthetic/summary/depth_scaling.csv). The IEEE draft in `paper/` compiled successfully with the generated result tables.

## 1. Scope

### 1.1 What the project is

The project is a **comparative study of three ways to record and enforce AI-model provenance on an EVM chain, evaluated on a real Hugging Face lineage tree**:

| ID | Design | Contract | Status |
|---|---|---|---|
| D1 | Direct on-chain storage registry (baseline) | `src/ModelRegistry.sol` (`AIModelRegistry`), extended with parent links and `getLineage` | Implemented with parents-first registration and deduplicated lineage reads |
| D2 | On-chain policy registry: policy rules P1–P5 checked in Solidity | `src/PolicyRegistry.sol` | Implemented and exercised in the local smoke replay |
| D3 | Merkle-DAG anchoring with off-chain OPA policy and on-chain attestation check | `src/DAGAnchor.sol` + `policy/provenance.rego` + attester script | Implemented and exercised in the local smoke replay |

Policy rules, identical in Solidity and Rego: **P1** every parent is registered and not revoked; **P2** the weights and dataset hashes are non-zero and the weights hash is not a duplicate; **P3** the dataset hash is on an allowlist; **P4** the publisher holds the publisher role; **P5** the licence is compatible with the parents' licences.

D3 node hash: `h(M_v) = H(h(W_v) ‖ h(D_v) ‖ sort(h(M_p) for every parent p) ‖ h(meta_v))`. Each node commits to its whole ancestry, and merges (several parents) are represented natively.

The existing Iris demo (two logistic-regression models, 150/150 offline mutations detected) is kept as the **end-to-end, byte-level verification example**. It is not the main workload.

### 1.2 Research questions

| ID | Research question | Required evidence |
| --- | --- | --- |
| SQ1 | Gas and new on-chain state (bytes) per registration for D1/D2/D3, and how they scale with lineage depth and number of parents | Transaction receipts from the full-tree replay; state diffs; synthetic depth chain of 1–20 |
| SQ2 | Policy-decision latency (OPA vs. on-chain check), lineage verification latency and gas back to the root by depth, and audit throughput (models/s, one auditor) | Timed runs (5 warm-up + 30 measured repetitions), `VerifyProbe`-style in-contract gas, full-tree audit run |
| SQ3 | Which design refuses, and which detects, weight-hash modification, dataset-hash substitution, parent spoofing, a non-allowlisted dataset and an unauthorized publisher; detection rate, false-positive rate on clean records and detection latency | Attack harness run against every design on the registered tree; clean-record controls |

The Iris demo also supports SQ3 at the file level (altered bytes are rejected by the verifier against real contract records).

### 1.3 Workload

- **Real tree:** the committed Hugging Face snapshot of `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (finetune, adapter, quantized and merge). The pull contains 2,630 records including external roots. The policy-clean plan contains 2,317 records at depths 0–3 and 62 multi-parent records. The ResNet-50 trial had one merge. The selection and limits (6,000 models, depth 12) are recorded in the measurement plan.
- **Weight hashes:** the SHA-256 values the Hub publishes for each weight file. For a seeded sample of 10 models (seed 42), download the weights and confirm local SHA-256 equals the Hub value.
- **Synthetic depth chain:** a hash-only chain of depth 1–20, always labelled synthetic in figures and text.

### 1.4 Removed from the original proposal

| Removed | Reason |
|---|---|
| ResNet-50 / ViT fine-tuning, 20 sequential training iterations | Training adds compute without changing what is measured; the real Hub tree supplies genuine lineage, and the synthetic chain covers depth up to 20 |
| 50 independent runs | Anvil gas is deterministic, so one replay is exact; only timing is repeated (5 warm-up + 30 measured) |
| Concurrent TPS with N = 10/50/100 clients | On an automining local node this measures Anvil, not the design. Replaced by single-auditor audit throughput |
| Gas reported in Gwei | Gas is measured in gas units; ETH fees only with a stated date and price |
| "Nobody has compared …" | Not established by a literature review; replaced by a positioned gap statement |

### 1.5 How this differs from ai-provenance-registry

| Aspect | ai-provenance-registry | blockchain-ai-provenance (this project) |
|---|---|---|
| Question | Gas cost vs. which guarantees each design gives up | **Where policy is enforced** (on-chain vs. OPA off-chain) vs. cost, latency, throughput and tamper handling |
| Designs | Storage, event-only, Merkle **batch** | Storage registry, **on-chain policy** registry, **Merkle-DAG + OPA attestation** |
| Lineage | One parent; merges excluded | **Multiple parents**; merges included |
| Lineage verification in Merkle design | One proof per generation | One inclusion check on the anchored head (the node hash commits to the ancestry) |
| Tree | `SmolLM2-360M` (language model, 1,369 models) | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (language model) |
| Metrics | Gas, verification gas, executed guarantee checks | Gas, **state bytes**, **latency (ms)**, **audit throughput**, **prevention vs. detection rates** |
| Depth | Real tree only (≤ 4) | Real tree plus **synthetic depth 1–20** |
| Real files | None (Hub hashes only) | Iris end-to-end demo plus a downloaded weight-hash sample |

Do not copy code or results from ai-provenance-registry. Cite it as related work.

### 1.6 Scope agreement checklist

- [ ] Both team members agree on this scope and check it against the course requirements.
- [ ] If the original proposal was formally approved, get the instructor's agreement to the revision.
- [x] Update `docs/proposal.md` to match the revised scope (17 November 2026).
- [x] Confirm the base model and pull limits after the trial pull; record them in a dated measurement plan (`docs/measurement_plan.md`) **before** measuring.

Do not report latency, throughput, state-growth or comparative claims until the corresponding experiments are implemented and recorded.

## 2. What is already available

| Component | Current status | Remaining evidence or work |
| --- | --- | --- |
| Solidity registry (future D1) | The original contract was deployed and verified. The current D1 source adds atomic registration and immutable model parent links | Parent links and `getLineage` are implemented for D1. For a public check use a **new deployment**; keep the existing Sepolia deployment as evidence of the original contract |
| Primary-hash validation | The committed contract rejects either missing primary hash and has regression tests | Keep the regression tests when changing code |
| Foundry dependency | `forge-std` is pinned to v1.17.0, revision `f3dae6e6ee381f25eb6a246f7da9b85c91a68219`; the submodule is initialized and setup documents the pinned checkout | Keep the pin |
| Contract tests and coverage | Default discovery now uses `forge_test/`; a fresh working-tree run passed all 18 tests with five fuzz tests × 256 cases, seed `0x2a`. Earlier saved coverage reports 100% for the registry | Extend for D1 changes; add suites for D2 and D3 |
| Local gas report | `forge_test_outputs/gas_report.txt` records test execution costs | Keep separate from real transaction gas |
| Static analysis | `results/slither/report.json` says `success: true`, `error: null`, and `results: {}` | Comparative reports and coverage are in `results/validation/comparative/` |
| Python verifier | Aligned with the current five-field model tuple and `getVersionCount()` | Extend to lineage verification for D1–D3 |
| Local integration | Seven checks passed against a temporary Anvil deployment | Add a reusable harness |
| Demo artifacts | All five files match the hash manifest; the metadata's dataset, weights and training-code hashes also match | Keep these exact bytes for the end-to-end demo |
| Offline integrity | CSV has 150 mutation trials and five clean controls: 150 detections, five accepted controls | Keep raw observations; document the mutation method |
| Hashing benchmark | 30 observations: 10 repetitions at each of 1, 10 and 50 MiB | Add dispersion summaries; supports SQ2's off-chain hashing cost |
| Sepolia deployment | Deployed on 8 November; saved receipt rechecked through public RPC on 13 November | Normalize into the experiment manifest |
| Explorer verification | Etherscan labels the source an exact match, compiler 0.8.24, optimization on with 200 runs | Link in README and paper |
| HF lineage pipeline | Committed workload, exclusions, synthetic chain and weight checks | Reuse the snapshots in every replay |
| D2, D3 contracts, OPA policy, attester | Implemented and exercised locally | Retain proof records for independent verification and repeat static analysis |
| Replay, timing, controlled validation | Full and synthetic benchmark results and controlled checks are saved | Assemble remaining publication tables and validate the release |
| Python dependencies | One `requirements.txt` pins runtime and static-analysis dependencies | Hub pull uses the existing HTTP dependency. `eth-account` is already pinned. Local validation used OPA 1.4.2 |
| Documentation and credentials | Setup corrected; RPC credential redacted from current files | Account owner must revoke/rotate the exposed credential |

### Confirmed deployment (original contract)

| Field | Recorded value |
| --- | --- |
| Network / chain ID | Ethereum Sepolia / `11155111` |
| Contract | `0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71` |
| Deployment transaction | `0x83297ce46d1e6f3e8edd9df82b5a6f34861accfb379312eb2180dce4982d1d36` |
| Deployment block / UTC time | `12089282` / `2026-11-08T07:48:00Z` |
| Receipt status | Successful (`0x1`), matching the saved receipt |
| Observed transaction gas | `7,428,102` gas units |
| Effective gas price / fee | `525,000,006` wei per gas / `0.003899753594568612` test ETH |
| Live state on review | `totalModels() = 0`; the accompanying head query returned block `12126583` |

Sources: [saved Sepolia broadcast](broadcast/Deploy.s.sol/11155111/run-latest.json), [teammate's notes](docs/notes.md), and the [public explorer](https://sepolia.etherscan.io/address/0xed1fe6c0edbd2d0eb424c5fe8b543fa7f5ff7d71#code). The files under `broadcast/Deploy.s.sol/1/` contain no transaction hash or receipt, so they are not evidence of a mainnet deployment.

This deployment is of the **pre-extension** contract. The D1/D2/D3 comparison uses new deployments. Do not mix the two ABIs or addresses.

### Teammate's changes since the previous plan

- `1aa4a95`: pinned Foundry submodule and lock file.
- `f75f38b`: formatted the contract without changing behaviour.
- `e9da6c3`, `50ae2fb`: kept functional, coverage and gas logs; moved tests to `forge_test/`.
- `842591a`: Slither output; replaced the Python requirements with the analysis environment.
- `50049b3`: `scripts/Deploy.s.sol` and Sepolia deployment artifacts.
- `5f7c92d`: deployment and Etherscan verification in `docs/notes.md`.
- `768d134`: merged these changes.

### Account-owner follow-up

The RPC credential previously copied into `docs/notes.md` has been redacted from current files. The Alchemy account owner must still revoke/rotate it, because historical commits keep the original value. Coordinate any history rewrite with the team.

## 3. Remaining implementation work

Suggested split: **contract lead** = teammate (D1–D3 contracts, tests, deployments); **verification/evaluation lead** = you (HF pipeline, OPA/attester, replay, timing, attacks, figures). Both review integration results and paper claims.

### Phase A — Freeze a reproducible baseline

Owner: both.

- [x] Commit the contract fix, expanded tests, verifier adjustment and updated conventions.
- [x] Pin `forge-std` (v1.17.0).
- [ ] Account owner: revoke/rotate the exposed RPC credential.
- [x] Record Python, OS, CPU, compiler settings, Foundry, OPA and dependency versions in `results/validation/comparative/environment.json`.
- [x] Recompute the five Iris artifact hashes against `results/artifact_hashes.txt` (all matched on 13 November).
- [x] Document the Iris source, stratified 80/20 split, seed 42, 120 training rows, CSV serialization and model parameters.

### Phase B — Measurement plan before measuring

Owner: both. **Complete before Phase E.**

- [x] Trial pull of the original `microsoft/resnet-50` candidate; record the size, depth profile, relations, number of multi-parent models and the share of models with Hub weight hashes.
- [x] Fix the base model, limits, relation types, inclusion/exclusion rules, policy rules P1–P5, the allowlist and licence-compatibility table, attack definitions, timing protocol (5 warm-up + 30 measured, median/IQR), synthetic-chain depths (1–20), and the Sepolia sample size.
- [x] Write these into `docs/measurement_plan.md` with a dated change log. Later changes need a dated note giving the reason.

### Phase C — Hugging Face lineage pipeline

Owner: verification/evaluation lead.

- [x] `scripts/hf_lineage.py`: breadth-first walk from the base model over finetune/adapter/quantized/merge relations; write `data/hf_tree.csv` (model id, parents, relation, depth, weight-file SHA-256 values, declared datasets, licence) and `data/hf_tree_meta.json` (pull time UTC, limits, whether truncated, library versions).
- [x] Derive per model: the weights hash (a deterministic combination of the weight-file SHA-256 values), the dataset-reference hash (hash of the declared dataset names; a documented limitation) and the metadata hash.
- [x] Inclusion rules: keep multi-parent models; exclude models with no weight hashes, unreadable cards, or a missing ancestor. Record each exclusion with its reason.
- [x] Order the registration plan topologically (all parents before children).
- [x] Weight-hash sample check: download 10 seeded models and compare the local SHA-256 with the Hub value.
- [x] `scripts/synthetic_chain.py`: a hash-only chain of depth 1–20 (and a small merge fan-in case), labelled synthetic.
- [x] Commit the pulled tree; the experiments reuse the committed CSV rather than the live Hub.

### Phase D — Contracts and the OPA policy path

Owner: contract lead (contracts), verification/evaluation lead (OPA/attester).

- [x] **D1** `AIModelRegistry`: add `parentIds` (array) per version or model, a parent-existence check, and `getLineage(id)` (walks all ancestors, deduplicated). Keep owner-only publication, append-only versions and ownership transfer.
- [x] **D2** `PolicyRegistry`: the same record as D1, plus P1–P5 enforced in Solidity: revocation flag, duplicate-weights mapping, dataset allowlist and publisher role (admin-managed), and a licence-compatibility table. Custom errors per rule.
- [x] **D3** `DAGAnchor`: stores the anchored DAG root/head per batch with its submitter and timestamp; verifies the EIP-712 attestation signature of the configured OPA attester with `ecrecover`; `verifyInclusion(nodeHash, publisher, proof, batchId)`. No full records on-chain.
- [x] `policy/provenance.rego`: P1–P5 in Rego, with OPA unit tests (`opa test`) mirroring the D2 Solidity tests rule for rule.
- [x] `scripts/attester.py`: builds the node, queries OPA, signs an allow decision (EIP-712), and builds node hashes and Merkle proofs.
- [x] `src/VerifyProbe.sol`: measures in-contract verification gas (`gasleft()` before and after) for D1/D2 lineage reads and D3 inclusion plus attestation checks.
- [ ] Foundry tests for all three contracts: every policy rule (accept and reject), events, multi-parent lineage, revocation, roles, attestation with a wrong signer, inclusion with a wrong proof, plus fuzz tests. Keep the existing 18 tests passing.
- [x] Equivalence test: for the same input set, D2 (Solidity) and OPA (Rego) give the same accept/reject decision for every case.
- [x] Rerun coverage and Slither on all three contracts and record tool versions. See `results/validation/comparative/`.

### Phase E — Replay and measurements

Owner: verification/evaluation lead. Main runs on local Anvil (chain 31337), with a fresh deployment per design.

- [x] `scripts/replay.py`: register the same topologically ordered plan under D1, D2 and D3; record `gasUsed` per transaction, the new storage bytes per transaction (state diff via `debug_traceTransaction` prestate diff mode), the D3 batch size, depth and number of parents → `gas.csv` in the run directory.
- [x] Repeat for the synthetic chain of depth 1–20 and the fan-in workloads. The run summary contains `depth_scaling.csv`.
- [x] Policy-decision latency: OPA decision time vs. D2's check through `eth_call`, 5 warm-up + 30 measured, over a seeded sample of records → `policy_latency.csv` in the run directory.
- [x] Lineage verification: from each sampled target back to the root, per design: wall time (ms) and in-contract gas (`VerifyProbe`), by depth on the real tree and the synthetic chain → `verify_latency.csv` and `verify_gas.csv` in the run directory.
- [x] Audit throughput: one auditor verifying every registered model sequentially, per design; report models/s and total time (repeat 5 times, median) → `audit_throughput.csv` in the run directory.
- [x] Gas decomposition: fit single-model registration gas against URI words, number of parents and a root indicator. Report coefficients and R² where the fit is identifiable.
- [x] Report on-chain gas and off-chain time in separate tables and figures.

### Phase F — Tamper and policy-violation harness

Owner: verification/evaluation lead; contract lead reviews.

- [x] Run the controlled integrity fixture in `scripts/registry_checks.py` against the committed trees. Test clean records, altered weights, changed dataset references, and a different existing parent for applicable records.
- [x] Test admission of independent candidates with an unknown parent, an unlisted dataset, or an unauthorized publisher. Use 100 seeded candidates per scenario. Revoked parents are tested in the separate Solidity/OPA equivalence fixture.
- [x] Save raw outcomes and per-case verification times under [the check runs](results/anvil/2026-11-20-checks/README.md). These are single timing observations per case.
- [x] Generate the paper tables for admission, detection and parent-case applicability from both validation runs. The generator rejects incomplete, duplicate or invalid observations.

### Phase G — Local integration and end-to-end demo

Owner: verification/evaluation lead.

- [x] `scripts/integration_demo.py` replays Iris v1/v2 against D1 and D2 and calls the byte verifier. The smoke replay covers a TinyLlama merge and its ancestors in D1–D3.
- [x] Check historical v1 after v2, rejection of altered dataset/weights/metadata copies, and ownership transfer through the Iris verifier. Foundry covers unauthorized appends.
- [x] Confirm the Iris verifier rejects a wrong chain and a missing model in both D1 and D2. See the [expanded scenarios](results/validation/iris-2026-11-24/scenarios.csv).
- [x] Save the Iris [scenario table](results/anvil/2026-11-20-iris/scenarios.csv) and logs. The demo starts and shuts down its local Anvil instance.

### Phase H — Sepolia check

Owner: contract lead; verification/evaluation lead checks independently.

- [x] Freeze the 32-model sample and verify the receipt comparison locally. See the [deployment runbook](docs/deployments.md).
- [x] Export D3 proof bundles and independently check a merge and its ancestors after reloading local chain state.
- [ ] Deploy D1, D2 and D3 to Sepolia; verify the sources on Etherscan.
- [ ] Replay a fixed prefix of the plan (size set in the measurement plan, including at least one merge model) under all three designs.
- [ ] Compare `gasUsed` with Anvil row by row → `results/sepolia/chain_check.json`. Report and explain any difference; do not remove it.
- [ ] Record addresses, transaction hashes, blocks, UTC times and the source commit in `docs/deployments.md`.

### Phase I — Figures, tables and release

Owner: both.

- [ ] Scripts generate every figure, table and quoted number from the raw CSVs (`scripts/make_figures.py`, `make_tables.py`, `make_numbers.py`).
- [x] Test the setup and four-model smoke replay from a [clean Python 3.11 clone](results/validation/clean-checkout-2026-11-21/report.json).
- [ ] Have each team member reproduce the setup independently.
- [ ] Review generated files for credentials and machine-specific paths.
- [ ] Tag the implementation revision and identify the evidence revision.
- [ ] Prepare a demo: register a subtree under all three designs, show a policy refusal on D2 and an OPA denial on D3, rebuild a lineage to the root, and detect a spoofed parent.

## 4. Evidence package for the paper

Keep the existing evidence (`forge_test_outputs/`, `results/slither/report.json`, `broadcast/Deploy.s.sol/11155111/`, `results/integrity.csv`, `results/hash_benchmark.csv`). Proposed layout for new runs:

```text
data/
  hf_tree.csv  hf_tree_meta.json  synthetic_chain.csv
policy/
  provenance.rego  provenance_test.rego
results/
  validation/      # forge, opa test, coverage, slither logs + versions
  anvil/
    manifest.json gas.csv depth_scaling.csv policy_latency.csv
    verify_latency.csv verify_gas.csv audit_throughput.csv attacks.csv
    gas_model.json scenarios.csv
  sepolia/
    manifest.json gas.csv chain_check.json receipts/
  summaries/       # generated paper tables and numbers
figures/
  architecture.pdf tree_profile.pdf gas_per_model.pdf state_bytes.pdf
  depth_scaling.pdf policy_latency.pdf verify_latency.pdf attacks.pdf
paper/
  main.tex references.bib sections/
```

Every manifest records the run, source commit, tool versions (Foundry, solc, OPA, Python), seeds, commands, UTC time, input hashes (tree CSV), network, and contract addresses.

## 5. Paper format and page budget

The starter manuscript is in [paper/main.tex](paper/main.tex). Related work, references, results interpretation and the final abstract are author tasks.

Use **LaTeX** with the course-approved IEEE conference template. Word submissions are not allowed.

Suggested title: **Where Should Provenance Policy Live? On-Chain Enforcement versus OPA-Attested Merkle-DAG Anchoring for AI Model Lineage**.

Target about **13 pages including references**.

| Section | Target pages | Purpose |
| --- | ---: | --- |
| Title, abstract, keywords | 0.5 | Problem, three designs, key measured findings, limits |
| 1. Introduction | 1.0 | Motivation, contribution, SQ1–SQ3 |
| 2. Background and related work | 1.5 | ML provenance, blockchain registries, policy engines; position against ai-provenance-registry and the literature |
| 3. Requirements, policy and threat model | 1.0 | Actors, P1–P5, attacks A1–A3 and V1–V2, assumptions |
| 4. System design and implementation | 2.0 | D1, D2, D3, OPA/attester, node-hash construction, verifier |
| 5. Evaluation methodology | 1.5 | Tree, synthetic chain, replay, timing protocol, attack harness |
| 6. Results | 2.0 | SQ1–SQ3 |
| 7. Discussion, limitations, threats to validity | 1.5 | Trust shift to the attester, cost vs. guarantees, validity |
| 8. Conclusion and future work | 0.5 | Supported conclusions only |
| References | 1.5 | Sources actually read |
| **Total** | **13.0** | |

## 6. Detailed paper structure

### Abstract and keywords

Write last. State the problem, the three designs, the real HF tree, two or three measured findings (for example gas and state per design, verification latency at depth d, and which attacks each design prevents), and the main limitation (D3 moves trust to the OPA attester; Hub dataset hashes are name-based).

Keywords: AI provenance; model lineage; blockchain; policy enforcement; Open Policy Agent; Merkle-DAG.

### 1. Introduction

1. Problem: model families on public hubs branch and merge; auditors need to trace a deployed model back to its root and check that each step met policy.
2. Design question: enforce policy on-chain (transparent, costly) or off-chain with OPA and anchor commitments (cheap, but trust shifts to the attester)?
3. Contribution: three implemented designs with identical policy rules, a reproducible replay on a real TinyLlama lineage snapshot including merges, and a measured comparison of cost, latency, throughput and tamper handling.
4. SQ1–SQ3.

Do not claim to be the first blockchain model registry or the first such comparison.

### 2. Background and related work

- ML provenance and model management (ModelDB, pipeline provenance, model cards, datasheets).
- Blockchain provenance registries: what is anchored and where policy lives. Include ai-provenance-registry as the closest course-level comparison (storage/event/Merkle batch, single parent, gas vs. guarantees).
- Policy-as-code (OPA/Rego) and attestation.
- A comparison table with columns: lineage model (single/multi-parent), policy location, on-chain data, evaluation workload, metrics reported. Write "not reported" where a source gives no evidence.

### 3. Requirements, policy and threat model

Actors: publisher, governance admin (allowlist, roles), OPA attester, auditor, RPC provider, Hub/file host. Policy P1–P5. Attacks A1–A3 and violations V1–V2. Assumptions: trusted contract address and chain; for D3 the attester key is honest and uncompromised (this is the key trust difference, and it is discussed in §7); hashes do not prove that training happened.

### 4. System design and implementation

- 4.1 Architecture figure: Hub tree → hash derivation → (D1/D2 transaction) or (OPA → attester → D3 anchor) → auditor.
- 4.2 D1 and D2 data model and policy checks (field table, custom errors).
- 4.3 D3 node-hash construction, DAG anchoring, attestation format (EIP-712), inclusion proofs.
- 4.4 Lineage rebuild algorithm per design (pseudocode), including deduplication of shared ancestors in merges.
- 4.5 Verifier and the Iris end-to-end path.

### 5. Evaluation methodology

Setup table (versions, chain IDs, seeds, tree pull date and size, sample counts). Describe: the replay protocol (fresh deployment, same order); the state-diff method; the timing protocol (5 warm-up + 30 measured, median/IQR, machine details); the synthetic chain; audit throughput; the attack harness (prevention vs. detection, clean controls); and the Sepolia gas check.

### 6. Results

- **6.1 SQ1:** gas and state bytes per registration per design; scaling with depth (real tree and synthetic 1–20) and with number of parents; gas decomposition.
- **6.2 SQ2:** policy-decision latency (OPA vs. on-chain); lineage verification latency and gas by depth; audit throughput.
- **6.3 SQ3:** prevention/detection matrix (design × attack), detection and false-positive rates, detection latency; the Iris byte-level results (150/150, 5/5), kept separate.

End each subsection with a direct, bounded answer.

### 7. Discussion, limitations, threats to validity

- D3's cost savings versus the trust moved to the attester key and OPA service availability.
- D2's transparency versus the gas of on-chain policy and the cost of updating policy.
- One base model and one snapshot date; Hub metadata quality; dataset hashes based on names.
- Anvil timing on one machine; no concurrent-load measurement (out of scope by design).
- Synthetic depth chain versus real depth.
- Provenance claims versus actual training; key compromise; dishonest authorized publishers.
- Internal, external and construct validity.

### 8. Conclusion and future work

Answer SQ1–SQ3 from measured results only. Future work: multiple base models and snapshots, decentralized attesters (threshold signatures), dataset content hashes, L2 deployment, concurrent load on a public network.

## 7. Figures and tables to prepare

| Item | Content | Source |
| --- | --- | --- |
| Figure 1 | Architecture of D1/D2/D3 and the OPA path | Implementation |
| Figure 2 | HF tree profile: models per depth and relation, merges | `data/hf_tree.csv` |
| Figure 3 | Gas per registration by design (main figure) | `results/anvil/gas.csv` |
| Figure 4 | New state bytes per registration and cumulative | `results/anvil/gas.csv` |
| Figure 5 | Depth scaling 1–20 (gas and verification latency), synthetic | `depth_scaling.csv`, `verify_latency.csv` |
| Figure 6 | Policy-decision latency, OPA vs. on-chain | `policy_latency.csv` |
| Figure 7 | Prevention/detection matrix | `attacks.csv` |
| Table 1 | Main comparison table (proposal caption) | Generated summaries |
| Table 2 | Related-work comparison | Papers actually read |
| Table 3 | Policy rules P1–P5 in Solidity and Rego | Contracts and policy |
| Table 4 | Setup and sample counts | Manifests |
| Table 5 | Test, coverage and static-analysis summary | `results/validation/` |
| Table 6 | Sepolia vs. Anvil gas check | `chain_check.json` |

Generate plots with matplotlib and diagrams with TikZ. Keep full logs, addresses and hashes in the repository, not in the manuscript.