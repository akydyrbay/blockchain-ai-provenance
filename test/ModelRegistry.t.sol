// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AIModelRegistry} from "../src/ModelRegistry.sol";

contract ModelRegistryTest is Test {
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
        assertEq(model.versionCount, 1);
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
        vm.prank(alice);
        uint256 version = registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        assertEq(version, 1);
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.versionCount, 2);
        assertEq(registry.getVersionCount(0), 2);
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
        AIModelRegistry.Version memory latest = registry.getLatestVersion(0);
        assertEq(latest.weightsHash, ARTIFACT_2);
    }

    function testCannotAppendAsNonOwner() public {
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, bob));
        vm.prank(bob);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
    }

    function testRegisterModelStartsWithoutVersions() public {
        vm.prank(alice);
        uint256 modelId = registry.registerModel("second-model", "metadata.json");
        assertEq(modelId, 1);
        assertEq(registry.totalModels(), 2);
        AIModelRegistry.Model memory model = registry.getModel(modelId);
        assertEq(model.versionCount, 0);
        assertEq(registry.getVersionCount(modelId), 0);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NoVersions.selector, modelId));
        registry.getLatestVersion(modelId);
    }

    function testRejectsBothZeroHashes() public {
        vm.expectRevert(AIModelRegistry.InvalidHashes.selector);
        vm.prank(alice);
        registry.registerVersion(0, bytes32(0), bytes32(0), "metadata.json", _metadataHashes(META_1));
    }

    function testUnknownModelAndVersionRevert() public {
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.ModelDoesNotExist.selector, 99));
        registry.getModel(99);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.ModelDoesNotExist.selector, 99));
        registry.getVersion(99, 0);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.VersionIndexOutOfBounds.selector, 0, 1));
        registry.getVersion(0, 1);
    }

    function testOwnershipTransferChangesAppendPermissions() public {
        vm.prank(alice);
        registry.transferModelOwnership(0, bob);
        AIModelRegistry.Model memory model = registry.getModel(0);
        assertEq(model.owner, bob);
        assertEq(model.versionCount, 1);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, alice));
        vm.prank(alice);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        vm.prank(bob);
        registry.registerVersion(0, ARTIFACT_2, DATA_2, "models/v2/metadata.json", _metadataHashes(META_2));
        AIModelRegistry.Version memory latestRecord = registry.getVersion(0, 1);
        assertEq(latestRecord.registeredBy, bob);
        AIModelRegistry.Version memory original = registry.getVersion(0, 0);
        assertEq(original.registeredBy, alice);
    }

    function testOwnershipTransferValidatesNewOwnerAndPermissions() public {
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.NotModelOwner.selector, 0, bob));
        vm.prank(bob);
        registry.transferModelOwnership(0, bob);
        vm.expectRevert(AIModelRegistry.InvalidNewOwner.selector);
        vm.prank(alice);
        registry.transferModelOwnership(0, address(0));
    }

    function _metadataHashes(bytes32 metadataHash) internal pure returns (bytes32[] memory hashes) {
        hashes = new bytes32[](1);
        hashes[0] = metadataHash;
    }
}
