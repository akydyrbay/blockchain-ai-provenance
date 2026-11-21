#!/usr/bin/env python3
"""Compare receipt gas for the same provenance sample on Anvil and Sepolia."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

from eth_account import Account
from web3 import Web3

from attester import Attester
from replay import (
    ROOT, account_for, anchor_call, executable, lineage, opa_ready, provider, read_records,
    rpc, server, verify_storage, write_csv,
)

SEPOLIA = 11155111
CONFIGURATIONS = (("D1", 1, "ModelRegistry", "AIModelRegistry"),
                  ("D2", 1, "PolicyRegistry", "PolicyRegistry"),
                  ("D3", 1, "DAGAnchor", "DAGAnchor"),
                  ("D3", 16, "DAGAnchor", "DAGAnchor"))


def sample(records):
    by_index = {record.index: record for record in records}
    closures = [lineage(record, by_index) | {record.index}
                for record in records if len(record.parents) > 1]
    selected = {record.index for record in records[:30]}
    if closures:
        selected.update(min(closures, key=lambda closure: (len(closure), sorted(closure))))
    rows = [record for record in records if record.index in selected]
    seen = set()
    for row in rows:
        if not set(row.parents) <= seen:
            raise ValueError(f"Sample is not parents-first at plan index {row.index}")
        seen.add(row.index)
    return rows


def write_json(path, value):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ReceiptLog:
    def __init__(self, w3, wallet, output, label):
        self.w3 = w3
        self.wallet = wallet
        self.output = output
        self.label = label
        self.chain = w3.eth.chain_id
        self.rows = []

    def send(self, function, design, capacity, operation, records=()):
        w3 = self.w3
        sender = self.wallet.address
        estimate = function.estimate_gas({"from": sender})
        quote = w3.eth.gas_price
        limit = (estimate * 120 + 99) // 100
        if w3.eth.get_balance(sender, "pending") < limit * quote:
            raise RuntimeError(f"Insufficient test ETH for {design} {operation}")
        tx = function.build_transaction({
            "from": sender, "chainId": self.chain, "nonce": w3.eth.get_transaction_count(sender, "pending"),
            "gasPrice": quote, "gas": limit,
        })
        payload = Web3.to_bytes(hexstr=tx["data"])
        next_row = {
            "design": design, "batch_capacity": capacity, "operation": operation,
            "indices": ";".join(str(record.index) for record in records),
            "calldata_bytes": len(payload), "calldata_zero_bytes": payload.count(0),
            "calldata_sha256": hashlib.sha256(payload).hexdigest(),
            "tx_hash": "", "contract": tx.get("to") or "", "gas_used": None, "block": None,
            "status": "prepared",
        }
        signed = self.wallet.sign_transaction(tx)
        next_row["tx_hash"] = Web3.to_hex(signed.hash)
        self.rows.append(next_row)
        self.flush()
        w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(signed.hash, timeout=120)
        next_row.update(gas_used=receipt.gasUsed, block=receipt.blockNumber,
                        status="confirmed" if receipt.status == 1 else "reverted")
        if receipt.contractAddress:
            next_row["contract"] = receipt.contractAddress
        self.flush()
        if receipt.status != 1:
            raise RuntimeError(f"Transaction reverted: {next_row['tx_hash']}")
        return receipt

    def flush(self):
        write_json(self.output / f"{self.label}_receipts.json", self.rows)


def replay_sample(w3, wallet, attester_key, opa_url, records, output, label):
    journal = ReceiptLog(w3, wallet, output, label)
    publishers = {record.publisher: wallet.address for record in records}
    datasets = sorted({record.dataset for record in records})
    by_index = {record.index: record for record in records}
    for design, capacity, source, name in CONFIGURATIONS:
        artifact = json.loads((ROOT / "out" / f"{source}.sol" / f"{name}.json").read_text())
        factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
        args = (attester_key.address,) if design == "D3" else ()
        deployed = journal.send(factory.constructor(*args), design, capacity, "deploy")
        contract = w3.eth.contract(address=deployed.contractAddress, abi=factory.abi)
        if design == "D2":
            journal.send(contract.functions.configure(datasets, [wallet.address], True),
                         design, capacity, "configure")
        if design == "D3":
            attester = Attester(attester_key, opa_url, datasets, publishers.values())
            proofs = {}
            for start in range(0, len(records), capacity):
                batch = records[start:start + capacity]
                _, batch_id, tree, signature = attester.anchor(
                    batch, publishers, contract,
                    lambda call: journal.send(call, design, capacity, "register", batch),
                    journal.chain, wallet.address, lambda *_: None,
                )
                proofs.update({record.index: (batch_id, tree.proof(i), signature)
                               for i, record in enumerate(batch)})
            valid = all(anchor_call(contract, row, by_index, proofs, publishers).call() for row in records)
        else:
            ids = {}
            for local_id, record in enumerate(records):
                journal.send(contract.functions.registerProvenance(*record.arguments(ids)),
                             design, capacity, "register", (record,))
                ids[record.index] = local_id
            valid = all(verify_storage(w3, contract, record, by_index, ids, publishers) for record in records)
        if not valid:
            raise RuntimeError(f"Lineage verification failed on {label} for {design}/{capacity}")
        print(f"{label}: {design}/{capacity} verified {len(records)} models", flush=True)
    write_csv(output / f"{label}_gas.csv", journal.rows)
    return journal.rows


def compare(local, remote):
    def key(row):
        return tuple(row[field] for field in ("design", "batch_capacity", "operation", "indices"))

    by_key = {key(row): row for row in remote}
    if len(by_key) != len(remote) or len(local) != len(remote) or set(by_key) != {key(row) for row in local}:
        raise ValueError("Transaction sequences cannot be compared")
    results = []
    for row in local:
        other = by_key[key(row)]
        if row["status"] != "confirmed" or other["status"] != "confirmed":
            raise ValueError("Only confirmed receipts can be compared")
        results.append({
            **{field: row[field] for field in ("design", "batch_capacity", "operation", "indices")},
            "anvil_gas": row["gas_used"], "sepolia_gas": other["gas_used"],
            "sepolia_minus_anvil": other["gas_used"] - row["gas_used"],
            "same_calldata": row["calldata_sha256"] == other["calldata_sha256"],
            "anvil_calldata_zero_bytes": row["calldata_zero_bytes"],
            "sepolia_calldata_zero_bytes": other["calldata_zero_bytes"],
            "anvil_tx": row["tx_hash"], "sepolia_tx": other["tx_hash"],
        })
    return results


def sepolia_wallet(args):
    url = os.environ.get("SEPOLIA_RPC_URL") or os.environ.get("ALCHEMY_SEPOLIA_URL")
    if not url:
        raise ValueError("Set SEPOLIA_RPC_URL or ALCHEMY_SEPOLIA_URL")
    remote = provider(url)
    if remote.eth.chain_id != SEPOLIA:
        raise ValueError("RPC must be Sepolia (chain 11155111)")
    if not sys.stdin.isatty():
        raise ValueError("Run interactively to unlock the encrypted keystore")
    keystore = json.loads(args.keystore.expanduser().read_text())
    wallet = Account.from_key(Account.decrypt(keystore, getpass("Sepolia keystore password: ")))
    return remote, wallet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New evidence directory")
    parser.add_argument("--opa", default="opa")
    parser.add_argument("--anvil-hardfork", default="cancun")
    parser.add_argument("--broadcast", action="store_true", help="Send the sample transactions on Sepolia")
    parser.add_argument("--keystore", type=Path, help="Encrypted deployment keystore for --broadcast")
    args = parser.parse_args()
    if args.broadcast and not args.keystore:
        parser.error("--broadcast requires --keystore")
    anvil, forge, opa = map(executable, ("anvil", "forge", args.opa))
    subprocess.run([forge, "build", "--offline"], cwd=ROOT, check=True)
    path = ROOT / "data/registration_plan.csv"
    records = sample(read_records(path))

    if args.broadcast:
        try:
            remote, wallet = sepolia_wallet(args)
        except Exception as error:
            if isinstance(error, ValueError) and str(error).startswith(("Set SEPOLIA", "RPC must", "Run interactively")):
                parser.error(str(error))
            parser.error(f"Unable to connect to Sepolia or unlock the keystore ({type(error).__name__})")
        attester_key = Account.create()
    else:
        remote = None
        wallet = account_for("chain-check-publisher")
        attester_key = account_for("chain-check-attester")

    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "started_utc": utc_now(), "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                                           cwd=ROOT, text=True).strip(),
        "sample_indices": [row.index for row in records], "input": str(path.relative_to(ROOT)),
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "anvil_hardfork": args.anvil_hardfork, "anvil_chain_id": 31337, "sepolia_chain_id": None,
        "publisher": wallet.address, "attester": attester_key.address,
        "configurations": [f"{design}/{capacity}" for design, capacity, _, _ in CONFIGURATIONS],
        "anvil_version": subprocess.check_output([anvil, "--version"], text=True).splitlines()[0],
        "forge_version": subprocess.check_output([forge, "--version"], text=True).splitlines()[0],
        "opa_version": subprocess.check_output([opa, "version"], text=True).splitlines()[0],
    }
    write_json(args.out / "manifest.json", manifest)
    with server(lambda port: [opa, "run", "--server", "--log-level", "error", "--addr",
                              f"127.0.0.1:{port}", str(ROOT / "policy/provenance.rego")], opa_ready) as opa_url:
        with server(lambda port: [anvil, "--host", "127.0.0.1", "--port", str(port), "--chain-id", "31337",
                                  "--hardfork", args.anvil_hardfork, "--silent"],
                    lambda url: provider(url).is_connected()) as anvil_url:
            local = provider(anvil_url)
            rpc(local, "anvil_setBalance", [wallet.address, hex(10**20)])
            local_rows = replay_sample(local, wallet, attester_key, opa_url, records, args.out, "anvil")
        if remote is not None:
            try:
                manifest["sepolia_chain_id"] = SEPOLIA
                manifest["sepolia_start_block"] = remote.eth.block_number
                write_json(args.out / "manifest.json", manifest)
                remote_rows = replay_sample(remote, wallet, attester_key, opa_url, records, args.out, "sepolia")
            except Exception as error:
                sys.exit(f"Sepolia run stopped ({type(error).__name__}); inspect sepolia_receipts.json before retrying")
            write_json(args.out / "chain_check.json", {"transactions": compare(local_rows, remote_rows)})
    manifest["finished_utc"] = utc_now()
    write_json(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
