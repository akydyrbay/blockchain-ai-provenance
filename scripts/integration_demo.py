#!/usr/bin/env python3
"""Run the preserved Iris files through the local D1 and D2 version verifier."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from hash_file import sha256_bytes
from replay import ROOT, anvil_server, deploy, executable, provider, receipt_for, write_csv


def send(w3, function, sender):
    return receipt_for(w3, function.transact({"from": sender}))


def run_demo(url, output):
    w3 = provider(url)
    admin, owner, successor = w3.eth.accounts[:3]
    dataset = ROOT / "data" / "iris_train.csv"
    versions = [
        (ROOT / "models" / f"v{number}" / "model.joblib", ROOT / "models" / f"v{number}" / "metadata.json")
        for number in (1, 2)
    ]
    model_name = json.loads(versions[0][1].read_text())["name"]
    rows = []
    for design, name in (("D1", "AIModelRegistry"), ("D2", "PolicyRegistry")):
        registry, _ = deploy(w3, admin, name)
        if design == "D2":
            send(w3, registry.functions.configure([sha256_bytes(dataset)], [owner, successor], True), admin)

        def register(number, publisher):
            artifact, metadata = versions[number - 1]
            return send(w3, registry.functions.registerVersion(
                0, sha256_bytes(artifact), sha256_bytes(dataset),
                f"iris:v{number}", [sha256_bytes(metadata)],
            ), publisher)

        def verify(scenario, number, expected, data=None, artifact=None, metadata=None,
                   chain_id=31337, model_id=0, diagnostic=None):
            original_artifact, original_metadata = versions[number - 1]
            command = [
                sys.executable, str(ROOT / "scripts" / "verify.py"),
                "--rpc-url", url, "--chain-id", str(chain_id), "--contract", registry.address,
                "--model-id", str(model_id), "--version", str(number), "--data", str(data or dataset),
                "--artifact", str(artifact or original_artifact), "--metadata", str(metadata or original_metadata),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            log = f"{design}-{scenario}.log"
            (output / log).write_text(result.stdout + result.stderr)
            rows.append({"design": design, "scenario": scenario, "expected_exit": expected,
                         "actual_exit": result.returncode, "log": log})
            marker = "VERIFIED" if expected == 0 else "NOT VERIFIED"
            if result.returncode != expected or result.stdout.splitlines()[-1:] != [marker]:
                raise AssertionError(f"{design} {scenario}: see {log}")
            if diagnostic and diagnostic not in result.stdout:
                raise AssertionError(f"{design} {scenario}: missing diagnostic in {log}")

        send(w3, registry.functions.registerModel(model_name, "iris:models"), owner)
        register(1, owner)
        verify("v1", 1, 0)
        send(w3, registry.functions.transferModelOwnership(0, successor), owner)
        register(2, successor)
        verify("v2", 2, 0)
        verify("historical-v1", 1, 0)
        verify("wrong-chain", 1, 1, chain_id=11155111, diagnostic="Wrong chain")
        verify("missing-model", 1, 1, model_id=1, diagnostic="Model 1 does not exist")
        for scenario, source, argument in (
            ("changed-data", dataset, "data"),
            ("changed-model", versions[1][0], "artifact"),
            ("changed-metadata", versions[1][1], "metadata"),
        ):
            with TemporaryDirectory() as temporary:
                changed = Path(temporary) / source.name
                changed.write_bytes(source.read_bytes() + b" ")
                verify(scenario, 2, 1, **{argument: changed})
    write_csv(output / "scenarios.csv", rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New directory for scenario logs")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    subprocess.run([executable("forge"), "build", "--offline"], cwd=ROOT, check=True)
    with anvil_server(executable("anvil")) as url:
        run_demo(url, args.out)


if __name__ == "__main__":
    main()
