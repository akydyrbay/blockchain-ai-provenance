// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AIModelRegistry} from "./ModelRegistry.sol";

contract PolicyRegistry is AIModelRegistry {
    uint8 public constant NO_DERIVATIVES = 4;
    uint8 public constant UNKNOWN = 5;

    address public immutable admin = msg.sender;
    mapping(uint256 => bool) public revoked;
    mapping(bytes32 => bool) public registeredWeights;
    mapping(bytes32 => bool) public allowedDataset;
    mapping(address => bool) public publisher;
    mapping(uint256 => uint8) public licenceClass;

    error NotAdmin();
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

    function _beforeVersion(
        uint256 modelId,
        bytes32 weightsHash,
        bytes32 dataHash,
        uint256[] memory parents,
        uint8 licence
    ) internal override {
        if (licence > UNKNOWN) revert InvalidLicenceClass(licence);
        for (uint256 i; i < parents.length; ++i) {
            if (revoked[parents[i]]) revert RevokedParent(parents[i]);
        }
        if (registeredWeights[weightsHash]) revert DuplicateWeights(weightsHash);
        if (!allowedDataset[dataHash]) revert DatasetNotAllowed(dataHash);
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
        registeredWeights[weightsHash] = true;
        licenceClass[modelId] = licence;
    }
}
