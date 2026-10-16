### **Research Proposal: Blockchain-Based AI Model Registry & Lineage Auditability**

#### **1. Research Gap**

While Merkle-DAG off-chain constraint evaluation and hybrid smart-contract model registries have been evaluated for static, single-version machine learning pipelines, **nobody has empirically compared their verification latency, gas costs, and lineage lookup overhead during continuous multi-version fine-tuning across 20+ sequential transfer-learning model iterations.**

---

#### **2. Research Questions**

**Main Research Question:** How do off-chain Merkle-DAG constraint enforcement and direct on-chain smart-contract registries compare in terms of verification latency, on-chain execution cost (gas), and lineage audit throughput when recording and validating an AI model's iterative lineage across continuous fine-tuning cycles?

**Sub-Questions:**

1. **SQ1 (Gas Execution & State Footprint):** How does the gas cost and state-storage growth of recording model lineage scale for Merkle-DAG root anchoring versus direct on-chain contract state updates as the lineage tree depth increases across 20 sequential model versions?
2. **SQ2 (Verification Latency & Throughput):** What is the trade-off in end-to-end verification latency and query throughput when verifying model-dataset lineage under off-chain Open Policy Agent (OPA) attestation versus smart-contract on-chain constraint validation during automated pipeline deployment?
3. **SQ3 (Tamper Detection & Auditability):** Under simulated lineage tampering (e.g., intermediate dataset substitution or unauthorized fine-tuning parent modification), what are the false-positive rates and detection times for both approaches when reconstructing lineage integrity from a deployed target model back to its original source pre-training checkpoint?

---

#### **3. Main Evaluation Table Caption**

**Table 1: Comparative Performance, Execution Cost, and Auditability Metrics of Merkle-DAG Off-Chain Policy Enforcement vs. Direct On-Chain Smart-Contract Model Registry Across 20 Sequential Fine-Tuning Iterations.**

> **Caption:** Comparative evaluation of (1) Merkle-DAG off-chain constraint enforcement via Open Policy Agent (OPA) and (2) direct Solidity smart-contract registry anchoring on an EVM-compatible local testnet (Hardhat/Anvil) across 20 sequential fine-tuning iterations on ResNet-50 and Vision Transformer (ViT-Base) model architectures. Metrics are reported per model version \(v \in {1, 2, \dots, 20}\) and averaged across 50 independent experimental runs. Evaluated variables include:
> 
> - **On-Chain Gas Cost per Version Update (Gwei)** (deployment vs. execution gas);
> - **Total On-Chain State Growth (KB)** (cumulative ledger footprint);
> - **Lineage Verification Latency (ms)** (time required to recompute and verify cryptographic parent hashes \(h(M_v) = H(h(M_{v-1}) \parallel h(D_v) \parallel \text{meta})\) back to root checkpoint \(M_0\));
> - **Audit Query Throughput (TPS)** (transactions processed per second under concurrent read/write loads of \(N = 10, 50, 100\) clients); and
> - **Tamper Detection Accuracy (%) & Detection Latency (ms)** under three controlled attack vectors (unauthorized weight modification, training dataset CID/hash replacement, and parent version hash spoofing).
