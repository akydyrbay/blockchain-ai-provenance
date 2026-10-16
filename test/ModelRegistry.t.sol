// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {ModelRegistry} from "../src/ModelRegistry.sol";

contract ModelRegistryTest is Test {
    ModelRegistry internal registry;
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
        registry = new ModelRegistry();
        vm.prank(alice);
        registry.registerModel("iris-logistic-regression", DATA_1, ARTIFACT_1, META_1);
    }

    function testRegisterCreatesFirstVersion() public view {
        (string memory name, address owner, address pendingOwner, uint256 latestVersion) = registry.getModel(1);
        assertEq(name, "iris-logistic-regression");
        assertEq(owner, alice);
        assertEq(pendingOwner, address(0));
        assertEq(latestVersion, 1);
        assertEq(registry.nextModelId(), 2);
        ModelRegistry.VersionRecord memory v = registry.getVersion(1, 1);
        assertEq(v.dataHash, DATA_1);
        assertEq(v.artifactHash, ARTIFACT_1);
        assertEq(v.metadataHash, META_1);
        assertEq(v.publisher, alice);
        assertEq(uint256(v.recordedAt), block.timestamp);
    }

    function testOwnerAppendsWithoutChangingPriorVersion() public {
        vm.prank(alice);
        uint256 version = registry.addVersion(1, DATA_2, ARTIFACT_2, META_2);
        assertEq(version, 2);
        (,,, uint256 latestVersion) = registry.getModel(1);
        assertEq(latestVersion, 2);
        ModelRegistry.VersionRecord memory old = registry.getVersion(1, 1);
        ModelRegistry.VersionRecord memory updated = registry.getVersion(1, 2);
        assertEq(old.artifactHash, ARTIFACT_1);
        assertEq(updated.artifactHash, ARTIFACT_2);
        assertEq(updated.dataHash, DATA_2);
        assertEq(updated.publisher, alice);
    }

    function testCannotAppendAsNonOwner() public {
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.NotModelOwner.selector, 1, bob));
        vm.prank(bob);
        registry.addVersion(1, DATA_2, ARTIFACT_2, META_2);
    }

    function testRejectsEmptyModelName() public {
        vm.expectRevert(ModelRegistry.EmptyName.selector);
        registry.registerModel("", DATA_1, ARTIFACT_1, META_1);
    }

    function testRejectsZeroHashes() public {
        vm.expectRevert(ModelRegistry.InvalidHash.selector);
        registry.registerModel("bad", bytes32(0), ARTIFACT_1, META_1);
        vm.expectRevert(ModelRegistry.InvalidHash.selector);
        vm.prank(alice);
        registry.addVersion(1, DATA_2, bytes32(0), META_2);
    }

    function testUnknownModelAndVersionRevert() public {
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.UnknownModel.selector, 99));
        registry.getModel(99);
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.UnknownVersion.selector, 1, 0));
        registry.getVersion(1, 0);
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.UnknownVersion.selector, 1, 2));
        registry.getVersion(1, 2);
    }

    function testOwnershipTransferRequiresAcceptance() public {
        vm.prank(alice);
        registry.proposeOwnershipTransfer(1, bob);

        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.NotPendingOwner.selector, 1, alice));
        vm.prank(alice);
        registry.acceptOwnership(1);

        vm.prank(bob);
        registry.acceptOwnership(1);
        (, address owner, address pending, uint256 latest) = registry.getModel(1);
        assertEq(owner, bob);
        assertEq(pending, address(0));
        assertEq(latest, 1);
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.NotModelOwner.selector, 1, alice));
        vm.prank(alice);
        registry.addVersion(1, DATA_2, ARTIFACT_2, META_2);
        vm.prank(bob);
        registry.addVersion(1, DATA_2, ARTIFACT_2, META_2);
        ModelRegistry.VersionRecord memory latestRecord = registry.getVersion(1, 2);
        assertEq(latestRecord.publisher, bob);
    }

    function testOwnershipTransferValidatesNewOwnerAndPermissions() public {
        vm.expectRevert(abi.encodeWithSelector(ModelRegistry.NotModelOwner.selector, 1, bob));
        vm.prank(bob);
        registry.proposeOwnershipTransfer(1, bob);
        vm.expectRevert(ModelRegistry.InvalidOwner.selector);
        vm.prank(alice);
        registry.proposeOwnershipTransfer(1, address(0));
        vm.expectRevert(ModelRegistry.InvalidOwner.selector);
        vm.prank(alice);
        registry.proposeOwnershipTransfer(1, alice);
    }
}
