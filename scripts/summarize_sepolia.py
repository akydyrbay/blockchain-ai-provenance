#!/usr/bin/env python3
"""Generate the paper's Sepolia sample table from paired transaction receipts."""
import argparse
import json
from collections import Counter
from pathlib import Path

from chain_check import CONFIGURATIONS, SEPOLIA, compare


def read_json(run, filename):
    return json.loads((run / filename).read_text(encoding="utf-8"))


def summarize(run):
    manifest = read_json(run, "manifest.json")
    sample = manifest["sample_indices"]
    configs = [(design, capacity) for design, capacity, _, _ in CONFIGURATIONS]
    if (manifest["sepolia_chain_id"] != SEPOLIA or manifest["anvil_chain_id"] != 31337
            or not manifest.get("finished_utc")):
        raise ValueError("Expected a completed Anvil–Sepolia replay")
    if not sample or len(sample) != len(set(sample)):
        raise ValueError("Expected a nonempty sample with distinct plan indices")
    if manifest["configurations"] != [f"{design}/{capacity}" for design, capacity in configs]:
        raise ValueError("Unexpected sample replay configurations")

    rows = compare(read_json(run, "anvil_receipts.json"), read_json(run, "sepolia_receipts.json"))
    if rows != read_json(run, "chain_check.json")["transactions"]:
        raise ValueError("Saved comparison differs from the paired receipts")
    if {(row["design"], row["batch_capacity"]) for row in rows} != set(configs):
        raise ValueError("Paired receipts do not cover the configured sample")

    summary = []
    for design, capacity in configs:
        expected = [";".join(map(str, sample[i:i + capacity]))
                    for i in range(0, len(sample), capacity)]
        config_rows = [row for row in rows if (row["design"], row["batch_capacity"]) == (design, capacity)]
        operations = {"deploy": 1, "register": len(expected)}
        if design == "D2":
            operations["configure"] = 1
        registrations = [row for row in config_rows if row["operation"] == "register"]
        if (Counter(row["operation"] for row in config_rows) != operations
                or [row["indices"] for row in registrations] != expected):
            raise ValueError(f"Missing or unexpected transactions for {design}/{capacity}")
        label = design if design != "D3" else f"D3 ($k={capacity}$)"
        summary.append((label, sum(row["anvil_gas"] for row in registrations) / len(sample),
                        sum(row["sepolia_gas"] for row in registrations) / len(sample)))
    return summary, len(sample), len(rows), sum(row["sepolia_minus_anvil"] > 0 for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, models, pairs, more_on_sepolia = summarize(args.run)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "sepolia_rows.tex").open("w", encoding="utf-8") as stream:
        for label, anvil, sepolia in rows:
            print(f"{label} & {anvil:,.0f} & {sepolia:,.0f}", r"\\", file=stream)
        print(r"\bottomrule", file=stream)
    (args.out / "sepolia_counts.tex").write_text(
        f"\\newcommand{{\\SepoliaModels}}{{{models:,}}}\n"
        f"\\newcommand{{\\SepoliaPairs}}{{{pairs:,}}}\n"
        f"\\newcommand{{\\SepoliaHigherGas}}{{{more_on_sepolia:,}}}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
