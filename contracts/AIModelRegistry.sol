// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AIModelRegistry {

    struct Model {
        uint256 modelId;
        string  name;
        string  metadataURI;  // URL to model metadata details
        address owner;
        uint256 createdAt;
    }

    struct Version {
        bytes32   weightsHash;      // hash of model weights / primary artifact
        bytes32   trainingDataHash; // hash of training set
        string    versionURI;       // URL to version metadata details
    }



// Variables

    uint256 private _currentModelId; 

    mapping(uint256 => Model) private _models;
    mapping(uint256 => Version[]) private _versions;


// Events

// Events


// Functions

    // Register new AI Model
    function registerModel(string calldata name, string calldata metadataURI) external returns (uint256 modelId) {

        modelId = _currentModelId++;

        _models[modelId] = Model({
            modelId:     modelId,
            name:        name,
            metadataURI: metadataURI,
            owner:       msg.sender,
            createdAt:   block.timestamp
        });

    }

    // Register new Version
    function registerVersion(uint256 modelId, bytes32 weightsHash, bytes32 trainingDataHash, string calldata versionURI) external {
        
  
        // At minimum we require one of the two main hashes to be set.
        if (weightsHash == bytes32(0) && trainingDataHash == bytes32(0)) {
            revert("Invalid hashes");
        }

        Version storage v = _versions[modelId].push();
        v.weightsHash       = weightsHash;
        v.trainingDataHash  = trainingDataHash;
        v.versionURI        = versionURI;
    }

}