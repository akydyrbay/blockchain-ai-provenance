### **Research Proposal: Blockchain-Based AI Model Registry & Lineage Auditability**

*Revised 17 November 2026. This version replaces the original proposal. The change log at the end lists what was removed, what was added and why.*

#### **1. Research Gap**

Blockchain registries for AI provenance (for example ProML, IBIS, and the works in `literature/`) usually evaluate **one** on-chain design on a small synthetic workload, and they treat lineage as a single parent pointer.

Our literature review has not found an empirical comparison of **where provenance policy is enforced**: inside a smart contract, or off-chain by a policy engine (Open Policy Agent, OPA) whose decisions are committed to the chain through a hash-linked Merkle-DAG. We also have not found one that measures this on a **real public model family tree that includes multi-parent (merged) models**. This proposal addresses that question. We make no claim that "nobody has compared" these designs. Section 2 of the paper will position the work against the sources we actually read.

---

#### **2. Research Questions**

**Main Research Question:** For a real Hugging Face vision-model family tree, how do (D1) a direct on-chain storage registry, (D2) a smart contract that enforces provenance policy itself, and (D3) off-chain OPA policy enforcement anchored on-chain through a Merkle-DAG compare in on-chain cost, lineage verification latency and audit throughput, and in which tampering and policy violations each one prevents or detects?

**Sub-Questions:**

1. **SQ1 (Gas & State Footprint):** How much gas and how much new on-chain state (bytes) does each design use per registered model? How do these costs scale with lineage depth and with the number of parents, both on the real tree and on a controlled synthetic chain of depth 1–20?
2. **SQ2 (Verification Latency & Audit Throughput):** How long does it take to (a) evaluate the provenance policy for one registration (OPA decision vs. on-chain check) and (b) rebuild and verify a model's full lineage back to the root checkpoint, as a function of depth? How many models per second can one auditor verify across the whole tree?
3. **SQ3 (Tamper Prevention, Detection & Auditability):** Under three controlled attacks (weight-hash modification, training-dataset hash substitution, parent spoofing) and two policy violations (non-allowlisted dataset, unauthorized publisher), which design refuses the record at registration, which detects it at audit time, and with what detection rate, false-positive rate on clean records, and detection latency?

---

#### **3. Designs Compared**

All three designs register the same records, in the same order (parents first), with the same policy rules, each in a fresh deployment.

| ID | Design | Contract | Policy enforced | Lineage stored | Verification |
|---|---|---|---|---|---|
| D1 | Direct on-chain storage registry (baseline) | `AIModelRegistry`, extended with parent links | Only the basics: owner-only publication, non-zero hashes, parents must exist | Full record and parent IDs in contract storage | `getLineage` walks the parents on-chain |
| D2 | On-chain policy registry | `PolicyRegistry` (new) | Policy rules P1–P5 written in Solidity and checked on every registration | Full record and parent IDs in contract storage | As D1, plus an on-chain policy status |
| D3 | Merkle-DAG anchoring with OPA attestation | `DAGAnchor` (new) plus an off-chain OPA service | Rules P1–P5 written in Rego and evaluated by OPA before anchoring. The attester signs the decision and the contract checks the signature (EIP-712 / `ecrecover`) | Only the hash commitments: each DAG node commits to its parents' node hashes, and the contract stores the anchored root or head | Recompute the node-hash path off-chain, then make one on-chain inclusion check and one attestation check |

D3 node hash: `h(M_v) = H(h(W_v) ‖ h(D_v) ‖ sort(h(M_p) for every parent p) ‖ h(meta_v))`. One inclusion check on the anchored head therefore commits to the whole ancestry. Merge nodes are represented natively.

**Policy rules (identical in Solidity and Rego):** P1 every parent is already registered and not revoked; P2 the weights and dataset hashes are non-zero and the weights hash is not a duplicate; P3 the dataset hash is on a governance allowlist; P4 the publisher holds the publisher role; P5 the declared licence is compatible with the parents' licences.

---

#### **4. Data**

- **Real lineage tree:** the Hugging Face Hub descendants of **`microsoft/resnet-50`**, following the finetune, adapter, quantized and merge relations. This is a vision CNN family, deliberately different from the SmolLM2 language-model family used by ai-provenance-registry. The base model, depth and size limits are fixed and logged before any gas is measured.
- **Weight hashes:** the SHA-256 values the Hub publishes for each weight file, so no weights need to be downloaded. For a seeded sample of models, we download the weights and recompute the hashes to confirm they match the Hub's values.
- **Synthetic depth chain:** a hash-only chain of depth 1–20, labelled as synthetic, used only to measure how cost scales with depth beyond what the real tree contains.
- **End-to-end file demo:** the existing Iris dataset and two logistic-regression artifacts, used to demonstrate byte-level verification of real files.

---

#### **5. Main Evaluation Table Caption**

**Table 1: Cost, Latency, Audit Throughput and Tamper Handling of a Direct On-Chain Registry (D1), an On-Chain Policy Registry (D2), and OPA-Attested Merkle-DAG Anchoring (D3) on the `microsoft/resnet-50` Hugging Face Lineage Tree.**

> **Caption:** All three designs register the same parents-first sequence of models from the real `microsoft/resnet-50` family tree, each in a fresh deployment on a local Anvil chain (Solidity 0.8.24, optimizer 200 runs). A sample is replayed on Sepolia to check that gas matches. Values are reported per design, by lineage depth and by number of parents. Columns:
>
> - **Gas per registration (gas units)**, plus deployment gas. Fees in ETH are given only with a stated date and gas price;
> - **New on-chain state (bytes)** per registration and in total after the whole tree;
> - **Policy-decision latency (ms)**: OPA evaluation for D3 vs. the on-chain check through `eth_call` for D2;
> - **Lineage verification latency (ms) and gas**, from a target model back to the root checkpoint, by depth (real tree and synthetic depth 1–20). Timing is reported as median and IQR over 30 measured repetitions after 5 warm-up repetitions;
> - **Audit throughput (models/s)**: one auditor verifying every registered model in sequence; and
> - **Prevention and detection** under weight-hash modification, dataset-hash substitution, parent spoofing, a non-allowlisted dataset and an unauthorized publisher: whether the record is refused at registration, the detection rate and false-positive rate at audit time, and the detection latency (ms).

---

#### **6. Out of Scope**

- Training or fine-tuning neural networks (ResNet-50/ViT training, 20 fine-tuning iterations). The real Hub tree replaces this workload.
- 50 independent experimental runs. Gas on Anvil is deterministic, so a single replay is exact. Only timing measurements are repeated (Section 5).
- Concurrent multi-client throughput (N = 10/50/100). On a local, automining Anvil chain that would measure the node rather than the registry design.
- Proof that training actually happened, legal ownership, dataset content hashes (the Hub publishes only dataset names), and off-chain file availability.
