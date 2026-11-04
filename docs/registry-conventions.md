# Registry conventions

These rules connect `AIModelRegistry` in `src/ModelRegistry.sol` with `scripts/verify.py`. Publishers and verifiers must use the same file-to-field mapping. The contract stores hashes and references; it does not enforce their application-specific meaning.

## Hashing and field mapping

All hashes are **SHA-256 of the exact file bytes**, represented as Solidity `bytes32` or `0x` followed by 64 hexadecimal characters. Do not normalize CSV or JSON content before hashing.

| Contract field | Required meaning |
| --- | --- |
| `weightsHash` | SHA-256 of that version's `model.joblib` |
| `trainingDataHash` | SHA-256 of the training dataset file; `data/iris_train.csv` for this demo |
| `artifactHashes[0]` | SHA-256 of that version's `metadata.json` |
| `versionURI` | Location of the preserved version-specific metadata file |
| Model `metadataURI` | Model-level metadata reference; the demo may use the v1 metadata location |

Register a version using this argument order:

```text
registerVersion(modelId, weightsHash, trainingDataHash, versionURI, [metadataHash])
```

The metadata hash must occupy the first array position. Additional entries may hold other artifact hashes, but their meaning is not defined here and the current verifier does not check them.

Use a stable metadata location, such as a repository URL containing the full commit SHA or a content-addressed URI. A URI locates a file; the registered hash checks its integrity. The verifier takes local file paths and does not fetch or validate URI contents.

## IDs and versions

`registerModel` creates an empty model record. Model IDs start at **0**; use the ID from its `ModelRegistered` event rather than assuming a value. Each `registerVersion` call appends one version, with indexes starting at **0** independently for each model.

Metadata and the verifier CLI retain one-based human version numbers:

| Model version | Metadata `version` / CLI `--version` | Contract index | Metadata `parent_version` |
| --- | --- | --- | --- |
| v1 | 1 | 0 | 0 (no predecessor) |
| v2 | 2 | 1 | 1 |
| vN | N | N - 1 | N - 1 |

`--model-id` is the actual zero-based contract ID. `--version` is translated to a contract index by subtracting one. `parent_version` refers to the preceding human version of the same model; it is not a model ID or proof of training ancestry. The contract has no explicit parent field.

## Metadata validation

For the requested version, `verify.py` checks:

- The dataset, weights, and metadata bytes match their registered hashes.
- `version` and `parent_version` follow the numbering above.
- `training_data_sha256` and `artifact_sha256` match the supplied files.
- `name` matches the registered model name.
- `training_code_sha256` matches `scripts/train_demo.py`, or the file supplied with `--training-script`.

The metadata may also record hyperparameters and library versions. Those bytes are protected by the metadata hash, but the verifier does not independently validate their accuracy.

The verifier rejects a missing `artifactHashes[0]` or a mismatching metadata hash. The metadata commitment is an application requirement: the contract permits an empty artifact array. The contract rejects a version if either `weightsHash` or `trainingDataHash` is zero. Publishers following these conventions must supply both file hashes and the metadata commitment.

## Preserving artifacts

Keep the registered dataset, model artifacts, metadata, and referenced training script unchanged. Reformatting JSON, changing line endings, or retraining can change hashes. Register newly produced artifacts as a new version and retain the old files for historical verification.

The demo's v1 and v2 models are trained independently on the same Iris training split. Their version order records publication sequence, not fine-tuning ancestry. A successful verification establishes agreement with registered claims; it does not prove the claimed training process or data origin.
