#!/usr/bin/env python3
"""Plot cold-call verification gas and local wall time for the synthetic workloads."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median, quantiles

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = {"D1": ("#1565a0", "-"), "D2": ("#ab4916", "--"), "D3": ("#376c45", ":")}


def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_results(run, workload):
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["mode"] != "synthetic" or manifest["input_sha256"] != hashlib.sha256(workload.read_bytes()).hexdigest():
        raise ValueError("Saved measurements do not match the synthetic workload")
    groups = {"chain": {}, "fanin": {}}
    for row in rows(workload):
        parents = int(row["n_parents"])
        if row["workload"] == "chain":
            groups["chain"][int(row["depth"])] = row["plan_index"]
        elif parents:
            groups["fanin"][parents] = row["plan_index"]
    gas = {}
    timings = defaultdict(dict)
    for row in rows(run / "verify_gas.csv"):
        if row["batch_size"] == "1":
            key = row["design"], row["model_index"]
            if key in gas:
                raise ValueError(f"Duplicate verification gas for {key}")
            gas[key] = int(row["gas"])
    for row in rows(run / "verify_latency.csv"):
        if row["batch_size"] == "1":
            key = row["design"], row["model_index"]
            trial = int(row["trial"])
            if trial in timings[key]:
                raise ValueError(f"Duplicate verification timing for {key}, trial {trial}")
            timings[key][trial] = float(row["milliseconds"])
    return groups, gas, timings


def plot(groups, gas, timings, output):
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.4), layout="constrained")
    for col, (group, xlabel) in enumerate((("chain", "Chain depth"), ("fanin", "Number of parents"))):
        indices = groups[group]
        xs = sorted(indices)
        for design, (color, style) in DESIGNS.items():
            keys = [(design, indices[x]) for x in xs]
            axes[0, col].plot(xs, [gas[key] for key in keys], color=color, linestyle=style, label=design)
            samples = []
            for key in keys:
                if timings[key].keys() != set(range(1, 31)):
                    raise ValueError(f"Expected 30 verification timings for {key}")
                samples.append(list(timings[key].values()))
            quartiles = [quantiles(values, n=4, method="inclusive") for values in samples]
            axes[1, col].plot(xs, [median(values) for values in samples], color=color, linestyle=style)
            axes[1, col].fill_between(xs, [q[0] for q in quartiles], [q[2] for q in quartiles],
                                     color=color, alpha=0.12)
        for ax in axes[:, col]:
            ax.grid(axis="y", alpha=0.25)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_xlabel(xlabel)
            ax.set_xticks(xs if group == "fanin" else range(0, max(xs) + 1, 5))
    axes[0, 0].set_ylabel("Verification gas")
    axes[1, 0].set_ylabel("Verification time (ms)")
    axes[0, 0].legend(frameon=False)
    fig.savefig(output, metadata={"CreationDate": None})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--workload", type=Path, default=ROOT / "data/synthetic_chain.csv")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plot(*read_results(args.run, args.workload), args.out)


if __name__ == "__main__":
    main()
