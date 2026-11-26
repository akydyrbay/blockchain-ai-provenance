// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PlacementRegistry, SolidityPolicyPlacement, OpaPolicyPlacement} from "../src/PlacementRegistry.sol";

contract PlacementRegistryTest is Test {
    bytes32 private constant DATA = bytes32(uint256(2));
    uint256 private constant ATTESTER_KEY = 42;
    address private constant PUBLISHER = address(0xa11ce);

    function record(bytes32 weights, uint256[] memory parents)
        private
        pure
        returns (PlacementRegistry.Provenance memory)
    {
        return PlacementRegistry.Provenance(
            "model", "https://example.test", weights, DATA, sha256("metadata"), parents
        );
    }

    function solidityRegistry() private returns (SolidityPolicyPlacement registry) {
        registry = new SolidityPolicyPlacement();
        bytes32[] memory datasets = new bytes32[](1);
        address[] memory publishers = new address[](1);
        datasets[0] = DATA;
        publishers[0] = PUBLISHER;
        registry.configure(datasets, publishers, true);
    }

    function ticket(
        OpaPolicyPlacement registry,
        uint256 key,
        uint256 modelId,
        PlacementRegistry.Provenance memory input,
        uint8 licence,
        address submitter
    ) private view returns (bytes memory) {
        bytes32 digest = registry.admissionDigest(modelId, registry.recordDigest(input), licence, submitter);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function testVariantsWriteTheSameSlots() public {
        SolidityPolicyPlacement onChain = solidityRegistry();
        OpaPolicyPlacement offChain = new OpaPolicyPlacement(vm.addr(ATTESTER_KEY));
        uint256[] memory noParents = new uint256[](0);
        uint256[] memory parent = new uint256[](1);
        PlacementRegistry.Provenance memory root = record(sha256("root"), noParents);
        PlacementRegistry.Provenance memory child = record(sha256("child"), parent);

        vm.startPrank(PUBLISHER);
        onChain.registerProvenance(root, 0, "");
        offChain.registerProvenance(root, 0, ticket(offChain, ATTESTER_KEY, 0, root, 0, PUBLISHER));

        vm.record();
        onChain.registerProvenance(child, 0, "");
        (, bytes32[] memory onChainWrites) = vm.accesses(address(onChain));
        vm.record();
        offChain.registerProvenance(child, 0, ticket(offChain, ATTESTER_KEY, 1, child, 0, PUBLISHER));
        (, bytes32[] memory offChainWrites) = vm.accesses(address(offChain));
        vm.stopPrank();

        assertGt(onChainWrites.length, 0);
        assertEq(onChainWrites.length, offChainWrites.length);
        for (uint256 i; i < onChainWrites.length; ++i) {
            assertEq(onChainWrites[i], offChainWrites[i]);
        }
        assertEq(onChain.getLineage(1), offChain.getLineage(1));
        assertEq(onChain.getVersion(1, 0).weightsHash, offChain.getVersion(1, 0).weightsHash);
        assertEq(onChain.getModel(1).owner, offChain.getModel(1).owner);
    }

    function testSolidityVariantAppliesPolicyRules() public {
        SolidityPolicyPlacement registry = solidityRegistry();
        uint256[] memory noParents = new uint256[](0);
        vm.startPrank(PUBLISHER);
        uint256 parent = registry.registerProvenance(record(bytes32(uint256(1)), noParents), 3, "");

        PlacementRegistry.Provenance memory fresh = record(bytes32(uint256(9)), noParents);
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.UnexpectedDecision.selector));
        registry.registerProvenance(fresh, 0, hex"01");

        PlacementRegistry.Provenance memory duplicate = record(bytes32(uint256(1)), noParents);
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.DuplicateWeights.selector, bytes32(uint256(1))));
        registry.registerProvenance(duplicate, 0, "");

        PlacementRegistry.Provenance memory unlisted = record(bytes32(uint256(5)), noParents);
        unlisted.dataHash = bytes32(uint256(9));
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.DatasetNotAllowed.selector, unlisted.dataHash));
        registry.registerProvenance(unlisted, 0, "");

        uint256[] memory parents = new uint256[](1);
        parents[0] = parent;
        PlacementRegistry.Provenance memory child = record(bytes32(uint256(2)), parents);
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.IncompatibleLicence.selector, parent));
        registry.registerProvenance(child, 0, "");
        vm.stopPrank();

        registry.setRevoked(parent, true);
        vm.prank(PUBLISHER);
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.RevokedParent.selector, parent));
        registry.registerProvenance(child, 3, "");

        registry.setRevoked(parent, false);
        vm.expectRevert(abi.encodeWithSelector(SolidityPolicyPlacement.PublisherNotAllowed.selector, address(this)));
        registry.registerProvenance(child, 3, "");
        vm.prank(PUBLISHER);
        assertEq(registry.registerProvenance(child, 3, ""), 1);
        assertTrue(registry.registeredWeights(bytes32(uint256(2))));
    }

    function testOpaVariantRequiresMatchingDecision() public {
        OpaPolicyPlacement registry = new OpaPolicyPlacement(vm.addr(ATTESTER_KEY));
        uint256[] memory noParents = new uint256[](0);
        PlacementRegistry.Provenance memory root = record(sha256("root"), noParents);
        bytes memory valid = ticket(registry, ATTESTER_KEY, 0, root, 0, PUBLISHER);

        bytes memory wrongKey = ticket(registry, ATTESTER_KEY + 1, 0, root, 0, PUBLISHER);
        PlacementRegistry.Provenance memory altered = record(sha256("other"), noParents);

        vm.startPrank(PUBLISHER);
        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(root, 0, "");
        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(root, 0, wrongKey);
        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(root, 1, valid);
        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(altered, 0, valid);
        vm.stopPrank();

        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(root, 0, valid);

        vm.startPrank(PUBLISHER);
        assertEq(registry.registerProvenance(root, 0, valid), 0);
        vm.expectRevert(OpaPolicyPlacement.InvalidDecision.selector);
        registry.registerProvenance(root, 0, valid);
        vm.stopPrank();
    }

    function testOpaVariantKeepsStructuralChecks() public {
        OpaPolicyPlacement registry = new OpaPolicyPlacement(vm.addr(ATTESTER_KEY));
        uint256[] memory parents = new uint256[](1);
        parents[0] = 7;
        PlacementRegistry.Provenance memory orphan = record(sha256("orphan"), parents);
        bytes memory signed = ticket(registry, ATTESTER_KEY, 0, orphan, 0, PUBLISHER);
        vm.prank(PUBLISHER);
        vm.expectRevert(abi.encodeWithSelector(PlacementRegistry.InvalidParent.selector, 7));
        registry.registerProvenance(orphan, 0, signed);
    }
}
