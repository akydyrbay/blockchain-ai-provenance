## Literature Annotations

- Gunasekara, L., De Silva, D., Mills, N., Moraliyage, H., & Jennings, A. (2026). “Blockchain-Based Provenance for Artificial Intelligence Lifecycle Traceability.” IEEE ICIT 2026. DOI: 10.1109/ICIT64854.2026.11490281

Paper represents datasets, features, models, metrics, reviews, and approvals using a Merkle style provenance DAG and combines off-chain validation with smart-contract enforcement. It will be important for our bibliography because model registry idea can be positioned as a more focused implementation of AI lifecycle provenance centered specifically on models, datasets, versions, and ownership. 

- Abdu, S. M., Bewuketu, G., Getaneh, D., et al. (2026). “Trustworthy AI for Secure and Robust Machine Learning through Blockchain Enabled Data Integrity.” Discover Artificial Intelligence, 6, 486. DOI: 10.1007/s44163-026-01443-5

This paper proposes a blockchain enabled ML provenance architecture that stores only compact hashes and metadata on-chain while keeping datasets and model updates off-chain. Particularly relevant to us are its Merkle root dataset commitments, model hashes, digital signatures, model version records, and IPFS/off-chain storage, which are applicable to the architecture we could implement.

- Schlegel, M., & Sattler, K.-U. (2025). “Capturing End-to-End Provenance for Machine Learning Pipelines.” Information Systems, 132, 102495. DOI: 10.1016/j.is.2024.102495.

The authors identify limitations in existing ML artifact-management systems and propose MLflow2PROV, which builds provenance graphs from MLflow and Git activities using the W3C PROV model. This paper is useful for determining exactly what information constitutes ML lineage—datasets, experiments, pipeline steps, models, developers, Git changes, and relations between artifacts—before deciding which parts should be committed to blockchain.

- Vartak, M., Subramanyam, H., Lee, W.-E., Viswanathan, S., Husnoo, S., Madden, S., & Zaharia, M. (2016). “ModelDB: A System for Machine Learning Model Management.” HILDA ’16. DOI: 10.1145/2939502.2939516.

ModelDB is an early model-management system designed to automatically record ML models, pipelines, parameters, metrics, training data, and associated metadata. It is important because it establishes the traditional centralized model-registry approach against which our blockchain registry can be compared; our research question can examine what blockchain adds beyond a normal database-based registry—primarily tamper evidence, decentralized verification, and cryptographic ownership/attestation.

- Radanliev, P., Santos, O., Maple, C., & Atefi, K. (2026). “Operationalising Artificial Intelligence Bills of Materials for Verifiable AI Provenance and Lifecycle Assurance.” Frontiers in Computer Science, 8, 1735919. DOI: 10.3389/fcomp.2026.1735919

This paper proposes an AI Bill of Materials (AIBOM) containing model artifacts, model versions, training-data lineage, dependencies, execution environments, and cryptographic identifiers. Of particular interest is its use of SHA-256 model hashes and structured training-data references, which could help define the metadata schema for each model version in our smart contract.

- Mitchell, M., Wu, S., Zaldivar, A., et al. (2019). “Model Cards for Model Reporting.” Proceedings of FAT ’19, pp. 220–229. DOI: 10.1145/3287560.3287596.

Model Cards propose standardized documentation accompanying trained ML models, including intended uses, evaluation procedures, limitations, and performance characteristics. For our system, a model card could be stored off-chain while its hash and URI are associated with a particular immutable model version on-chain, extending the registry beyond merely storing a model binary hash. 

- Gebru, T., Morgenstern, J., Vecchione, B., et al. (2021). “Datasheets for Datasets.” Communications of the ACM, 64(12), 86–92.

This work proposes standardized documentation for datasets, covering their origin, composition, collection process, recommended use, and other characteristics. Since our proposed blockchain registry includes training-data hashes, this paper provides the conceptual basis for attaching meaningful provenance metadata to those hashes rather than simply recording an unidentified dataset digest.

- Liang, X., Shetty, S., Tosh, D. K., Kamhoua, C. A., Kwiat, K. A., & Njilla, L. (2017). “ProvChain: A Blockchain-Based Data Provenance Architecture in Cloud Environment with Enhanced Privacy and Availability.” IEEE/ACM CCGrid 2017, pp. 468–477. DOI: 10.1109/CCGRID.2017.8.

ProvChain is one of the important earlier works demonstrating how blockchain can maintain tamper-resistant provenance records without treating the blockchain as ordinary bulk storage. Although it deals with cloud files rather than AI models, its collection–storage–verification architecture and use of hashes/Merkle structures provide a blockchain provenance foundation that can be adapted to model artifacts and training datasets.

- Samuel, S., Löffler, F., & König-Ries, B. (2020). “Machine Learning Pipelines: Provenance, Reproducibility and FAIR Data Principles.”

This work examines ML experiment reproducibility and argues that source code and datasets alone are insufficient; additional pipeline provenance must be captured. It is useful for motivating why our registry should potentially record not only modelHash and datasetHash, but also items such as training configuration, code/version references, environment information, and relationships between model versions.

- Filatovas, E., Stripinis, L., Orts, F., & Paulavičius, R. (2024). "Advancing Research Reproducibility in Machine Learning through Blockchain Technology." *Informatica*, 35(2), 231–258. DOI: 10.15388/24-INFOR553

The paper proposes a community-driven, Hyperledger Fabric-based platform that stores ML experiment artifacts (models, datasets, parameters, hyperparameters, environment, hardware, and results) on-chain via a metadata schema and smart contracts to enable full reproducibility and auditability. It is important for our bibliography because it provides an experimentally validated blockchain architecture and metadata model that our work can build upon, extend, or contrast against when positioning our own reproducibility-focused design.

- Akther, A., Arobee, A., Adnan, A. A., Auyon, O., Islam, A. S. M., & Akter, F. (2025). "Blockchain as a Platform for Artificial Intelligence (AI) Transparency." arXiv preprint arXiv:2503.08699.

The paper surveys how blockchain's decentralization, immutability, and transparency can address AI's "black box" problem by recording AI decisions, data provenance, and model versions for auditability and regulatory compliance, while also discussing scalability, complexity, and integration challenges. It is important for our bibliography because it frames the broader AI transparency motivation and benefit/challenge landscape that our more focused reproducibility or provenance mechanism can be positioned within.

- Neulinger, A., & Sparer, L. (2025). "Fostering AI alignment through blockchain, proof of personhood and zero knowledge proofs." *Cluster Computing*, 28, 983. DOI: 10.1007/s10586-025-05729-8

The paper proposes a conceptual framework where AI alignment rules are encoded as immutable smart contracts on a blockchain governed by a Proof-of-Personhood consensus mechanism, using zk-STARKs for privacy-preserving, post-quantum-resistant identity verification and an AI shield to enforce rules in real time. It is important for our bibliography because it demonstrates a concrete blockchain-based governance and enforcement architecture for AI safety, offering a complementary perspective on how on-chain rules and cryptographic proofs can be used to constrain and audit AI systems.

- Wang, Q., Yu, G., Sai, Y., Bandara, H. M. N. D., & Chen, S. (2024). "Is Your AI Truly Yours? Leveraging Blockchain for Copyrights, Provenance, and Lineage." *IEEE International Conference on Blockchain* (Blockchain 2024). DOI: 10.1109/Blockchain62396.2024.00044

The paper presents IBIs, a blockchain-based framework with on-chain registries for datasets, licenses, and models plus off-chain signing services to dynamically manage copyright compliance, data provenance, and licensing updates across iterative AI retraining and fine-tuning workflows. It is important for our bibliography because it addresses the license lifecycle and ownership accountability dimensions of provenance that complement our model/dataset registry focus.

- Mu, X., Wang, Y., Zhang, Y., Zhang, J., Wang, H., Xiang, Y., & Yu, Y. (2024). "Model Provenance via Model DNA." arXiv preprint arXiv:2404.13672.

The paper introduces "Model DNA," a compact learned representation encoding a model's training data and input-output behavior, and uses a contrastive learning framework with a provenance classifier to determine whether a target model is derived from a source model via fine-tuning. It is important for our bibliography because it offers a content-based, ML-native alternative to ledger-based provenance, which we can contrast with our blockchain registry approach when justifying why cryptographic record-keeping is needed alongside technical provenance detection.

- Verginadis, Y., Patiniotakis, I., & Mentzas, G. (2025). "NFT-based Data Provenance for AI Transparency in Enterprise." *Procedia Computer Science* (CENTERIS 2025).

The paper proposes minting datasets as ERC-721 NFTs on a permissioned Ethereum network, where automated tools and human expert reviewers attach evaluation metadata on-chain while the data itself is stored off-chain via IPFS. It is important for our bibliography because it demonstrates a concrete NFT-based dataset certification and review workflow with attribute-based access control that we can position as a complementary data-level provenance mechanism to our model-centric registry.

- Mohit, A., Aggarwal, B., & Gondhalekar, C. (2024). "Provenance Verification of AI-Generated Images via a Perceptual Hash Registry Anchored on Blockchain."

The paper registers 64-bit perceptual hashes of AI-generated images at creation time in a blockchain-anchored registry, combining a Merkle Patricia Trie for on-chain commitments with off-chain BK-trees for Hamming-distance similarity search that survives resizing, compression, and minor edits. It is important for our bibliography because it shows how content-level fingerprints can be indexed and matched at scale, offering a concrete contrast to our metadata/registry approach for model and dataset provenance.

- Adeyinka, A. (2025). "Securing the AI Supply Chain: Using Blockchain For Verifiable AI Model Provenance on Government Clouds." *SAMRIDDHI: A Journal of Physical Sciences, Engineering and Technology*, 17(1), 29–35. DOI: 10.18090/samriddhi.v17i01.05

The paper presents a conceptual framework for anchoring datasets, training configurations, model checkpoints, and deployment instances on a blockchain to provide tamper-evident lifecycle provenance in government cloud AI supply chains. It is important for our bibliography because it maps provenance controls directly to policy frameworks such as NIST AI RMF, FedRAMP, ISO/IEC 42001, and the EU AI Act, which we can cite when justifying compliance-oriented design requirements.

- Sukumaran, S., Korath, A., & Arun, G. (2026). "Tamper-Evident Data and Model Provenance for IoT-Based Machine Learning Using Blockchain and Off-Chain Storage." *Information*, 17(5), 499. DOI: 10.3390/info17050499

The paper proposes a hybrid architecture that stores cryptographic hashes and metadata of IoT data batches, preprocessing outputs, and trained models on a permissioned blockchain while keeping large artifacts off-chain, with smart contracts enforcing verifiable linkage across the ML lifecycle. It is important for our bibliography because its simulated tamper-detection experiments with constant on-chain storage overhead provide a directly comparable evaluation baseline for lifecycle-level data–model provenance.

- Noh, S., & Rhee, K.-H. (2024). "Transparent and Accountable Training Data Sharing in Decentralized Machine Learning Systems." *Computers, Materials & Continua*, 79(3).

The paper designs a smart-contract-based dataset splitting and distribution protocol for decentralized ML that stores only IPFS content identifiers on-chain and uses attribute-based proxy re-encryption to keep test data confidential from workers and prevent malicious requesters from manipulating evaluation data. It is important for our bibliography because it highlights the often-overlooked malicious-requester threat and demonstrates a practical cost model for minimizing on-chain storage to CIDs, which we can reference when justifying our own off-chain storage design.

- Ahmed, W.A.H. Exploring blockchain technology as a governance layer for responsible artificial intelligence. AI Ethics 6, 334 (2026). https://doi.org/10.1007/s43681-026-01192-2

This paper examines how blockchain technology can help bridge the gap between high-level AI governance principles and their practical implementation. It proposes a conceptual framework for recordings related to governance data throughout the AI lifecycle on a blockchain to improve transparency, auditability, and accountability. The paper is relevant to our project because it provides a theoretical foundation for using blockchain to track AI model provenance, ownership, and development history.