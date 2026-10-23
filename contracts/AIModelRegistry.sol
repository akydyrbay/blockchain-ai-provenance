// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AIModelRegistry {

    struct Model {
        uint256 modelId;
        string  name;
        string  metadataURI;
    }

    struct Version {
        bytes32   weightsHash;      // hash of model weights / primary artifact
        bytes32   trainingDataHash; // hash of training set
        string    versionURI;       // URL to metadata details
    }



// Variables

    uint256 private currentModelId; 

    mapping(uint256 => Model) private models;
    mapping(uint256 => Version[]) private versions;


// Events

// Events


// Functions

    // Register new AI Model
    function registerModel(string calldata name, string calldata metadataURI) external returns (uint256 modelId) {

        modelId = currentModelId++;

        models[modelId] = Model({
            modelId:     modelId,
            name:        name,
            metadataURI: metadataURI,
        });

    }

}