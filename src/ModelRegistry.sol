// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AIModelRegistry {
    struct Model {
        uint256 modelId;
        string name;
        string metadataURI; // URL to model metadata details
        address owner;
        uint256 createdAt;
    }

    struct Version {
        bytes32 weightsHash; // hash of model weights
        bytes32 trainingDataHash; // hash of training set
        string versionURI; // URL to version metadata details
        bytes32[] artifactHashes; // for configs
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

    // Variables
    uint256 private _currentModelId;
    mapping(uint256 => Model) private _models;
    mapping(uint256 => Version[]) private _versions;

    mapping(uint256 => uint256[]) private _parentIds;
    mapping(uint256 => uint8) private _licences;

    // Events
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
    event ModelOwnershipTransferred(
        uint256 indexed modelId, address indexed previousOwner, address indexed newOwner
    );

    event LineageRecorded(uint256 indexed modelId, uint256[] parentIds);

    // Errors
    error ModelDoesNotExist(uint256 modelId);
    error NoVersions(uint256 modelId);
    error InvalidHashes();
    error VersionIndexOutOfBounds(uint256 modelId, uint256 versionIndex);
    error NotModelOwner(uint256 modelId, address caller);
    error InvalidNewOwner();
    error EmptyName();
    error InvalidParent(uint256 parentId);
    error DuplicateParent(uint256 parentId);

    // Modifiers
    modifier modelExists(uint256 modelId) {
        if (_models[modelId].owner == address(0)) {
            revert ModelDoesNotExist(modelId);
        }
        _;
    }

    modifier onlyModelOwner(uint256 modelId) {
        if (_models[modelId].owner != msg.sender) {
            revert NotModelOwner(modelId, msg.sender);
        }
        _;
    }

    // Functions

    // Register new AI Model
    function registerModel(string calldata name, string calldata metadataURI)
        external
        returns (uint256 modelId)
    {
        return _registerModel(name, metadataURI);
    }

    function _registerModel(string calldata name, string calldata metadataURI)
        internal
        returns (uint256 modelId)
    {
        if (bytes(name).length == 0) {
            revert EmptyName();
        }

        modelId = _currentModelId++;
        _licences[modelId] = 5; // Unknown for the legacy entry point.

        _models[modelId] = Model({
            modelId: modelId,
            name: name,
            metadataURI: metadataURI,
            owner: msg.sender,
            createdAt: block.timestamp
        });

        emit ModelRegistered(modelId, msg.sender, name, metadataURI);
    }

    /// Register an immutable model lineage and its first version in one transaction.
    function registerProvenance(Provenance calldata record, uint8 licence)
        external
        returns (uint256 modelId)
    {
        modelId = _registerModel(record.name, record.uri);
        for (uint256 i; i < record.parentIds.length; ++i) {
            uint256 parentId = record.parentIds[i];
            if (parentId >= modelId || _versions[parentId].length == 0) revert InvalidParent(parentId);
            for (uint256 j; j < i; ++j) {
                if (record.parentIds[j] == parentId) revert DuplicateParent(parentId);
            }
        }
        _parentIds[modelId] = record.parentIds;
        _licences[modelId] = licence;
        bytes32[] memory artifacts = new bytes32[](1);
        artifacts[0] = record.metadataHash;
        _registerVersion(modelId, record.weightsHash, record.dataHash, record.uri, artifacts);
        emit LineageRecorded(modelId, record.parentIds);
    }

    function getParents(uint256 modelId) external view modelExists(modelId) returns (uint256[] memory) {
        return _parentIds[modelId];
    }

    /// Return all distinct ancestors in discovery order. Parents always have lower IDs.
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

    function _beforeVersion(uint256, bytes32, bytes32, uint256[] memory, uint8) internal virtual {}

    // Register new Version
    function registerVersion(
        uint256 modelId,
        bytes32 weightsHash,
        bytes32 trainingDataHash,
        string calldata versionURI,
        bytes32[] calldata artifactHashes
    ) external modelExists(modelId) onlyModelOwner(modelId) returns (uint256 versionIndex) {
        return _registerVersion(modelId, weightsHash, trainingDataHash, versionURI, artifactHashes);
    }

    function _registerVersion(
        uint256 modelId,
        bytes32 weightsHash,
        bytes32 trainingDataHash,
        string calldata versionURI,
        bytes32[] memory artifactHashes
    ) internal returns (uint256 versionIndex) {
        if (weightsHash == bytes32(0) || trainingDataHash == bytes32(0)) {
            revert InvalidHashes();
        }

        _beforeVersion(modelId, weightsHash, trainingDataHash, _parentIds[modelId], _licences[modelId]);

        Version storage v = _versions[modelId].push();
        v.weightsHash = weightsHash;
        v.trainingDataHash = trainingDataHash;
        v.versionURI = versionURI;
        v.timestamp = block.timestamp;
        v.registeredBy = msg.sender;

        for (uint256 i = 0; i < artifactHashes.length; i++) {
            v.artifactHashes.push(artifactHashes[i]);
        }

        versionIndex = _versions[modelId].length - 1;

        emit VersionCreated(
            modelId, versionIndex, weightsHash, trainingDataHash, artifactHashes, msg.sender, versionURI
        );
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
        if (versionIndex >= _versions[modelId].length) {
            revert VersionIndexOutOfBounds(modelId, versionIndex);
        }
        return _versions[modelId][versionIndex];
    }

    function totalModels() external view returns (uint256) {
        return _currentModelId;
    }

    function getLatestVersion(uint256 modelId) external view modelExists(modelId) returns (Version memory) {
        uint256 len = _versions[modelId].length;
        if (len == 0) {
            revert NoVersions(modelId);
        }
        return _versions[modelId][len - 1];
    }

    function getVersionCount(uint256 modelId) external view modelExists(modelId) returns (uint256) {
        return _versions[modelId].length;
    }

    function getArtifactHashes(uint256 modelId, uint256 versionIndex)
        external
        view
        modelExists(modelId)
        returns (bytes32[] memory)
    {
        if (versionIndex >= _versions[modelId].length) {
            revert VersionIndexOutOfBounds(modelId, versionIndex);
        }
        return _versions[modelId][versionIndex].artifactHashes;
    }

    function transferModelOwnership(uint256 modelId, address newOwner)
        external
        modelExists(modelId)
        onlyModelOwner(modelId)
    {
        if (newOwner == address(0)) revert InvalidNewOwner();

        address previousOwner = _models[modelId].owner;
        _models[modelId].owner = newOwner;

        emit ModelOwnershipTransferred(modelId, previousOwner, newOwner);
    }
}
