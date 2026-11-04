// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AIModelRegistry} from "../src/ModelRegistry.sol";

contract ModelRegistryTest is Test {
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

    AIModelRegistry internal registry;
    address internal alice;
    address internal bob;
    bytes32 internal constant DATA_1 = keccak256("dataset_v1");
    bytes32 internal constant ARTIFACT_1 = keccak256("artifact_v1");
    bytes32 internal constant META_1 = keccak256("metadata_v1");
    bytes32 internal constant DATA_2 = keccak256("dataset_v2");
    bytes32 internal constant ARTIFACT_2 = keccak256("artifact_v2");
    bytes32 internal constant META_2 = keccak256("metadata_v2");

    function setUp() public {
        vm.warp(100);
        alice = makeAddr("alice");
        bob = makeAddr("bob");
        registry = new AIModelRegistry();
        vm.prank(alice);
        registry.registerModel("iris-logistic-regression", "models/v1/metadata.json");
        vm.prank(alice);
        registry.registerVersion(0, ARTIFACT_1, DATA_1, "models/v1/metadata.json", _metadataHashes(META_1));
    }

    function testRegisterVersionStoresRecord() public view {
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.modelId, 0);
        assertEq(model.name, "iris-logistic-regression");
        assertEq(model.metadataURI, "models/v1/metadata.json");
        assertEq(model.owner, alice);
        assertEq(model.createdAt, block.timestamp);
        assertEq(registry.getVersionCount(0), 1);
        assertEq(registry.totalModels(), 1);
        AIModelRegistry.Version memory v = registry.getVersion(0, 0);
        assertEq(v.trainingDataHash, DATA_1);
        assertEq(v.weightsHash, ARTIFACT_1);
        assertEq(v.artifactHashes, _metadataHashes(META_1));
        assertEq(v.versionURI, "models/v1/metadata.json");
        assertEq(v.registeredBy, alice);
        assertEq(v.timestamp, block.timestamp);
        assertEq(registry.getArtifactHashes(0, 0), _metadataHashes(META_1));
    }

    function testOwnerAppendsWithoutChangingPriorVersion() public {
        bytes memory original = abi.encode(registry.getVersion(0, 0));
        vm.warp(200);
        vm.prank(alice);
        uint256 version = registry.registerVersion(
            0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2)
        );
        assertEq(version, 1);
        assertEq(registry.getVersionCount(0), 2);
        assertEq(abi.encode(registry.getVersion(0, 0)), original);
        AIModelRegistry.Version memory old = registry.getVersion(0, 0);
        AIModelRegistry.Version memory updated = registry.getVersion(0, 1);
        assertEq(old.weightsHash, ARTIFACT_1);
        assertEq(old.trainingDataHash, DATA_1);
        assertEq(old.artifactHashes, _metadataHashes(META_1));
        assertEq(old.registeredBy, alice);
        assertEq(updated.weightsHash, ARTIFACT_2);
        assertEq(updated.trainingDataHash, DATA_2);
        assertEq(updated.artifactHashes, _metadataHashes(META_2));
        assertEq(updated.registeredBy, alice);
        assertEq(old.timestamp, 100);
        assertEq(updated.timestamp, 200);
        assertEq(updated.versionURI, "models/v2/metadata.json");
        AIModelRegistry.Version memory latest = registry.getLatestVersion(0);
        assertEq(abi.encode(latest), abi.encode(updated));
    }

    function testCannotAppendAsNonOwner() public {
        bytes memory original = abi.encode(registry.getVersion(0, 0));
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, bob));
        vm.prank(bob);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        assertEq(registry.getVersionCount(0), 1);
        assertEq(abi.encode(registry.getVersion(0, 0)), original);
    }

    function testRegisterModelStartsWithoutVersions() public {
        vm.warp(200);
        vm.expectEmit(true, true, false, true, address(registry));
        emit ModelRegistered(1, alice, "second-model", "metadata.json");
        vm.prank(alice);
        uint256 modelId = registry.registerModel("second-model", "metadata.json");
        assertEq(modelId, 1);
        assertEq(registry.totalModels(), 2);
        AIModelRegistry.Model memory model = registry.getModel(modelId);
        assertEq(model.modelId, modelId);
        assertEq(model.name, "second-model");
        assertEq(model.metadataURI, "metadata.json");
        assertEq(model.owner, alice);
        assertEq(model.createdAt, 200);
        assertEq(registry.getVersionCount(modelId), 0);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NoVersions.selector, modelId));
        registry.getLatestVersion(modelId);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, modelId, 0));
        registry.getVersion(modelId, 0);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, modelId, 0));
        registry.getArtifactHashes(modelId, 0);
    }

    function testRejectsBothZeroHashes() public {
        _assertInvalidHashes(bytes32(0), bytes32(0));
    }

    function testRejectsZeroWeightsHash() public {
        _assertInvalidHashes(bytes32(0), DATA_2);
    }

    function testRejectsZeroTrainingDataHash() public {
        _assertInvalidHashes(ARTIFACT_2, bytes32(0));
    }

    function testRejectsEmptyNameWithoutConsumingModelId() public {
        vm.expectRevert(AIModelRegistry.EmptyName.selector);
        vm.prank(alice);
        registry.registerModel("", "metadata.json");
        assertEq(registry.totalModels(), 1);
        vm.prank(alice);
        assertEq(registry.registerModel("valid", "metadata.json"), 1);
    }

    function testVersionRegistrationEmitsEventAndStoresAllArtifacts() public {
        bytes32[] memory artifacts = new bytes32[](2);
        artifacts[0] = META_2;
        artifacts[1] = keccak256("config_v2");
        vm.warp(200);
        vm.expectEmit(true, true, true, true, address(registry));
        emit VersionCreated(0, 1, ARTIFACT_2, DATA_2, artifacts, alice, "models/v2/metadata.json");
        vm.prank(alice);
        uint256 index = registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", artifacts);
        assertEq(index, 1);
        AIModelRegistry.Version memory version = registry.getVersion(0, index);
        assertEq(version.weightsHash, ARTIFACT_2);
        assertEq(version.trainingDataHash, DATA_2);
        assertEq(version.versionURI, "models/v2/metadata.json");
        assertEq(version.artifactHashes, artifacts);
        assertEq(version.registeredBy, alice);
        assertEq(version.timestamp, 200);
        assertEq(registry.getArtifactHashes(0, index), artifacts);
    }

    function testUnknownModelAndVersionRevert() public {
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.ModelDoesNotExist.selector, 99));
        registry.getModel(99);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.ModelDoesNotExist.selector, 99));
        registry.getVersion(99, 0);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, 0, 1));
        registry.getVersion(0, 1);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, 0, 1));
        registry.getArtifactHashes(0, 1);
    }

    function testOwnershipTransferChangesAppendPermissions() public {
        bytes memory original = abi.encode(registry.getVersion(0, 0));
        vm.warp(200);
        vm.expectEmit(true, true, true, true, address(registry));
        emit ModelOwnershipTransferred(0, alice, bob);
        vm.prank(alice);
        registry.transferModelOwnership(0, bob);
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.owner, bob);
        assertEq(model.createdAt, 100);
        assertEq(model.name, "iris-logistic-regression");
        assertEq(model.metadataURI, "models/v1/metadata.json");
        assertEq(registry.getVersionCount(0), 1);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, alice));
        vm.prank(alice);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        assertEq(registry.getVersionCount(0), 1);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, alice));
        vm.prank(alice);
        registry.transferModelOwnership(0, alice);
        vm.expectEmit(true, true, true, true, address(registry));
        emit VersionCreated(0, 1, ARTIFACT_2, DATA_2, _metadataHashes(META_2), bob, "models/v2/metadata.json");
        vm.prank(bob);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        AIModelRegistry.Version memory latestRecord = registry.getVersion(0, 1);
        assertEq(latestRecord.registeredBy, bob);
        assertEq(latestRecord.timestamp, 200);
        assertEq(registry.getVersionCount(0), 2);
        assertEq(abi.encode(registry.getVersion(0, 0)), original);
    }

    function testOwnershipTransferValidatesNewOwnerAndPermissions() public {
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, bob));
        vm.prank(bob);
        registry.transferModelOwnership(0, bob);
        vm.expectRevert(AIModelRegistry.InvalidNewOwner.selector);
        vm.prank(alice);
        registry.transferModelOwnership(0, address(0));
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.owner, alice);
        assertEq(registry.getVersionCount(0), 1);
    }

    function testVersionsAreIsolatedBetweenModels() public {
        bytes memory original = abi.encode(registry.getVersion(0, 0));
        vm.prank(bob);
        uint256 modelId = registry.registerModel("bob-model", "bob.json");
        vm.prank(bob);
        uint256 index =
            registry.registerVersion(modelId, ARTIFACT_2, DATA_2, "bob.json", _metadataHashes(META_2));
        assertEq(index, 0);
        assertEq(registry.getVersionCount(modelId), 1);
        assertEq(registry.getVersionCount(0), 1);
        assertEq(abi.encode(registry.getVersion(0, 0)), original);
        AIModelRegistry.Version memory version = registry.getVersion(modelId, 0);
        assertEq(version.registeredBy, bob);
        assertEq(version.weightsHash, ARTIFACT_2);
    }

    function testFuzzRejectsEitherMissingHash(bytes32 nonzeroHash) public {
        vm.assume(nonzeroHash != bytes32(0));
        _assertInvalidHashes(bytes32(0), nonzeroHash);
        _assertInvalidHashes(nonzeroHash, bytes32(0));
    }

    function testFuzzStoresNonzeroHashes(bytes32 weights, bytes32 data, bytes32 metadata) public {
        vm.assume(weights != bytes32(0) && data != bytes32(0));
        vm.prank(alice);
        uint256 index = registry.registerVersion(0, weights, data, "metadata.json", _metadataHashes(metadata));
        assertEq(index, 1);
        AIModelRegistry.Version memory version = registry.getVersion(0, index);
        assertEq(version.weightsHash, weights);
        assertEq(version.trainingDataHash, data);
        assertEq(version.artifactHashes, _metadataHashes(metadata));
    }

    function testFuzzNonOwnerCannotAppendOrTransfer(address caller) public {
        vm.assume(caller != alice);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, caller));
        vm.prank(caller);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "metadata.json", _metadataHashes(META_2));
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, caller));
        vm.prank(caller);
        registry.transferModelOwnership(0, bob);
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.owner, alice);
        assertEq(registry.getVersionCount(0), 1);
    }

    function testFuzzInvalidVersionIndexes(uint256 index) public {
        index = bound(index, 1, type(uint256).max);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, 0, index));
        registry.getVersion(0, index);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, 0, index));
        registry.getArtifactHashes(0, index);
    }

    function testFuzzMissingModelsRejectAllModelOperations(uint256 modelId) public {
        modelId = bound(modelId, 1, type(uint256).max);
        bytes memory error = abi.encodeWithSelector(AIModelRegistry.ModelDoesNotExist.selector, modelId);
        vm.expectRevert(error);
        registry.getModel(modelId);
        vm.expectRevert(error);
        registry.getVersion(modelId, 0);
        vm.expectRevert(error);
        registry.getLatestVersion(modelId);
        vm.expectRevert(error);
        registry.getVersionCount(modelId);
        vm.expectRevert(error);
        registry.getArtifactHashes(modelId, 0);
        vm.expectRevert(error);
        vm.prank(alice);
        registry.registerVersion(modelId, ARTIFACT_1, DATA_1, "metadata.json", _metadataHashes(META_1));
        vm.expectRevert(error);
        vm.prank(alice);
        registry.transferModelOwnership(modelId, bob);
        assertEq(registry.totalModels(), 1);
    }

    function _assertInvalidHashes(bytes32 weights, bytes32 data) internal {
        bytes memory original = abi.encode(registry.getVersion(0, 0));
        vm.expectRevert(AIModelRegistry.InvalidHashes.selector);
        vm.prank(alice);
        registry.registerVersion(0, weights, data, "metadata.json", _metadataHashes(META_1));
        assertEq(registry.getVersionCount(0), 1);
        assertEq(abi.encode(registry.getVersion(0, 0)), original);
    }

    function _metadataHashes(bytes32 metadataHash) internal pure returns (bytes32[] memory hashes) {
        hashes = new bytes32[](1);
        hashes[0] = metadataHash;
    }
}
