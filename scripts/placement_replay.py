#!/usr/bin/env python3
"""Controlled policy-placement replay on fresh local Anvil chains.

C-Sol and C-OPA inherit one registry contract (src/PlacementRegistry.sol), so they write
the same storage per model, register one publisher-signed transaction per model, and are
audited by the same storage verifier as D1 and D2. Only the admission decision moves:
C-Sol evaluates the D2 rules in Solidity, whereas C-OPA asks OPA and submits the
attester's signature over the record with the transaction.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from eth_abi import encode
from eth_account.messages import encode_typed_data
from web3 import Web3, __version__ as web3_version
from web3.exceptions import ContractLogicError

from attester import Attester, Parent
from registry_checks import registration_cases
from replay import (
    ROOT, ZERO, account_for, anvil_server, as_signer, executable, gas_row, opa_ready, provider,
    read_records, receipt_for, sampled_records, server, smoke_records, time_calls, verify_measurements,
    verify_storage, write_csv,
)

CONFIGURATIONS = {"C-Sol": "SolidityPolicyPlacement", "C-OPA": "OpaPolicyPlacement"}
ADMISSION_FIELDS = [
    {"name": "modelId", "type": "uint256"},
    {"name": "record", "type": "bytes32"},
    {"name": "licence", "type": "uint8"},
    {"name": "publisher", "type": "address"},
]


def deploy_placement(w3, admin, name, *args):
    artifact = json.loads((ROOT / "out" / "PlacementRegistry.sol" / f"{name}.json").read_text())
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
    receipt = receipt_for(w3, factory.constructor(*args).transact({"from": admin, "gas": 12_000_000}))
    return w3.eth.contract(address=receipt.contractAddress, abi=artifact["abi"]), receipt


def record_digest(fields):
    """Python mirror of OpaPolicyPlacement.recordDigest for the contract-level arguments."""
    name, uri, weights, dataset, metadata, parents = fields
    packed = b"".join(parent.to_bytes(32, "big") for parent in parents)
    return Web3.keccak(encode(
        ["bytes32"] * 6,
        [Web3.keccak(text=name), Web3.keccak(text=uri), weights, dataset, metadata, Web3.keccak(packed)],
    ))


class AdmissionService:
    """OPA decision followed, if allowed, by a signed admission for one exact record."""

    def __init__(self, signer, opa_url, datasets, publishers, chain_id, contract):
        self.attester = Attester(signer, opa_url, datasets, publishers)
        self.signer = signer
        self.domain = {"name": "OpaPolicyPlacement", "version": "1", "chainId": chain_id,
                       "verifyingContract": contract}

    def ticket(self, record, fields, licence, publisher, model_id):
        if not self.attester.decision(record, publisher)[0]:
            return None
        message = {"modelId": model_id, "record": record_digest(fields), "licence": licence,
                   "publisher": publisher}
        signed = self.signer.sign_message(encode_typed_data(self.domain, {"Admission": ADMISSION_FIELDS}, message))
        return signed.r.to_bytes(32, "big") + signed.s.to_bytes(32, "big") + bytes([signed.v])

    def commit(self, record):
        self.attester.parents[record.index] = Parent(record.index, record.licence)
        self.attester.weights.add(record.weights)


def submit(contract, fields, licence, decision, sender):
    try:
        contract.functions.registerProvenance(fields, licence, decision).call({"from": sender})
        return True, "eth_call allowed"
    except ContractLogicError as error:
        return False, str(error)


def placement_equivalence(w3, opa_url, records):
    """Run the D2/D3 policy-equivalence cases against both controlled variants."""
    admin, publisher, outsider = w3.eth.accounts[:3]
    base = replace(records[0], index=0, parents=(), licence=0)
    solidity, _ = deploy_placement(w3, admin, CONFIGURATIONS["C-Sol"])
    signer = account_for("placement-equivalence")
    opa, _ = deploy_placement(w3, admin, CONFIGURATIONS["C-OPA"], signer.address)
    service = AdmissionService(signer, opa_url, [base.dataset], [publisher], w3.eth.chain_id, opa.address)
    receipt_for(w3, solidity.functions.configure([base.dataset], [publisher], True).transact({"from": admin}))
    ids = {}
    for index, licence in ((0, 0), (1, 4), (2, 3)):
        root = replace(base, index=index, licence=licence, weights=hashlib.sha256(bytes([index])).digest())
        fields, _ = root.arguments(ids)
        receipt_for(w3, solidity.functions.registerProvenance(fields, licence, b"").transact({"from": publisher}))
        decision = service.ticket(root, fields, licence, publisher, index)
        receipt_for(w3, opa.functions.registerProvenance(fields, licence, decision).transact({"from": publisher}))
        service.commit(root)
        ids[index] = index
    normal = replace(base, index=3, parents=(0,), weights=hashlib.sha256(b"test candidate").digest())
    tests = [
        ("clean", normal, publisher, True),
        ("clean_merge", replace(normal, parents=(0, 2), licence=3), publisher, True),
        ("unregistered_parent", replace(normal, parents=(100,)), publisher, False),
        ("duplicate_parent", replace(normal, parents=(0, 0)), publisher, False),
        ("missing_weights", replace(normal, weights=ZERO), publisher, False),
        ("missing_dataset", replace(normal, dataset=ZERO), publisher, False),
        ("duplicate_weights", replace(normal, weights=hashlib.sha256(bytes([0])).digest()), publisher, False),
        ("unlisted_dataset", replace(normal, dataset=bytes([1]) * 32), publisher, False),
        ("unauthorized_publisher", normal, outsider, False),
        ("unknown_child", replace(normal, licence=5, parents=(2,)), publisher, True),
        ("invalid_licence_class", replace(normal, licence=6), publisher, False),
        ("stricter_parent", replace(normal, parents=(2,)), publisher, False),
        ("no_derivatives", replace(normal, licence=5, parents=(1,)), publisher, False),
        ("revoked_parent", normal, publisher, False),
    ]
    output = []
    for name, record, sender, expected in tests:
        if name == "revoked_parent":
            receipt_for(w3, solidity.functions.setRevoked(0, True).transact({"from": admin}))
            service.attester.parents[0] = Parent(0, 0, True)
        fields, licence = record.arguments(ids)
        on_chain, _ = submit(solidity, fields, licence, b"", sender)
        decision = service.ticket(record, fields, licence, sender, 3)
        off_chain = decision is not None and submit(opa, fields, licence, decision, sender)[0]
        if on_chain != off_chain or off_chain != expected:
            raise AssertionError(f"{name}: C-Sol={on_chain}, C-OPA={off_chain}, expected={expected}")
        output.append({"case": name, "expected": expected, "c_sol": on_chain, "c_opa": off_chain})
    return output


def replay(w3, opa_url, design, records, mode):
    admin = w3.eth.accounts[0]
    accounts = {name: account_for("publisher:" + name) for name in sorted({r.publisher for r in records})}
    publishers = {name: account.address for name, account in accounts.items()}
    datasets = sorted({r.dataset for r in records})
    signer = account_for("attester")
    args = (signer.address,) if design == "C-OPA" else ()
    contract, deployed = deploy_placement(w3, admin, CONFIGURATIONS[design], *args)
    rows = [gas_row(w3, design, 1, contract.address, "deploy", [], deployed)]
    ids, nonces, policy_rows = {}, {}, []
    samples = sampled_records(records, mode == "synthetic")
    sample_ids = {record.index for record in samples} if mode in ("full", "synthetic") else set()
    service = None
    if design == "C-Sol":
        addresses = list(publishers.values())
        for offset in range(0, len(addresses), 100):
            call = contract.functions.configure(datasets if offset == 0 else [], addresses[offset:offset + 100], True)
            setup = receipt_for(w3, call.transact({"from": admin, "gas": 12_000_000}))
            rows.append(gas_row(w3, design, 1, contract.address, "configure", [], setup))
    else:
        service = AdmissionService(signer, opa_url, datasets, publishers.values(), w3.eth.chain_id, contract.address)

    for model_id, record in enumerate(records):
        fields, licence = record.arguments(ids)
        sender = accounts[record.publisher].address
        if design == "C-OPA":
            def decide():
                return service.ticket(record, fields, licence, sender, model_id)
        else:
            def decide():
                return contract.functions.registerProvenance(fields, licence, b"").call({"from": sender})
        if record.index in sample_ids:
            for trial, milliseconds, _ in time_calls(decide):
                policy_rows.append({"design": design, "batch_size": 1, "model_index": record.index,
                                    "depth": record.depth, "trial": trial, "milliseconds": milliseconds})
        decision = b""
        if design == "C-OPA":
            decision = None if record.index in service.attester.parents else decide()
            if decision is None:
                raise ValueError(f"OPA refused registration of {record.name}")
        receipt = as_signer(w3, accounts[record.publisher],
                            contract.functions.registerProvenance(fields, licence, decision), nonces)
        ids[record.index] = model_id
        if service:
            service.commit(record)
        rows.append(gas_row(w3, design, 1, contract.address, "register", [record], receipt))

    by_id = {r.index: r for r in records}

    def query(target):
        return contract.functions.getLineage(ids[target.index])

    def verify(target):
        return verify_storage(w3, contract, target, by_id, ids, publishers)

    def decide_candidate(record, sender):
        fields, licence = record.arguments(ids)
        decision = b""
        if design == "C-OPA":
            decision = service.ticket(record, fields, licence, sender, len(records))
            if decision is None:
                return False, "OPA denied"
        return submit(contract, fields, licence, decision, sender)

    print(f"{design}: registered {len(records)}", flush=True)
    admission = registration_cases(records, publishers, w3.eth.accounts[2], decide_candidate, design, 1)
    timed, gas, audit = [], [], []
    if mode in ("full", "synthetic"):
        timed, gas, audit = verify_measurements(w3, design, 1, records, samples, verify, query, contract.address)
    print(f"{design}: completed admission and verification checks", flush=True)
    return {
        "gas.csv": rows, "policy_latency.csv": policy_rows, "verify_latency.csv": timed,
        "verify_gas.csv": gas, "audit_throughput.csv": audit, "registration_cases.csv": admission,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full", "synthetic"), default="smoke")
    parser.add_argument("--configuration", action="append", choices=CONFIGURATIONS,
                        help="Run only the named configurations. Repeat to choose several.")
    parser.add_argument("--out", type=Path, required=True, help="New directory for this run's artifacts")
    parser.add_argument("--opa", default=os.environ.get("OPA", "opa"), help="Path to the OPA executable")
    args = parser.parse_args()
    forge, anvil, opa = map(executable, ("forge", "anvil", args.opa))
    args.out.mkdir(parents=True, exist_ok=False)
    timestamp = datetime.now(timezone.utc).isoformat()
    subprocess.run([forge, "build", "--offline"], cwd=ROOT, check=True)
    path = ROOT / "data" / ("synthetic_chain.csv" if args.mode == "synthetic" else "registration_plan.csv")
    records = read_records(path)
    if args.mode == "smoke":
        records = smoke_records(records)
    configurations = list(dict.fromkeys(args.configuration or CONFIGURATIONS))
    manifest = {
        "experiment": "controlled policy placement", "configurations": configurations, "mode": args.mode,
        "started_utc": timestamp, "chain_id": 31337, "seed": 42, "hardfork": "cancun",
        "host": {"os": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
        "python": sys.version, "web3": web3_version, "command": sys.argv,
        "input": str(path.relative_to(ROOT)), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model_indices": [record.index for record in records],
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for pattern in ("src/*.sol", "policy/*.rego", "scripts/replay.py", "scripts/attester.py",
                                          "scripts/placement_replay.py", "scripts/registry_checks.py",
                                          "foundry.toml", "requirements.txt") for p in sorted(ROOT.glob(pattern))},
        "versions": {name: subprocess.check_output([cmd, "version" if name == "opa" else "--version"],
                                                   text=True).strip()
                     for name, cmd in (("forge", forge), ("anvil", anvil), ("opa", opa))},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
    }
    with server(lambda port: [opa, "run", "--server", "--log-level", "error", "--addr", f"127.0.0.1:{port}",
                              str(ROOT / "policy" / "provenance.rego")], opa_ready) as endpoint:
        with anvil_server(anvil) as url:
            write_csv(args.out / "policy_equivalence.csv", placement_equivalence(provider(url), endpoint, records))
        outputs = {}
        for design in configurations:
            with anvil_server(anvil) as url:
                run = replay(provider(url), endpoint, design, records, args.mode)
            for filename, rows in run.items():
                if rows:
                    outputs.setdefault(filename, []).extend(rows)
                    write_csv(args.out / filename, outputs[filename])
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
