// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title ModelRegistry
/// @notice An append-only registry of model artifact, training data and metadata hashes.
/// @dev Hashes are SHA-256 digests of raw file bytes computed OFF CHAIN.
///      The registry attests who recorded hashes, not who legally owns or trained a model.
contract ModelRegistry {
    struct Model {
        string name;
        address owner;
        address pendingOwner;
        uint256 latestVersion;
    }

    struct VersionRecord {
        bytes32 dataHash;
        bytes32 artifactHash;
        bytes32 metadataHash;
        uint64 recordedAt;
        address publisher;
    }

    error UnknownModel(uint256 modelId);
    error UnknownVersion(uint256 modelId, uint256 version);
    error NotModelOwner(uint256 modelId, address caller);
    error NotPendingOwner(uint256 modelId, address caller);
    error InvalidOwner();
    error EmptyName();
    error InvalidHash();

    event ModelRegistered(uint256 indexed modelId, address indexed owner, string name);
    event VersionRecorded(uint256 indexed modelId, uint256 indexed version, address indexed publisher);
    event OwnershipTransferProposed(uint256 indexed modelId, address indexed oldOwner, address indexed newOwner);
    event ModelOwnershipTransferred(uint256 indexed modelId, address indexed oldOwner, address indexed newOwner);

    uint256 public nextModelId = 1;
    mapping(uint256 => Model) private _models;
    mapping(uint256 => mapping(uint256 => VersionRecord)) private _versions;

    function registerModel(
        string calldata name,
        bytes32 dataHash,
        bytes32 artifactHash,
        bytes32 metadataHash
    ) external returns (uint256 modelId) {
        if (bytes(name).length == 0) revert EmptyName();
        _validateHashes(dataHash, artifactHash, metadataHash);

        modelId = nextModelId++;
        _models[modelId] = Model({
            name: name,
            owner: msg.sender,
            pendingOwner: address(0),
            latestVersion: 1
        });
        emit ModelRegistered(modelId, msg.sender, name);
        _storeVersion(modelId, 1, dataHash, artifactHash, metadataHash);
    }

    function addVersion(
        uint256 modelId,
        bytes32 dataHash,
        bytes32 artifactHash,
        bytes32 metadataHash
    ) external returns (uint256 version) {
        Model storage m = _requireModel(modelId);
        if (msg.sender != m.owner) revert NotModelOwner(modelId, msg.sender);
        _validateHashes(dataHash, artifactHash, metadataHash);

        version = ++m.latestVersion;
        _storeVersion(modelId, version, dataHash, artifactHash, metadataHash);
    }

    function proposeOwnershipTransfer(uint256 modelId, address newOwner) external {
        Model storage m = _requireModel(modelId);
        if (msg.sender != m.owner) revert NotModelOwner(modelId, msg.sender);
        if (newOwner == address(0) || newOwner == m.owner) revert InvalidOwner();

        m.pendingOwner = newOwner;
        emit OwnershipTransferProposed(modelId, m.owner, newOwner);
    }

    function acceptOwnership(uint256 modelId) external {
        Model storage m = _requireModel(modelId);
        if (msg.sender != m.pendingOwner) revert NotPendingOwner(modelId, msg.sender);
        address previousOwner = m.owner;
        m.owner = msg.sender;
        m.pendingOwner = address(0);
        emit ModelOwnershipTransferred(modelId, previousOwner, msg.sender);
    }

    function getModel(uint256 modelId)
        external view returns (string memory name, address owner, address pendingOwner, uint256 latestVersion)
    {
        Model storage m = _requireModel(modelId);
        return (m.name, m.owner, m.pendingOwner, m.latestVersion);
    }

    /// @notice For version >= 2, the implicit parent is version - 1 of the same model.
    function getVersion(uint256 modelId, uint256 version) external view returns (VersionRecord memory) {
        Model storage m = _requireModel(modelId);
        if (version == 0 || version > m.latestVersion) revert UnknownVersion(modelId, version);
        return _versions[modelId][version];
    }

    function _requireModel(uint256 modelId) private view returns (Model storage m) {
        m = _models[modelId];
        if (m.latestVersion == 0) revert UnknownModel(modelId);
    }

    function _validateHashes(bytes32 dataHash, bytes32 artifactHash, bytes32 metadataHash) private pure {
        if (dataHash == bytes32(0) || artifactHash == bytes32(0) || metadataHash == bytes32(0)) {
            revert InvalidHash();
        }
    }

    function _storeVersion(
        uint256 modelId,
        uint256 version,
        bytes32 dataHash,
        bytes32 artifactHash,
        bytes32 metadataHash
    ) private {
        _versions[modelId][version] = VersionRecord({
            dataHash: dataHash,
            artifactHash: artifactHash,
            metadataHash: metadataHash,
            recordedAt: uint64(block.timestamp),
            publisher: msg.sender
        });
        emit VersionRecorded(modelId, version, msg.sender);
    }
}
