// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// Shared registry for the controlled policy-placement experiment.
///
/// Both concrete registries below inherit this contract unchanged, so they write the same
/// storage slots per registration, accept one publisher-signed transaction per model, and
/// expose the same lineage and record getters to the storage verifier. They differ only in
/// `_admit`, which either evaluates the D2 admission rules in Solidity or verifies an
/// admission decision that an off-chain OPA attester signed for this exact record.
abstract contract PlacementRegistry {
    struct Model {
        uint256 modelId;
        string name;
        string metadataURI;
        address owner;
        uint256 createdAt;
    }

    struct Version {
        bytes32 weightsHash;
        bytes32 trainingDataHash;
        string versionURI;
        bytes32[] artifactHashes;
        uint256 timestamp;
        address registeredBy;
    }

    struct Provenance {
        string name;
        string uri;
        bytes32 weightsHash;
        bytes32 dataHash;
        bytes32 metadataHash;
        uint256[] parentIds;
    }

    uint8 public constant NO_DERIVATIVES = 4;
    uint8 public constant UNKNOWN = 5;

    uint256 private _currentModelId;
    mapping(uint256 => Model) private _models;
    mapping(uint256 => Version[]) private _versions;
    mapping(uint256 => uint256[]) private _parentIds;

    /// Policy index written by both variants, read on-chain only by the Solidity variant.
    mapping(bytes32 => bool) public registeredWeights;
    mapping(uint256 => uint8) public licenceClass;

    event ModelRegistered(uint256 indexed modelId, address indexed owner, string name, string metadataURI);
    event VersionCreated(
        uint256 indexed modelId,
        uint256 indexed versionIndex,
        bytes32 weightsHash,
        bytes32 trainingDataHash,
        bytes32[] artifactHashes,
        address indexed registeredBy,
        string versionURI
    );
    event LineageRecorded(uint256 indexed modelId, uint256[] parentIds);

    error ModelDoesNotExist(uint256 modelId);
    error VersionIndexOutOfBounds(uint256 modelId, uint256 versionIndex);
    error InvalidHashes();
    error EmptyName();
    error InvalidParent(uint256 parentId);
    error DuplicateParent(uint256 parentId);

    modifier modelExists(uint256 modelId) {
        if (_models[modelId].owner == address(0)) revert ModelDoesNotExist(modelId);
        _;
    }

    /// Register an immutable lineage record and its first version in one transaction.
    /// The structural checks match the D1 baseline and are identical in both variants.
    function registerProvenance(Provenance calldata record, uint8 licence, bytes calldata decision)
        external
        returns (uint256 modelId)
    {
        if (bytes(record.name).length == 0) revert EmptyName();
        if (record.weightsHash == bytes32(0) || record.dataHash == bytes32(0)) revert InvalidHashes();
        modelId = _currentModelId++;
        _checkParents(modelId, record.parentIds);
        _admit(modelId, record, licence, decision);
        _store(modelId, record, licence);
    }

    function _checkParents(uint256 modelId, uint256[] calldata parents) private view {
        for (uint256 i; i < parents.length; ++i) {
            uint256 parentId = parents[i];
            if (parentId >= modelId || _versions[parentId].length == 0) revert InvalidParent(parentId);
            for (uint256 j; j < i; ++j) {
                if (parents[j] == parentId) revert DuplicateParent(parentId);
            }
        }
    }

    function _store(uint256 modelId, Provenance calldata record, uint8 licence) private {
        registeredWeights[record.weightsHash] = true;
        licenceClass[modelId] = licence;
        _models[modelId] = Model({
            modelId: modelId, name: record.name, metadataURI: record.uri, owner: msg.sender, createdAt: block.timestamp
        });
        _parentIds[modelId] = record.parentIds;
        Version storage v = _versions[modelId].push();
        v.weightsHash = record.weightsHash;
        v.trainingDataHash = record.dataHash;
        v.versionURI = record.uri;
        v.timestamp = block.timestamp;
        v.registeredBy = msg.sender;
        v.artifactHashes.push(record.metadataHash);

        bytes32[] memory artifacts = new bytes32[](1);
        artifacts[0] = record.metadataHash;
        emit ModelRegistered(modelId, msg.sender, record.name, record.uri);
        emit VersionCreated(modelId, 0, record.weightsHash, record.dataHash, artifacts, msg.sender, record.uri);
        emit LineageRecorded(modelId, record.parentIds);
    }

    /// Admission decision for a structurally valid record. Reverts to refuse the record.
    function _admit(uint256 modelId, Provenance calldata record, uint8 licence, bytes calldata decision)
        internal
        view
        virtual;

    function getParents(uint256 modelId) external view modelExists(modelId) returns (uint256[] memory) {
        return _parentIds[modelId];
    }

    /// Return all distinct ancestors in discovery order (same traversal as the D1 registry).
    function getLineage(uint256 modelId)
        external
        view
        modelExists(modelId)
        returns (uint256[] memory ancestors)
    {
        ancestors = new uint256[](modelId);
        uint256[] memory stack = new uint256[](modelId + 1);
        bool[] memory seen = new bool[](modelId);
        stack[0] = modelId;
        uint256 pending = 1;
        uint256 count;
        while (pending != 0) {
            uint256 current = stack[--pending];
            uint256[] storage parents = _parentIds[current];
            for (uint256 i; i < parents.length; ++i) {
                uint256 parent = parents[i];
                if (seen[parent]) continue;
                seen[parent] = true;
                ancestors[count++] = parent;
                stack[pending++] = parent;
            }
        }
        assembly ("memory-safe") {
            mstore(ancestors, count)
        }
    }

    function getModel(uint256 modelId) external view modelExists(modelId) returns (Model memory) {
        return _models[modelId];
    }

    function getVersion(uint256 modelId, uint256 versionIndex)
        external
        view
        modelExists(modelId)
        returns (Version memory)
    {
        if (versionIndex >= _versions[modelId].length) revert VersionIndexOutOfBounds(modelId, versionIndex);
        return _versions[modelId][versionIndex];
    }

    function totalModels() external view returns (uint256) {
        return _currentModelId;
    }
}

/// Controlled variant C-Sol: the admission rules of D2 are evaluated in Solidity.
contract SolidityPolicyPlacement is PlacementRegistry {
    address public immutable admin = msg.sender;
    mapping(uint256 => bool) public revoked;
    mapping(bytes32 => bool) public allowedDataset;
    mapping(address => bool) public publisher;

    error NotAdmin();
    error UnexpectedDecision();
    error RevokedParent(uint256 parentId);
    error DuplicateWeights(bytes32 weightsHash);
    error DatasetNotAllowed(bytes32 dataHash);
    error PublisherNotAllowed(address account);
    error IncompatibleLicence(uint256 parentId);
    error InvalidLicenceClass(uint8 licence);

    event DatasetPermission(bytes32 indexed dataHash, bool allowed);
    event PublisherPermission(address indexed account, bool allowed);
    event Revocation(uint256 indexed modelId, bool revoked);

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    function configure(bytes32[] calldata datasets, address[] calldata publishers, bool allowed)
        external
        onlyAdmin
    {
        for (uint256 i; i < datasets.length; ++i) {
            allowedDataset[datasets[i]] = allowed;
            emit DatasetPermission(datasets[i], allowed);
        }
        for (uint256 i; i < publishers.length; ++i) {
            publisher[publishers[i]] = allowed;
            emit PublisherPermission(publishers[i], allowed);
        }
    }

    function setRevoked(uint256 modelId, bool value) external onlyAdmin modelExists(modelId) {
        revoked[modelId] = value;
        emit Revocation(modelId, value);
    }

    /// The same checks, in the same order, as `PolicyRegistry._beforeVersion`.
    function _admit(uint256, Provenance calldata record, uint8 licence, bytes calldata decision)
        internal
        view
        override
    {
        if (decision.length != 0) revert UnexpectedDecision();
        if (licence > UNKNOWN) revert InvalidLicenceClass(licence);
        uint256[] calldata parents = record.parentIds;
        for (uint256 i; i < parents.length; ++i) {
            if (revoked[parents[i]]) revert RevokedParent(parents[i]);
        }
        if (registeredWeights[record.weightsHash]) revert DuplicateWeights(record.weightsHash);
        if (!allowedDataset[record.dataHash]) revert DatasetNotAllowed(record.dataHash);
        if (!publisher[msg.sender]) revert PublisherNotAllowed(msg.sender);
        for (uint256 i; i < parents.length; ++i) {
            uint8 parentLicence = licenceClass[parents[i]];
            if (
                parentLicence == NO_DERIVATIVES
                    || (licence != UNKNOWN && parentLicence != UNKNOWN && licence < parentLicence)
            ) {
                revert IncompatibleLicence(parents[i]);
            }
        }
    }
}

/// Controlled variant C-OPA: the admission rules are evaluated off-chain by OPA, and the
/// contract accepts a record only with the attester's EIP-712 signature over that record,
/// its licence class, the next model identifier and the submitting publisher.
contract OpaPolicyPlacement is PlacementRegistry {
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 private constant ADMISSION_TYPEHASH =
        keccak256("Admission(uint256 modelId,bytes32 record,uint8 licence,address publisher)");
    uint256 private constant MAX_S = 0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    address public immutable attester;

    error InvalidAttester();
    error InvalidDecision();

    constructor(address signer) {
        if (signer == address(0)) revert InvalidAttester();
        attester = signer;
    }

    function recordDigest(Provenance calldata record) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                keccak256(bytes(record.name)),
                keccak256(bytes(record.uri)),
                record.weightsHash,
                record.dataHash,
                record.metadataHash,
                keccak256(abi.encodePacked(record.parentIds))
            )
        );
    }

    function admissionDigest(uint256 modelId, bytes32 record, uint8 licence, address submitter)
        public
        view
        returns (bytes32)
    {
        bytes32 domain = keccak256(
            abi.encode(
                DOMAIN_TYPEHASH, keccak256("OpaPolicyPlacement"), keccak256("1"), block.chainid, address(this)
            )
        );
        bytes32 message = keccak256(abi.encode(ADMISSION_TYPEHASH, modelId, record, licence, submitter));
        return keccak256(abi.encodePacked(hex"1901", domain, message));
    }

    function _admit(uint256 modelId, Provenance calldata record, uint8 licence, bytes calldata decision)
        internal
        view
        override
    {
        if (decision.length != 65) revert InvalidDecision();
        bytes32 r = bytes32(decision[0:32]);
        bytes32 s = bytes32(decision[32:64]);
        uint8 v = uint8(decision[64]);
        if ((v != 27 && v != 28) || uint256(s) > MAX_S) revert InvalidDecision();
        bytes32 digest = admissionDigest(modelId, recordDigest(record), licence, msg.sender);
        if (ecrecover(digest, v, r, s) != attester) revert InvalidDecision();
    }
}
