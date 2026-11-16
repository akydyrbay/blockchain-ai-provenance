// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract DAGAnchor {
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 private constant BATCH_TYPEHASH =
        keccak256("Batch(uint256 batchId,bytes32 root,uint256 size,address submitter)");
    uint256 private constant MAX_S = 0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    struct Batch {
        bytes32 root;
        address submitter;
        uint64 timestamp;
        uint32 size;
    }

    address public immutable attester;
    uint256 public nextBatchId;
    mapping(uint256 => Batch) public batches;

    error InvalidAttester();
    error InvalidBatch();
    error InvalidAttestation();

    event BatchAnchored(
        uint256 indexed batchId, bytes32 indexed root, address indexed submitter, uint32 size
    );

    constructor(address signer) {
        if (signer == address(0)) revert InvalidAttester();
        attester = signer;
    }

    function anchor(bytes32 root, uint32 size, uint8 v, bytes32 r, bytes32 s) external returns (uint256 id) {
        if (root == bytes32(0) || size == 0) revert InvalidBatch();
        id = nextBatchId;
        if (!verifyAttestation(id, root, size, msg.sender, v, r, s)) revert InvalidAttestation();
        batches[id] = Batch(root, msg.sender, uint64(block.timestamp), size);
        nextBatchId = id + 1;
        emit BatchAnchored(id, root, msg.sender, size);
    }

    function attestationDigest(uint256 id, bytes32 root, uint256 size, address submitter)
        public
        view
        returns (bytes32)
    {
        bytes32 domain = keccak256(
            abi.encode(DOMAIN_TYPEHASH, keccak256("DAGAnchor"), keccak256("1"), block.chainid, address(this))
        );
        bytes32 message = keccak256(abi.encode(BATCH_TYPEHASH, id, root, size, submitter));
        return keccak256(abi.encodePacked(hex"1901", domain, message));
    }

    function verifyAttestation(
        uint256 id,
        bytes32 root,
        uint256 size,
        address submitter,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public view returns (bool) {
        if ((v != 27 && v != 28) || uint256(s) > MAX_S) return false;
        return ecrecover(attestationDigest(id, root, size, submitter), v, r, s) == attester;
    }

    function verifyInclusion(bytes32 nodeHash, address publisher, bytes32[] calldata proof, uint256 batchId)
        public
        view
        returns (bool)
    {
        bytes32 root = batches[batchId].root;
        if (root == bytes32(0)) return false;
        bytes32 hash = sha256(abi.encodePacked(bytes1(0x00), nodeHash, publisher));
        for (uint256 i; i < proof.length; ++i) {
            bytes32 sibling = proof[i];
            (bytes32 first, bytes32 second) = hash < sibling ? (hash, sibling) : (sibling, hash);
            hash = sha256(abi.encodePacked(bytes1(0x01), first, second));
        }
        return hash == root;
    }

    function verifyAnchored(
        bytes32 nodeHash,
        address publisher,
        bytes32[] calldata proof,
        uint256 batchId,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external view returns (bool) {
        Batch storage batch = batches[batchId];
        return verifyInclusion(nodeHash, publisher, proof, batchId)
            && verifyAttestation(batchId, batch.root, batch.size, batch.submitter, v, r, s);
    }
}
