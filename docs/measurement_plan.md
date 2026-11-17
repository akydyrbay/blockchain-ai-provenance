# Measurement plan

Written **before any gas, latency or attack measurement**, after a trial pull of the
model tree. Change it only by adding a dated note to the change log at the bottom,
saying what changed and why. The research questions come from
[the proposal](proposal.md).

## 1. What is measured, in one paragraph

We register the same real Hugging Face model family under three designs: a direct
on-chain storage registry (D1), a contract that enforces provenance policy itself (D2),
and off-chain OPA policy anchored on-chain through a Merkle-DAG (D3). For each design
we measure the gas and new on-chain state per registration (SQ1); how long a policy
decision, a full lineage verification and an audit of the whole tree take (SQ2); and
which tampering and policy violations each design refuses at registration or detects at
audit time (SQ3). Policy rules are identical in Solidity and Rego, so the designs differ
only in *where* the rules run and *what* is stored on-chain.

## 2. Data

### 2.1 Model tree

| Item | Decision |
|---|---|
| Source | Hugging Face Hub API, through `scripts/hf_lineage.py` |
| Base model | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (chosen by the trial pull and survey in §2.4; to be confirmed by both team members) |
| Relations followed | finetune, adapter, quantized, merge (`base_model:` tags and card `base_model`) |
| Limits | `--max-models 6000 --max-depth 12`. The walk must finish untruncated (`"truncated": false`); if not, raise the limit and log it here before measuring |
| Final pull | Run once into `data/`, then committed. Every experiment reads the committed `data/hf_tree.csv`, never the live Hub |
| Trial pull and survey | `results/trial_pull/resnet-50/` and `results/trial_pull/candidate_survey.json` (17 November 2026), summarised in §2.4 |

### 2.2 Hashes per model

| Field | Rule |
|---|---|
| `weightsHash` | SHA-256 over the sorted lines `path:sha256\n` of every weight file the Hub publishes an LFS SHA-256 for. Weight files: `.safetensors .bin .pt .pth .h5 .msgpack .onnx .gguf .ckpt .keras .tflite .ot`, excluding `training_args`, `optimizer`, `scheduler`, `scaler`, `rng_state*`, `trainer_state` and anything under `runs/`, `checkpoint-*/`, `logs/` |
| `dataHash` | SHA-256 over the sorted declared dataset names joined by `\n`. If none are declared: SHA-256 of the fixed string `dataset:undeclared` |
| `metaHash` | SHA-256 of the canonical JSON `{"id", "repo_sha", "license", "relations"}` (sorted keys, no spaces) |
| D3 node hash | `h(M) = SHA-256(weightsHash ‖ dataHash ‖ sorted parent node hashes ‖ metaHash)` |

The dataset hash covers dataset **names**, not content, because the Hub publishes no
dataset content hashes. The sentinel for undeclared datasets is allowed by policy (§3)
and reported as a limitation.

**Weight-hash spot check:** download every weight file of 10 registrable models chosen
with seed 42, and confirm that the local SHA-256 equals the Hub value for every file →
`results/anvil/weight_spot_check.csv`.

### 2.3 Which models are registered

`hf_lineage.py` gives every model a status, in parents-first order (the first matching
rule wins): `cycle`, `info_unavailable`, `no_weight_hashes`, `duplicate_weights`,
`ancestor_excluded`, `ok`.

- **Merges are kept** with all their parents. A parent outside the family is added as
  an extra root (`external_root`); its own ancestors are not walked.
- **Policy-clean plan (main replay):** models with status `ok` that also pass P1–P5 under
  the configuration in §3, plus all their ancestors. All three designs register exactly
  this set, in the same topological order (all parents first, ties broken by BFS order),
  so gas and timing compare like with like.
- **Natural violations:** registrable models that fail a policy rule (e.g. a licence
  incompatible with a parent). They are left out of the main replay and reported in SQ3
  as real-world cases: refused by D2 and D3, accepted by D1.
- Excluded models are counted by reason in the paper; none are silently dropped.

### 2.4 Trial pull result (17 November 2026)

The base model was chosen in two steps, before any measurement.

**Step 1: full trial pull of `microsoft/resnet-50`** (`results/trial_pull/resnet-50/`,
limits 3,000 models / depth 10, not truncated, 1,043 requests):

| Item | Value |
|---|---|
| Models | 522 (incl. 1 external root) |
| Per depth | 0: 2 · 1: 514 · 2: 6 |
| Relations | finetune 503, quantized 15, adapter 2 |
| Multi-parent | 1 |
| Weight hashes published | 97.7 % |
| Registrable (`ok`) | 505 (96.7 %); excluded: 12 no weight hashes, 5 duplicate weights |
| Licences | apache-2.0 419, none 53, mit 37, others ≤ 3 each |

**Rejected:** the tree is only two levels deep (6 models at depth 2) and has a single
merge, so it cannot support the depth and multi-parent questions. A direct-children check
of 12 candidates found that vision families (ResNet-50, Swin-Tiny, ViT-Base) have **no
merges** at all; only language-model families do.

**Step 2: depth survey of three language-model candidates** (`--survey`, walk only,
limits 6,000 models / depth 12; `results/trial_pull/candidate_survey.json`):

| Candidate | Models | Truncated | Max depth | Per depth (0/1/2/3/4/5) | Multi-parent |
|---|---|---|---|---|---|
| `Qwen/Qwen2.5-0.5B` | ≥ 6,000 | **yes** | ≥ 3 | 1 / 1,463 / 4,503 / 33+ | ≥ 130 |
| `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | 2,586 | no | 4 | 1 / 2,388 / 176 / 19 / 2 | **91** |
| `microsoft/phi-2` | 1,628 | no | 5 | 1 / 1,480 / 114 / 22 / 10 / 1 | 20 |

**Decision: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`.** It has 4.5× more multi-parent models
than phi-2, and merges are what separates the Merkle-DAG design (D3) from the others. Its
walk is complete, and it is a different family from ai-provenance-registry's SmolLM2.
Qwen2.5-0.5B was rejected because its tree exceeds 6,000 models (it contains the whole
Qwen2.5-0.5B-Instruct family), which makes pulling and replaying it impractical. phi-2 is
the fallback if the final TinyLlama pull leaves fewer than 30 registrable multi-parent
models.

**Consequences for the design of the study:**
- Real trees are shallow in every candidate: at most 2 % of models sit at depth ≥ 3.
  Real-tree results are therefore reported by depth 0–4, and **depth scaling (SQ1, SQ2)
  is measured on the synthetic chain** (§2.5), always labelled synthetic.
- 78 of the 91 multi-parent models have at least one parent outside the family. These
  parents become extra roots (§2.3).
- Still to be measured at the final pull (Phase C): weight-hash coverage, registrable
  share and number of registrable merges. The final pull needs about 2 requests per model
  (≈ 5,200 requests, ≈ 55 minutes without a Hub token).

### 2.5 Synthetic workloads

Labelled **synthetic** in every figure and table.

- **Depth chain:** a linear chain of depth 1–20 (21 models) with hash-only records.
- **Fan-in:** one model with 1, 2, 4 and 8 parents (all registered roots).

## 3. Policy rules and configuration

The same five rules in Solidity (D2, `PolicyRegistry`) and Rego (D3, `policy/provenance.rego`).
A rule-by-rule equivalence test must show the same allow/deny decision on every test case
before any measurement.

| Rule | Check | Configuration used in the replay |
|---|---|---|
| P1 | Every parent is registered and not revoked | No revocations in the main replay; revocation is exercised in tests and SQ3 |
| P2 | `weightsHash` and `dataHash` are non-zero; `weightsHash` is not already registered | — |
| P3 | `dataHash` is on the dataset allowlist | Allowlist = every `dataHash` in the policy-clean plan (including the `dataset:undeclared` sentinel). V1 uses hashes not on it |
| P4 | The sender holds the publisher role | One publisher account per Hub namespace (the part of the model ID before `/`), derived deterministically from seed 42; the admin grants all of them the role before the replay. V2 uses an account without the role |
| P5 | The licence is compatible with every parent's licence (table below) | — |

**Licence classes for P5** (strictness order; a child may not be in a less strict class
than its strictest parent):

| Class | Rank | Licences |
|---|---|---|
| permissive | 0 | `apache-2.0`, `mit`, `bsd`, `bsd-2-clause`, `bsd-3-clause`, `isc`, `afl-3.0`, `wtfpl`, `unlicense`, `zlib`, `bsl-1.0`, `artistic-2.0`, `ecl-2.0`, `postgresql`, `ms-pl`, `cc0-1.0`, `pddl`, `odc-by`, `cc-by-2.0`, `cc-by-2.5`, `cc-by-3.0`, `cc-by-4.0` |
| copyleft | 1 | `gpl`, `gpl-2.0`, `gpl-3.0`, `lgpl-*`, `agpl-3.0`, `mpl-2.0`, `epl-*`, `eupl-1.1`, `osl-3.0`, `odbl`, `gfdl`, `cc-by-sa-*` |
| restricted-use | 2 | `openrail`, `openrail++`, `*-openrail-m`, `bigscience-bloom-rail-1.0`, `llama2`, `llama3*`, `gemma`, `deepfloyd-if-license`, `apple-ascl`, `other` (custom terms) |
| non-commercial | 3 | `cc-by-nc-*`, `cc-by-nc-sa-*` |
| no-derivatives | — | `cc-by-nd-*`, `cc-by-nc-nd-*`: any child of such a parent fails P5 |
| unknown | — | No licence, or `unknown`. Allowed (cannot be checked) and counted separately |

Licence IDs not in this table are classed as `restricted-use` and listed in the paper.

**Ownership:** D1 and D2 record the publishing account as owner; D3 records the batch
submitter and the attested publisher inside the node.

## 4. Designs and deployments

| | D1 `AIModelRegistry` (extended) | D2 `PolicyRegistry` | D3 `DAGAnchor` + OPA |
|---|---|---|---|
| Transactions | 1 per model | 1 per model | 1 per batch of *k* models |
| On-chain | Full record + parent IDs | Full record + parent IDs + policy state | Batch root, submitter, time, attester-signature check |
| Policy | Parent existence, non-zero hashes, owner-only | P1–P5 in Solidity | P1–P5 in Rego (OPA), EIP-712 attestation checked on-chain |
| Batch sizes | — | — | k = 1, 16, 128 |

- Every design and every D3 batch size gets a **fresh deployment** on a fresh Anvil
  (chain ID 31337), and the same plan is registered in the same order.
- Compiler: solc 0.8.24, optimizer on, 200 runs, EVM Cancun (`foundry.toml`).
- OPA: run locally as a server (`opa run --server`, pinned version recorded in
  `results/validation/environment.json`); the attester queries its HTTP decision API.

## 5. Metrics

| SQ | Metric | How it is measured | Output |
|---|---|---|---|
| 1 | Gas per registration | `gasUsed` from each receipt; D3: batch gas ÷ k | `results/anvil/gas.csv` |
| 1 | Deployment gas | Receipt of each contract deployment | `results/anvil/gas.csv` |
| 1 | New state bytes | `debug_traceTransaction` with `prestateTracer` in diff mode: storage slots that go from zero to non-zero × 32 bytes, reported per registration and cumulatively | `results/anvil/gas.csv` |
| 1 | Scaling with depth and number of parents | Gas and state against depth and `n_parents`, on the real tree and the synthetic workloads | `results/anvil/depth_scaling.csv` |
| 1 | Gas decomposition | Least-squares fit `gas = a + b·uri_words + c·n_parents + d·is_root` per design; report coefficients, R², largest residual | `results/anvil/gas_model.json` |
| 2 | Policy-decision latency | D3: OPA HTTP decision round trip (plus OPA's own `timer_rego_query_eval_ns` from `?metrics`). D2: `eth_call` round trip of the registration with the same inputs. Both on localhost | `results/anvil/policy_latency.csv` |
| 2 | Lineage verification latency | Wall time to rebuild and verify a model's full lineage to its root(s): D1/D2 `getLineage` + record reads and hash comparison; D3 recomputing node hashes off-chain + one on-chain inclusion check of the head + attestation check | `results/anvil/verify_latency.csv` |
| 2 | Lineage verification gas | In-contract `gasleft()` difference measured by `VerifyProbe` | `results/anvil/verify_gas.csv` |
| 2 | Audit throughput | One auditor verifying every model in the policy-clean plan in sequence; models/s and total time | `results/anvil/audit_throughput.csv` |
| 3 | Prevention | Whether the registration of an attacked record is refused, with the revert reason or OPA deny reason | `results/anvil/attacks.csv` |
| 3 | Detection | Whether lineage verification flags the attacked record; detection rate, false-positive rate on clean records, detection latency | `results/anvil/attacks.csv` |
| — | Anvil vs. Sepolia | Same transactions on both chains, `gasUsed` compared row by row | `results/sepolia/chain_check.json` |

Gas is reported in **gas units**. ETH fees are given only with a stated date and gas price.
On-chain gas and off-chain time are never plotted on the same axis.

## 6. Timing protocol (SQ2 and SQ3 latency)

- Every timed operation: **5 warm-up runs (discarded) + 30 measured runs**. Report median
  and interquartile range, with n.
- Clock: `time.perf_counter_ns()` in the Python harness.
- Same machine for every design, recorded in `results/validation/environment.json`; no
  other heavy processes; Anvil and OPA run on the same host.
- **Verification sample:** with seed 42, up to 10 models per depth from the policy-clean
  plan, plus every multi-parent model in it, plus the synthetic workloads.
- **Audit throughput:** the full policy-clean plan, 5 repetitions, median reported.
- These are local, single-machine latencies. Concurrent multi-client throughput is out of
  scope (proposal §6).

## 7. Attacks and policy violations (SQ3)

| ID | Attack | Prevention test (registration) | Detection test (audit) |
|---|---|---|---|
| A1 | Weight-hash modification | — (a new hash is just a new model; no rule can refuse it) | Verify the registered model against a weights hash with one byte flipped |
| A2 | Dataset-hash substitution | Register a copy of the record with another dataset hash that is not on the allowlist | Verify the registered model against a substituted dataset hash |
| A3 | Parent spoofing | (a) Register with a parent that was never registered; (b) register with a revoked parent | Verify the lineage when a different registered model is claimed as the parent |
| V1 | Non-allowlisted dataset | Register a new record whose `dataHash` is not allowlisted | — |
| V2 | Unauthorized publisher | Register from an account without the publisher role | — |

- **Detection set:** every model in the policy-clean plan, once per attack (view calls
  and off-chain checks only). **Clean controls:** the same models, unmodified; any
  rejection counts as a false positive.
- **Prevention set:** 100 models per attack, chosen with seed 42, each attempted from an
  `evm_snapshot` and then reverted, so the chain state stays identical between attempts.
- Each row records: design, attack, model, depth, prevented (y/n), detected (y/n),
  latency (ms) and evidence (revert reason, OPA deny reason or verifier output).
- RPC errors, timeouts and crashes are recorded as **operational errors**. They never
  count as detection.
- **Natural violations** found in the tree (§2.3) are reported alongside the controlled
  attacks.

## 8. Sepolia check

- Deploy D1, D2 and D3 (k = 1 and k = 16) to Sepolia and verify the sources on Etherscan.
- Replay the first 30 models of the policy-clean plan, plus the smallest ancestor-closed
  set containing one multi-parent model if the plan contains one.
- Success: every transaction uses the same `gasUsed` as the same transaction on Anvil.
  Any difference is reported in the paper with its explanation, not removed.
- Addresses, transaction hashes, block range and source commit → `docs/deployments.md`.
- RPC URL and keys come from the environment (`.env`, Foundry keystore) only.

## 9. Fixed decisions

- Same models, same order, a fresh deployment per design and per batch size.
- Main measurements on local Anvil, where gas is deterministic, so **each registration
  is measured once**. Only timings are repeated (§6).
- Seeds: 42 for all sampling and account derivation.
- Every number in the paper is generated from the files listed in §5 by a script.

## 10. Known limitations (go into the paper)

- One base model and one snapshot date; the Hub changes daily.
- Dataset hashes cover declared names, not content; most models declare no dataset.
- Hub metadata (base model, licence) is self-reported by uploaders.
- D3's guarantees rest on the honesty and key security of the OPA attester.
- Registration proves that an account *claimed* these hashes at a time; it does not prove
  that training happened.
- Latency comes from one local machine; there is no concurrent-load measurement.
- Sepolia is checked on a sample only.

## Change log

- 2026-11-17: first version, written after the trial pull and the candidate survey and
  before any measurement. Base model `microsoft/resnet-50` (used for the trial) replaced by
  `TinyLlama/TinyLlama-1.1B-Chat-v1.0` for the reasons in §2.4; limits set to 6,000 models /
  depth 12.
