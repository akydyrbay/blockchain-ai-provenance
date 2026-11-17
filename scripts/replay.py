#!/usr/bin/env python3
"""Replay the committed workloads on fresh local Anvil chains."""
import argparse
import csv
import hashlib
import json
import os
import platform
import random
import sys
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import requests
from eth_account import Account
from web3 import Web3, __version__ as web3_version
from web3.exceptions import ContractLogicError

from attester import Attester, Parent, node_hash
from registry_checks import integrity_cases, registration_cases

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {
    "permissive": 0, "copyleft": 1, "restricted-use": 2,
    "non-commercial": 3, "no-derivatives": 4, "unknown": 5,
}
ZERO = bytes(32)
CONFIGURATIONS = {"D1": ("D1", 1), "D2": ("D2", 1), "D3-1": ("D3", 1),
                  "D3-16": ("D3", 16), "D3-128": ("D3", 128)}


@dataclass(frozen=True)
class Record:
    index: int
    name: str
    uri: str
    depth: int
    parents: tuple
    publisher: str
    licence: int
    weights: bytes
    dataset: bytes
    metadata: bytes

    def arguments(self, ids):
        return (
            self.name, self.uri, self.weights, self.dataset, self.metadata,
            [ids.get(parent, 2**256 - 1) for parent in self.parents],
        ), self.licence


def read_records(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return [
            Record(
                int(row["plan_index"]), row["model_id"],
                f"https://huggingface.co/{row['model_id']}/tree/{row['repo_sha']}"
                if row["repo_sha"] else "synthetic:" + row["model_id"],
                int(row["depth"]), tuple(map(int, filter(None, row["parent_indices"].split(";")))),
                row["publisher"], CLASSES[row["licence_class"]],
                Web3.to_bytes(hexstr=row["weights_hash"]), Web3.to_bytes(hexstr=row["data_ref_hash"]),
                Web3.to_bytes(hexstr=row["meta_hash"]),
            )
            for row in csv.DictReader(stream)
        ]


def lineage(target, records):
    parents = set()
    pending = list(target.parents)
    while pending:
        index = pending.pop()
        if index not in parents:
            parents.add(index)
            pending.extend(records[index].parents)
    return parents


def smoke_records(records):
    by_id = {record.index: record for record in records}
    merge = next(record for record in records if len(record.parents) > 1)
    selected = lineage(merge, by_id) | {merge.index}
    return [record for record in records if record.index in selected]


def executable(name):
    path = shutil.which(name)
    if not path and name in ("forge", "anvil"):
        path = Path.home() / ".foundry" / "bin" / name
    if not path or not Path(path).is_file():
        raise FileNotFoundError(f"Provide {name} on PATH")
    return str(path)


@contextmanager
def server(command, ready):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(command(port), stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError(f"Local server exited with {process.returncode}")
            if ready(url):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError(f"Local server did not become ready at {url}")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def opa_ready(url):
    try:
        return requests.get(url + "/health", timeout=0.3).ok
    except requests.ConnectionError:
        return False


def provider(url):
    return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 20}))


def anvil_server(anvil):
    return server(
        lambda port: [anvil, "--host", "127.0.0.1", "--port", str(port),
                      "--chain-id", "31337", "--hardfork", "cancun", "--silent"],
        lambda url: provider(url).is_connected(),
    )


def rpc(w3, method, params):
    response = w3.provider.make_request(method, params)
    if "error" in response:
        raise RuntimeError(f"{method}: {response['error']}")
    return response["result"]


def deploy(w3, admin, name, *args):
    source = "ModelRegistry" if name == "AIModelRegistry" else name
    artifact = json.loads((ROOT / "out" / f"{source}.sol" / f"{name}.json").read_text())
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
    receipt = receipt_for(w3, factory.constructor(*args).transact({"from": admin, "gas": 12_000_000}))
    return w3.eth.contract(address=receipt.contractAddress, abi=artifact["abi"]), receipt


def receipt_for(w3, tx):
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=30)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {Web3.to_hex(tx)}")
    return receipt


def account_for(name):
    return Account.from_key(hashlib.sha256(f"provenance-local-v1:42:{name}".encode()).digest())


def as_signer(w3, account, operation, nonces):
    sender = account.address
    if sender not in nonces:
        rpc(w3, "anvil_setBalance", [sender, hex(10**20)])
        nonces[sender] = w3.eth.get_transaction_count(sender)
    tx = operation.build_transaction({
        "from": sender, "nonce": nonces[sender], "gas": 4_000_000,
        "gasPrice": 3_000_000_000, "chainId": 31337,
    })
    signed = account.sign_transaction(tx)
    receipt = receipt_for(w3, w3.eth.send_raw_transaction(signed.raw_transaction))
    nonces[sender] += 1
    return receipt


def state_bytes(w3, receipt, address):
    diff = rpc(w3, "debug_traceTransaction", [Web3.to_hex(receipt.transactionHash), {
        "tracer": "prestateTracer", "tracerConfig": {"diffMode": True},
    }])
    previous = diff["pre"].get(address.lower(), {}).get("storage", {})
    after = diff["post"].get(address.lower(), {}).get("storage", {})
    return 32 * sum(
        int(value, 16) != 0 and int(previous.get(slot, "0x0"), 16) == 0
        for slot, value in after.items()
    )


def gas_row(w3, design, batch_size, address, operation, records, receipt):
    new_bytes = state_bytes(w3, receipt, address)
    return {
        "design": design, "batch_size": batch_size, "operation": operation,
        "models": len(records), "model_indices": ";".join(str(r.index) for r in records),
        "depth": records[0].depth if len(records) == 1 else "",
        "n_parents": len(records[0].parents) if len(records) == 1 else "",
        "gas": receipt.gasUsed, "new_state_bytes": new_bytes,
        "gas_per_model": receipt.gasUsed / len(records) if records else "",
        "state_bytes_per_model": new_bytes / len(records) if records else "",
        "tx_hash": Web3.to_hex(receipt.transactionHash), "block": receipt.blockNumber,
        "contract": address,
    }


def verify_storage(w3, registry, target, records, ids, publishers):
    ancestors = lineage(target, records)
    expected = [records[index] for index in sorted(ancestors)] + [target]
    with w3.batch_requests() as rpc_batch:
        rpc_batch.add(registry.functions.getLineage(ids[target.index]))
        for record in expected:
            model_id = ids[record.index]
            rpc_batch.add(registry.functions.getParents(model_id))
            rpc_batch.add(registry.functions.getModel(model_id))
            rpc_batch.add(registry.functions.getVersion(model_id, 0))
        results = rpc_batch.execute()

    if set(results[0]) != {ids[i] for i in ancestors}:
        return False
    for offset, record in enumerate(expected):
        parents, model, version = results[1 + 3 * offset:4 + 3 * offset]
        if parents != [ids[i] for i in record.parents]:
            return False
        if (model[1], model[2], version[0], version[1], version[2], version[3], version[5]) != (
            record.name, record.uri, record.weights, record.dataset, record.uri,
            [record.metadata], publishers[record.publisher],
        ):
            return False
    return True


def anchor_call(anchor, target, records, proofs, publishers):
    nodes = {}
    for index in sorted(lineage(target, records) | {target.index}):
        record = target if index == target.index else records[index]
        nodes[index] = node_hash(record.weights, record.dataset,
                                 (nodes[parent] for parent in record.parents), record.metadata)
    batch_id, proof, signature = proofs[target.index]
    return anchor.functions.verifyAnchored(
        nodes[target.index], publishers[target.publisher], proof, batch_id, *signature,
    )


def time_calls(operation):
    for _ in range(5):
        operation()
    for i in range(30):
        start = time.perf_counter_ns()
        result = operation()
        yield i + 1, (time.perf_counter_ns() - start) / 1_000_000, result


def sampled_records(records, synthetic):
    if synthetic:
        return records
    random_seeded = random.Random(42)
    selected = {record.index for record in records if len(record.parents) > 1}
    for depth in sorted({record.depth for record in records}):
        group = [record.index for record in records if record.depth == depth]
        selected.update(random_seeded.sample(group, min(10, len(group))))
    return [record for record in records if record.index in selected]


def verify_measurements(w3, design, size, records, samples, verify, gas_query, address):
    probe, _ = deploy(w3, w3.eth.accounts[0], "VerifyProbe")
    verification_rows, gas_rows, audit_rows = [], [], []
    for target in samples:
        fields = {
            "design": design, "batch_size": size, "model_index": target.index, "depth": target.depth,
            "n_parents": len(target.parents),
        }
        for trial, milliseconds, accepted in time_calls(lambda: verify(target)):
            if not accepted:
                raise AssertionError(f"{design} did not verify {target.name}")
            verification_rows.append(dict(fields, trial=trial, milliseconds=milliseconds))
        gas_used, _ = probe.functions.measure(address, gas_query(target)._encode_transaction_data()).call()
        gas_rows.append(dict(fields, gas=gas_used))
    for trial in range(1, 6):
        start = time.perf_counter_ns()
        for target in records:
            if not verify(target):
                raise AssertionError(f"{design} audit failed for {target.name}")
        seconds = (time.perf_counter_ns() - start) / 1_000_000_000
        audit_rows.append({"design": design, "batch_size": size, "trial": trial, "seconds": seconds,
                           "models": len(records), "models_per_second": len(records) / seconds})
    return verification_rows, gas_rows, audit_rows


def assert_policy_equivalence(w3, opa_url, records):
    """Exercise the same controlled policy inputs against a disposable D2 and OPA state."""
    admin, publisher, outsider = w3.eth.accounts[:3]
    contract, _ = deploy(w3, admin, "PolicyRegistry")
    base = replace(records[0], index=0, parents=(), licence=0)
    anchor_state = Attester(account_for("equivalence"), opa_url, [base.dataset], [publisher])
    receipt_for(w3, contract.functions.configure([base.dataset], [publisher], True).transact({"from": admin}))
    ids = {0: 0, 1: 1}
    for index, licence in ((0, 0), (1, 4), (2, 3)):
        root = replace(base, index=index, licence=licence, weights=hashlib.sha256(bytes([index])).digest())
        ids[index] = index
        receipt_for(w3, contract.functions.registerProvenance(*root.arguments(ids)).transact({"from": publisher}))
        anchor_state.parents[index] = Parent(index, licence)
        anchor_state.weights.add(root.weights)
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
            receipt_for(w3, contract.functions.setRevoked(0, True).transact({"from": admin}))
            anchor_state.parents[0] = Parent(0, 0, True)
        try:
            contract.functions.registerProvenance(*record.arguments(ids)).call({"from": sender})
            solidity = True
        except ContractLogicError:
            solidity = False
        rego, _ = anchor_state.decision(record, sender)
        if solidity != rego or rego != expected:
            raise AssertionError(f"{name}: Solidity={solidity}, OPA={rego}, expected={expected}")
        output.append({"case": name, "expected": expected, "solidity": solidity, "rego": rego})
    return output


def replay(w3, opa_url, design, size, records, mode):
    admin = w3.eth.accounts[0]
    accounts = {name: account_for("publisher:" + name) for name in sorted({r.publisher for r in records})}
    publishers = {name: account.address for name, account in accounts.items()}
    datasets = sorted({r.dataset for r in records})
    name = {"D1": "AIModelRegistry", "D2": "PolicyRegistry", "D3": "DAGAnchor"}[design]
    signer = account_for("attester")
    args = (signer.address,) if design == "D3" else ()
    contract, deployed = deploy(w3, admin, name, *args)
    rows = [gas_row(w3, design, size, contract.address, "deploy", [], deployed)]
    ids, proofs, nonces = {}, {}, {}
    policy_rows = []
    samples = sampled_records(records, mode == "synthetic")
    sample_ids = {record.index for record in samples} if mode in ("full", "synthetic") else set()

    def record_policy_latency(record, operation):
        if record.index not in sample_ids:
            return
        for trial, milliseconds, metrics in time_calls(operation):
            policy_rows.append({
                "design": design, "batch_size": size, "model_index": record.index, "depth": record.depth,
                "trial": trial, "milliseconds": milliseconds,
                "opa_eval_ns": metrics.get("timer_rego_query_eval_ns", "") if isinstance(metrics, dict) else "",
            })
    if design == "D2":
        addresses = list(publishers.values())
        for offset in range(0, len(addresses), 100):
            call = contract.functions.configure(datasets if offset == 0 else [], addresses[offset:offset + 100], True)
            setup = receipt_for(w3, call.transact({"from": admin, "gas": 12_000_000}))
            rows.append(gas_row(w3, design, size, contract.address, "configure", [], setup))
    if design == "D3":
        attester = Attester(signer, opa_url, datasets, publishers.values())
        def observe(record, publisher):
            record_policy_latency(record, lambda: attester.decision(record, publisher)[1])

        for offset in range(0, len(records), size):
            batch_records = records[offset:offset + size]
            receipt, batch_id, batch, signature = attester.anchor(
                batch_records, publishers, contract,
                lambda call: receipt_for(w3, call.transact({"from": admin, "gas": 4_000_000})),
                w3.eth.chain_id, admin, observe,
            )
            for i, record in enumerate(batch_records):
                proofs[record.index] = batch_id, batch.proof(i), signature
            rows.append(gas_row(w3, design, size, contract.address, "register", batch_records, receipt))
    else:
        for model_id, record in enumerate(records):
            call = contract.functions.registerProvenance(*record.arguments(ids))
            if design == "D2":
                record_policy_latency(record, lambda: call.call({"from": accounts[record.publisher].address}))
            receipt = as_signer(w3, accounts[record.publisher], call, nonces)
            ids[record.index] = model_id
            rows.append(gas_row(w3, design, size, contract.address, "register", [record], receipt))

    by_id = {r.index: r for r in records}
    if design == "D3":
        def query(target):
            return anchor_call(contract, target, by_id, proofs, publishers)

        def verify(target):
            return query(target).call()
    else:
        def query(target):
            return contract.functions.getLineage(ids[target.index])

        def verify(target):
            return verify_storage(w3, contract, target, by_id, ids, publishers)

    def decide(record, sender):
        if design == "D3":
            accepted, _ = attester.decision(record, sender)
            return accepted, "OPA allowed" if accepted else "OPA denied"
        try:
            contract.functions.registerProvenance(*record.arguments(ids)).call({"from": sender})
            return True, "eth_call allowed"
        except ContractLogicError as error:
            return False, str(error)

    print(f"{design} k={size}: registered {len(records)}", flush=True)
    checked, admission = [], []
    if mode in ("smoke", "checks"):
        checked = integrity_cases(records, verify, design, size)
        admission = registration_cases(records, publishers, w3.eth.accounts[2], decide, design, size)
        timed, gas, audit = [], [], []
    else:
        timed, gas, audit = verify_measurements(w3, design, size, records, samples, verify, query, contract.address)
    print(f"{design} k={size}: registered {len(records)} and completed lineage checks", flush=True)
    return {
        "gas.csv": rows, "policy_latency.csv": policy_rows, "verify_latency.csv": timed,
        "verify_gas.csv": gas, "audit_throughput.csv": audit, "integrity_cases.csv": checked,
        "registration_cases.csv": admission,
    }


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full", "synthetic", "checks"), default="smoke")
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
        "configurations": configurations, "mode": args.mode, "started_utc": timestamp, "chain_id": 31337, "seed": 42, "hardfork": "cancun",
        "host": {"os": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
        "python": sys.version, "web3": web3_version, "command": sys.argv,
        "input": str(path.relative_to(ROOT)), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model_indices": [record.index for record in records],
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for pattern in ("src/*.sol", "policy/*.rego", "scripts/replay.py", "scripts/attester.py",
                                          "scripts/registry_checks.py", "foundry.toml", "requirements.txt") for p in sorted(ROOT.glob(pattern))},
        "versions": {name: subprocess.check_output([cmd, "version" if name == "opa" else "--version"],
                                                   text=True).strip()
                     for name, cmd in (("forge", forge), ("anvil", anvil), ("opa", opa))},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    with server(lambda port: [opa, "run", "--server", "--log-level", "error", "--addr", f"127.0.0.1:{port}",
                              str(ROOT / "policy" / "provenance.rego")], opa_ready) as endpoint:
        with anvil_server(anvil) as url:
            write_csv(args.out / "policy_equivalence.csv", assert_policy_equivalence(provider(url), endpoint, records))
        outputs = {}
        for config in configurations:
            design, size = CONFIGURATIONS[config]
            with anvil_server(anvil) as url:
                run = replay(provider(url), endpoint, design, size, records, args.mode)
            for filename, rows in run.items():
                if rows:
                    outputs.setdefault(filename, []).extend(rows)
                    write_csv(args.out / filename, outputs[filename])
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
