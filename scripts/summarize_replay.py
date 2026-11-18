#!/usr/bin/env python3
"""Summarize a completed Anvil run and export its gas-by-design plot."""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from replay import ROOT, read_records, write_csv


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def summarize(path, out):
    manifest = json.loads((path / "manifest.json").read_text())
    transactions = read_rows(path / "gas.csv")
    configs = defaultdict(list)
    for row in transactions:
        configs[row["design"], int(row["batch_size"])].append(row)

    summary = []
    for (design, batch_size), rows in configs.items():
        registrations = [row for row in rows if row["operation"] == "register"]
        models = sum(int(row["models"]) for row in registrations)
        if models != len(manifest["model_indices"]):
            raise ValueError(f"Incomplete registration results for {design} k={batch_size}")
        gas = sum(int(row["gas"]) for row in registrations)
        state = sum(int(row["new_state_bytes"]) for row in registrations)
        summary.append({
            "design": design, "batch_size": batch_size, "models": models,
            "registration_transactions": len(registrations),
            "deployment_gas": sum(int(row["gas"]) for row in rows if row["operation"] == "deploy"),
            "configuration_gas": sum(int(row["gas"]) for row in rows if row["operation"] == "configure"),
            "registration_gas": gas, "mean_gas_per_model": round(gas / models, 2),
            "registration_new_bytes": state, "mean_new_bytes_per_model": round(state / models, 2),
        })
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "registrations.csv", summary)
    with (out / "registration_rows.tex").open("w", encoding="utf-8") as stream:
        for row in summary:
            label = row["design"]
            if label == "D3":
                label += f" ($k={row['batch_size']}$)"
            print(f"{label} & {row['registration_transactions']:,} & "
                  f"{row['mean_gas_per_model']:,.0f} & {row['mean_new_bytes_per_model']:,.1f} "
                  + chr(92) * 2, file=stream)
        print(r"\bottomrule", file=stream)
    timings = {}
    for filename, metric in (("policy_latency.csv", "milliseconds"),
                             ("verify_latency.csv", "milliseconds"),
                             ("audit_throughput.csv", "models_per_second")):
        source = path / filename
        if not source.is_file():
            continue
        groups = defaultdict(list)
        for row in read_rows(source):
            groups[row["design"], row["batch_size"]].append(float(row[metric]))
        compact = []
        for (design, batch_size), values in groups.items():
            lower, _, upper = statistics.quantiles(values, n=4, method="inclusive")
            compact.append({
                "design": design, "batch_size": batch_size, "n": len(values), "metric": metric,
                "median": statistics.median(values), "q1": lower, "q3": upper,
            })
        write_csv(out / filename, compact)
        timings[filename] = {(row["design"], int(row["batch_size"])): row["median"] for row in compact}
    if timings:
        with (out / "timing_rows.tex").open("w", encoding="utf-8") as stream:
            for design, batch_size in configs:
                label = f"D3 ($k={batch_size}$)" if design == "D3" else design
                key = design, batch_size
                cells = []
                for metric in ("policy_latency.csv", "verify_latency.csv", "audit_throughput.csv"):
                    median = timings.get(metric, {}).get(key)
                    cells.append(f"{median:.2f}" if median is not None else "--")
                print(" & ".join([label, *cells]) + " " + chr(92) * 2, file=stream)
            print(r"\bottomrule", file=stream)
    for filename, outcome in (("integrity_cases.csv", "verified"), ("registration_cases.csv", "accepted")):
        source = path / filename
        if source.is_file():
            summarize_cases(source, out / filename, outcome)
    if manifest["mode"] in ("full", "synthetic"):
        scaling_and_fit(manifest, transactions, out)
    return manifest["mode"], summary



def summarize_cases(source, destination, outcome):
    groups = defaultdict(list)
    for row in read_rows(source):
        groups[row["design"], row["batch_size"], row["scenario"]].append(row)
    summary = []
    for (design, batch_size, scenario), rows in groups.items():
        accepted = sum(row[outcome] == "True" for row in rows)
        summary.append({
            "design": design, "batch_size": batch_size, "scenario": scenario, "cases": len(rows),
            "passed": accepted, "rejected": len(rows) - accepted,
            "median_milliseconds": statistics.median(float(row["milliseconds"]) for row in rows)
            if "milliseconds" in rows[0] else "",
        })
    write_csv(destination, summary)


def scaling_and_fit(manifest, transactions, out):
    import hashlib
    import numpy as np

    workload = ROOT / manifest["input"]
    if hashlib.sha256(workload.read_bytes()).hexdigest() != manifest["input_sha256"]:
        raise ValueError("Workload no longer matches the run manifest")
    records = {record.index: record for record in read_records(workload)}
    groups = defaultdict(list)
    for row in transactions:
        if row["operation"] != "register" or row["models"] != "1" or row["batch_size"] != "1":
            continue
        groups[row["design"]].append(row)
    models = {}
    scaling = []
    for design, group in groups.items():
        features, observed = [], []
        for row in group:
            record = records[int(row["model_indices"])]
            features.append([1, (len(record.uri.encode()) + 31) // 32, len(record.parents), int(not record.parents)])
            observed.append(int(row["gas"]))
            scaling.append({
                "design": design, "model_index": record.index, "depth": record.depth, "n_parents": len(record.parents),
                "gas": int(row["gas"]), "new_state_bytes": int(row["new_state_bytes"]),
            })
        matrix, costs = np.asarray(features), np.asarray(observed)
        coeffs, _, rank, _ = np.linalg.lstsq(matrix, costs, rcond=None)
        error = costs - matrix @ coeffs
        variance = np.sum((costs - costs.mean()) ** 2)
        models[design] = {
            "n": len(group), "rank": int(rank),
            "columns": ["intercept", "uri_words", "n_parents", "is_root"],
            "coefficients": coeffs.tolist() if rank == matrix.shape[1] else None,
            "r_squared": float(1 - np.dot(error, error) / variance) if variance and rank == matrix.shape[1] else None,
            "largest_absolute_residual": float(np.abs(error).max()) if rank == matrix.shape[1] else None,
        }
    write_csv(out / "depth_scaling.csv", scaling)
    (out / "gas_model.json").write_text(json.dumps(models, indent=2) + "\n")

def plot_gas(mode, rows, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"D3 (k={row['batch_size']})" if row["design"] == "D3" else row["design"] for row in rows]
    fig, ax = plt.subplots(figsize=(7, 3.8), layout="constrained")
    ax.scatter(labels, [row["mean_gas_per_model"] for row in rows], color="#315779", s=55, zorder=3)
    ax.set_yscale("log")
    ax.set_ylabel("Mean gas units per model")
    ax.grid(axis="y", alpha=0.25)
    ax.set_title(f"Anvil registration cost ({mode} workload)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out / "registration_gas.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Completed replay directory")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    mode, rows = summarize(args.run, args.out)
    plot_gas(mode, rows, args.out)


if __name__ == "__main__":
    main()
