// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {AIModelRegistry} from "../src/ModelRegistry.sol";
import {PolicyRegistry} from "../src/PolicyRegistry.sol";
import {DAGAnchor} from "../src/DAGAnchor.sol";
import {VerifyProbe} from "../src/VerifyProbe.sol";

contract ComparativeRegistryTest is Test {
    bytes32 private constant DATA = bytes32(uint256(2));
    address private constant PUBLISHER = address(0xa11ce);

    function record(bytes32 weights, uint256[] memory parents)
        private
        pure
        returns (AIModelRegistry.Provenance memory)
    {
        return AIModelRegistry.Provenance(
            "model", "https://example.test", weights, DATA, sha256("metadata"), parents
        );
    }

    function testMergeReturnsSharedAncestorOnce() public {
        AIModelRegistry registry = new AIModelRegistry();
        uint256[] memory noParents = new uint256[](0);
        uint256 root = registry.registerProvenance(record(sha256("root"), noParents), 0);
        uint256[] memory parent = new uint256[](1);
        parent[0] = root;
        uint256[] memory parents = new uint256[](2);
        parents[0] = registry.registerProvenance(record(sha256("left"), parent), 0);
        parents[1] = registry.registerProvenance(record(sha256("right"), parent), 0);
        uint256 child = registry.registerProvenance(record(sha256("merge"), parents), 0);
        uint256[] memory ancestorIds = registry.getLineage(child);
        assertEq(ancestorIds.length, 3);
        assertEq(ancestorIds[0], parents[0]);
        assertEq(ancestorIds[1], parents[1]);
        assertEq(ancestorIds[2], root);
    }

    function testUnversionedParentCannotBeUsed() public {
        AIModelRegistry registry = new AIModelRegistry();
        uint256[] memory parents = new uint256[](1);
        parents[0] = registry.registerModel("empty", "");
        AIModelRegistry.Provenance memory child = record(sha256("child"), parents);
        vm.expectRevert(abi.encodeWithSelector(AIModelRegistry.InvalidParent.selector, parents[0]));
        registry.registerProvenance(child, 0);
        assertEq(registry.totalModels(), 1);
    }

    function testLegacyVersionPathEnforcesPublisherPolicy() public {
        PolicyRegistry registry = new PolicyRegistry();
        bytes32[] memory datasets = new bytes32[](1);
        datasets[0] = DATA;
        registry.configure(datasets, new address[](0), true);
        vm.startPrank(PUBLISHER);
        uint256 model = registry.registerModel("model", "");
        bytes32 weights = bytes32(uint256(1));
        vm.expectRevert(abi.encodeWithSelector(PolicyRegistry.PublisherNotAllowed.selector, PUBLISHER));
        registry.registerVersion(model, weights, DATA, "", new bytes32[](0));
        vm.stopPrank();
    }

    function configuredPolicy() private returns (PolicyRegistry registry) {
        registry = new PolicyRegistry();
        bytes32[] memory datasets = new bytes32[](1);
        address[] memory publishers = new address[](1);
        datasets[0] = DATA;
        publishers[0] = address(this);
        registry.configure(datasets, publishers, true);
    }

    function testRegisteredWeightCannotBeReused() public {
        PolicyRegistry registry = configuredPolicy();
        bytes32 weights = bytes32(uint256(1));
        AIModelRegistry.Provenance memory input = record(weights, new uint256[](0));
        registry.registerProvenance(input, 0);
        vm.expectRevert(abi.encodeWithSelector(PolicyRegistry.DuplicateWeights.selector, weights));
        registry.registerProvenance(input, 0);
    }

    function testParentLicenceAndRevocation() public {
        PolicyRegistry registry = configuredPolicy();
        uint256 parent = registry.registerProvenance(record(bytes32(uint256(1)), new uint256[](0)), 3);
        uint256[] memory parents = new uint256[](1);
        parents[0] = parent;
        AIModelRegistry.Provenance memory child = record(bytes32(uint256(2)), parents);
        vm.expectRevert(abi.encodeWithSelector(PolicyRegistry.IncompatibleLicence.selector, parent));
        registry.registerProvenance(child, 0);
        registry.setRevoked(parent, true);
        vm.expectRevert(abi.encodeWithSelector(PolicyRegistry.RevokedParent.selector, parent));
        registry.registerProvenance(child, 3);
        registry.setRevoked(parent, false);
        uint256 registered = registry.registerProvenance(child, 3);
        assertEq(registry.licenceClass(registered), 3);
    }

    function testUnlistedDatasetCannotBeRegistered() public {
        PolicyRegistry registry = configuredPolicy();
        AIModelRegistry.Provenance memory input = record(bytes32(uint256(1)), new uint256[](0));
        input.dataHash = bytes32(uint256(9));
        vm.expectRevert(abi.encodeWithSelector(PolicyRegistry.DatasetNotAllowed.selector, input.dataHash));
        registry.registerProvenance(input, 0);
    }

    function testProbeReturnsLineageCallResult() public {
        AIModelRegistry registry = new AIModelRegistry();
        VerifyProbe probe = new VerifyProbe();
        registry.registerProvenance(record(bytes32(uint256(1)), new uint256[](0)), 0);
        (uint256 spent, bytes memory result) =
            probe.measure(address(registry), abi.encodeCall(AIModelRegistry.getLineage, (0)));
        assertGt(spent, 0);
        assertEq(abi.decode(result, (uint256[])).length, 0);
    }

    function testAnchoredProofAndAttestation() public {
        uint256 key = 42;
        DAGAnchor anchor = new DAGAnchor(vm.addr(key));
        bytes32 node = sha256("node");
        bytes32 root = sha256(abi.encodePacked(bytes1(0), node, PUBLISHER));
        uint8 v;
        bytes32 r;
        bytes32 s;
        (v, r, s) = vm.sign(41, anchor.attestationDigest(0, root, 1, address(this)));
        vm.expectRevert(DAGAnchor.InvalidAttestation.selector);
        anchor.anchor(root, 1, v, r, s);
        (v, r, s) = vm.sign(key, anchor.attestationDigest(0, root, 1, address(this)));
        anchor.anchor(root, 1, v, r, s);
        bytes32[] memory proof = new bytes32[](0);
        assertTrue(anchor.verifyAnchored(node, PUBLISHER, proof, 0, v, r, s));
        assertFalse(anchor.verifyAnchored(node, address(0), proof, 0, v, r, s));
        proof = new bytes32[](1);
        proof[0] = sha256("unrelated node");
        assertFalse(anchor.verifyAnchored(node, PUBLISHER, proof, 0, v, r, s));
        vm.expectRevert(DAGAnchor.InvalidAttestation.selector);
        anchor.anchor(root, 1, v, r, s);
    }
}
