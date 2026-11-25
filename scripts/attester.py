#!/usr/bin/env python3
"""Evaluate OPA decisions and commit approved provenance into signed Merkle batches."""

import hashlib
from dataclasses import dataclass

import requests
from eth_account.messages import encode_typed_data

BATCH_FIELDS = [
    {"name": "batchId", "type": "uint256"},
    {"name": "root", "type": "bytes32"},
    {"name": "size", "type": "uint256"},
    {"name": "submitter", "type": "address"},
]


def sha256(value):
    return hashlib.sha256(value).digest()


def node_hash(weights, dataset, parents, metadata):
    return sha256(weights + dataset + b"".join(sorted(parents)) + metadata)


def leaf_hash(node, publisher):
    return sha256(b"\x00" + node + bytes.fromhex(publisher[2:]))


def pair_hash(first, second):
    return sha256(b"\x01" + b"".join(sorted((first, second))))


class MerkleBatch:
    def __init__(self, leaves):
        if not leaves:
            raise ValueError("Cannot anchor an empty batch")
        self.layers = [leaves]
        while len(self.layers[-1]) > 1:
            level = self.layers[-1]
            self.layers.append([
                pair_hash(level[i], level[min(i + 1, len(level) - 1)])
                for i in range(0, len(level), 2)
            ])

    @property
    def root(self):
        return self.layers[-1][0]

    def proof(self, index):
        if not 0 <= index < len(self.layers[0]):
            raise IndexError(index)
        siblings = []
        for level in self.layers[:-1]:
            siblings.append(level[min(index ^ 1, len(level) - 1)])
            index //= 2
        return siblings


def sign_batch(account, chain_id, contract, batch_id, root, size, submitter):
    domain = {
        "name": "DAGAnchor", "version": "1", "chainId": chain_id, "verifyingContract": contract,
    }
    message = {"batchId": batch_id, "root": root, "size": size, "submitter": submitter}
    signed = account.sign_message(encode_typed_data(domain, {"Batch": BATCH_FIELDS}, message))
    return signed.v, signed.r.to_bytes(32, "big"), signed.s.to_bytes(32, "big")


@dataclass(frozen=True)
class Parent:
    id: int
    licence: int
    revoked: bool = False


class Attester:
    """Owns the policy state. Callers supply records, never authorization flags."""

    def __init__(self, account, endpoint, allowed_datasets, publishers):
        self.account = account
        self.endpoint = endpoint.rstrip("/") + "/v1/data/provenance/allow"
        self.session = requests.Session()
        self.allowed_datasets = frozenset(allowed_datasets)
        self.publishers = frozenset(publishers)
        self.parents = {}
        self.weights = set()
        self.nodes = {}

    def decision(self, record, publisher):
        parents = []
        for index in record.parents:
            parent = self.parents.get(index)
            parents.append({
                "id": index, "registered": parent is not None,
                "revoked": parent.revoked if parent else False,
                "licence": parent.licence if parent else 5,
            })
        response = self.session.post(self.endpoint, json={"input": {
            "licence": record.licence,
            "weights_valid": len(record.weights) == 32 and any(record.weights),
            "dataset_valid": len(record.dataset) == 32 and any(record.dataset),
            "duplicate_weights": record.weights in self.weights,
            "dataset_allowed": record.dataset in self.allowed_datasets,
            "publisher_allowed": publisher in self.publishers,
            "parents": parents,
        }}, params={"metrics": "true"}, timeout=10)
        response.raise_for_status()
        body = response.json()
        decision = body.get("result")
        if type(decision) is not bool:
            raise ValueError("OPA returned no boolean provenance decision")
        return decision, body.get("metrics", {})

    def anchor(self, records, publishers, contract, send, chain_id, submitter, observe):
        staged = []
        leaves = []
        try:
            for record in records:
                publisher = publishers[record.publisher]
                observe(record, publisher)
                if record.index in self.parents or not self.decision(record, publisher)[0]:
                    raise ValueError(f"OPA refused registration of {record.name}")
                node = node_hash(record.weights, record.dataset,
                                 (self.nodes[parent] for parent in record.parents), record.metadata)
                self.parents[record.index] = Parent(record.index, record.licence)
                self.nodes[record.index] = node
                self.weights.add(record.weights)
                staged.append(record)
                leaves.append(leaf_hash(node, publisher))

            batch = MerkleBatch(leaves)
            batch_id = contract.functions.nextBatchId().call()
            signature = sign_batch(self.account, chain_id, contract.address, batch_id,
                                   batch.root, len(staged), submitter)
            receipt = send(contract.functions.anchor(batch.root, len(staged), *signature))
        except Exception:
            for record in staged:
                del self.parents[record.index]
                del self.nodes[record.index]
                self.weights.remove(record.weights)
            raise
        return receipt, batch_id, batch, signature
