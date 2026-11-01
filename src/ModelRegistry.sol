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



// Variables

    uint256 private _currentModelId; 

    mapping(uint256 => Model) private _models;
    mapping(uint256 => Version[]) private _versions;


// Events

// Events


// Errors
    error ModelDoesNotExist(uint256 modelId);
    error NoVersions(uint256 modelId);
    error InvalidHashes();
    error VersionIndexOutOfBounds(uint256 modelId, uint256 versionIndex);


// Modifiers 
    modifier modelExists(uint256 modelId) {
        if (_models[modelId].owner == address(0)) {
            revert ModelDoesNotExist(modelId);
        }
        _;
    }

// Functions

    // Register new AI Model
    function registerModel(string calldata name, string calldata metadataURI) external returns (uint256 modelId) {

        modelId = _currentModelId++;

        _models[modelId] = Model({
            modelId: modelId,
            name: name,
            metadataURI: metadataURI,
            owner: msg.sender,
            createdAt: block.timestamp
        });

    }

    // Register new Version
    function registerVersion(uint256 modelId, bytes32 weightsHash, bytes32 trainingDataHash, string calldata versionURI) external modelExists(modelId) {

        if (weightsHash == bytes32(0) && trainingDataHash == bytes32(0)) {
            revert InvalidHashes();
        }

        Version storage v = _versions[modelId].push();
        v.weightsHash = weightsHash;
        v.trainingDataHash = trainingDataHash;
        v.versionURI = versionURI;
    }

    function getModel(uint256 modelId) external view modelExists(modelId) returns (Model memory) {
        return _models[modelId];
    }

    function getVersion(uint256 modelId, uint256 versionIndex) external view modelExists(modelId) returns (Version memory) {
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

}