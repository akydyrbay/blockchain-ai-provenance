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