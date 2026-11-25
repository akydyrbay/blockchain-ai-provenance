#!/usr/bin/env python3
"""Export and independently verify D3 lineage against a specified on-chain anchor."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from web3 import Web3
from web3.exceptions import ContractLogicError

from replay import ROOT, anchor_call, lineage, provider, read_records

PLAN = ROOT / "data/registration_plan.csv"


def record_commitments(record):
    return {
        "parents": list(record.parents),
        "weights": Web3.to_hex(record.weights),
        "dataset": Web3.to_hex(record.dataset),
        "metadata": Web3.to_hex(record.metadata),
    }


def proof_bundle(chain_id, address, records, proofs, publishers):
    entries = {}
    for record in records:
        batch_id, siblings, (v, r, s) = proofs[record.index]
        entries[str(record.index)] = {
            **record_commitments(record),
            "publisher": publishers[record.publisher],
            "batch_id": batch_id,
            "siblings": [Web3.to_hex(sibling) for sibling in siblings],
            "signature": [v, Web3.to_hex(r), Web3.to_hex(s)],
        }
    return {"chain_id": chain_id, "anchor": address, "plan_sha256": plan_hash(PLAN), "records": entries}


def plan_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(w3, bundle, chain_id, anchor, model_index, plan):
    if w3.eth.chain_id != chain_id or bundle["chain_id"] != chain_id:
        raise ValueError("Wrong chain for proof bundle")
    address = Web3.to_checksum_address(anchor)
    if Web3.to_checksum_address(bundle["anchor"]) != address:
        raise ValueError("Wrong anchor for proof bundle")
    if bundle["plan_sha256"] != plan_hash(plan):
        raise ValueError("Registration plan hash differs from proof bundle")
    if not w3.eth.get_code(address):
        raise ValueError("No contract at expected anchor address")

    records = {record.index: record for record in read_records(plan)}
    target = records[model_index]
    required = sorted(lineage(target, records) | {model_index})
    publishers, proofs = {}, {}
    for index in required:
        record = records[index]
        entry = bundle["records"][str(index)]
        commitments = record_commitments(record)
        if any(entry[field] != value for field, value in commitments.items()):
            raise ValueError(f"Exported commitments differ from plan for model index {index}")
        publisher = Web3.to_checksum_address(entry["publisher"])
        if publishers.setdefault(record.publisher, publisher) != publisher:
            raise ValueError(f"Conflicting publisher mapping for model index {index}")
        v, r, s = entry["signature"]
        proofs[index] = (entry["batch_id"], [Web3.to_bytes(hexstr=sibling) for sibling in entry["siblings"]],
                         (v, Web3.to_bytes(hexstr=r), Web3.to_bytes(hexstr=s)))

    abi = json.loads((ROOT / "out/DAGAnchor.sol/DAGAnchor.json").read_text())["abi"]
    registry = w3.eth.contract(address=address, abi=abi)
    for index in required:
        if not anchor_call(registry, records[index], records, proofs, publishers).call():
            raise ValueError(f"Invalid on-chain proof or attestation for model index {index}")
    return len(required) - 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--rpc-url", default=os.environ.get("SEPOLIA_RPC_URL") or os.environ.get("ALCHEMY_SEPOLIA_URL"))
    parser.add_argument("--chain-id", type=int, required=True)
    parser.add_argument("--anchor", required=True, help="Expected address from the deployment receipt")
    parser.add_argument("--model-index", type=int, required=True, help="Target plan_index from the registration plan")
    args = parser.parse_args()
    if not args.rpc_url:
        parser.error("Set SEPOLIA_RPC_URL or provide --rpc-url")
    try:
        bundle = json.loads(args.bundle.read_text())
        ancestors = verify_bundle(provider(args.rpc_url), bundle, args.chain_id, args.anchor, args.model_index, args.plan)
    except (KeyError, TypeError, ValueError, ContractLogicError) as error:
        parser.exit(1, f"NOT VERIFIED: {error}\n")
    print(f"VERIFIED: model index {args.model_index} and {ancestors} ancestors")


if __name__ == "__main__":
    main()
