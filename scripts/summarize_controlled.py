#!/usr/bin/env python3
"""Generate the paper inputs for the controlled placement and equal-scope verification runs."""
import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path

from replay import ROOT, write_csv

PLACEMENT = ("C-Sol", "C-OPA")
ANCHOR_SIZES = ("1", "16", "128")
REFERENCE_RUN = ROOT / "results/anvil/2026-11-20-full"


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_manifest(run, mode):
    manifest = json.loads((run / "manifest.json").read_text())
    workload = ROOT / manifest["input"]
    if manifest["mode"] != mode or not manifest.get("finished_utc"):
        raise ValueError(f"{run} is not a completed {mode} run")
    if hashlib.sha256(workload.read_bytes()).hexdigest() != manifest["input_sha256"]:
        raise ValueError(f"{run} no longer matches its workload")
    return manifest


def spread(values):
    if not values:
        raise ValueError("No observations to summarize")
    lower, _, upper = statistics.quantiles(values, n=4, method="inclusive")
    return statistics.median(values), lower, upper


def columns(name, values):
    median, lower, upper = spread(values)
    return {f"{name}_median": median, f"{name}_q1": lower, f"{name}_q3": upper}


def cell(values):
    median, lower, upper = spread(values)
    return f"{median:.2f} [{lower:.2f}, {upper:.2f}]"


def grouped(rows, metric, *keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(float(row[metric]))
    return groups


def registration(rows, design, models):
    deploy = [int(row["gas"]) for row in rows if row["design"] == design and row["operation"] == "deploy"]
    setup = sum(int(row["gas"]) for row in rows if row["design"] == design and row["operation"] == "configure")
    register = [row for row in rows if row["design"] == design and row["operation"] == "register"]
    if len(deploy) != 1 or sum(int(row["models"]) for row in register) != models:
        raise ValueError(f"Incomplete registration rows for {design}")
    gas = sum(int(row["gas"]) for row in register)
    state = sum(int(row["new_state_bytes"]) for row in register)
    return deploy[0], setup, gas / models, state / models, register


def placement(run, out, csv_out):
    manifest = read_manifest(run, "full")
    if manifest["configurations"] != list(PLACEMENT):
        raise ValueError("Expected the C-Sol and C-OPA configurations")
    models = len(manifest["model_indices"])
    transactions = read_rows(run / "gas.csv")
    decision = grouped(read_rows(run / "policy_latency.csv"), "milliseconds", "design")
    verify = grouped(read_rows(run / "verify_latency.csv"), "milliseconds", "design")
    audit = grouped(read_rows(run / "audit_throughput.csv"), "models_per_second", "design")
    probe = grouped(read_rows(run / "verify_gas.csv"), "gas", "design")
    summary, per_model = [], {}
    with (out / "placement_rows.tex").open("w", encoding="utf-8") as stream:
        for design in PLACEMENT:
            deploy, setup, gas, state, register = registration(transactions, design, models)
            per_model[design] = {row["model_indices"]: (int(row["gas"]), int(row["new_state_bytes"]))
                                 for row in register}
            audit_median = statistics.median(audit[design,])
            summary.append({
                "design": design, "models": models, "deployment_gas": deploy, "configuration_gas": setup,
                "mean_gas_per_model": round(gas, 2), "mean_new_bytes_per_model": round(state, 2),
                **columns("decision_ms", decision[design,]), **columns("verify_ms", verify[design,]),
                **columns("audit_models_per_second", audit[design,]),
                "median_probe_gas": statistics.median(probe[design,]),
            })
            print(f"{design} & {deploy:,} & {setup:,} & {gas:,.0f} & {state:,.1f} & "
                  f"{cell(decision[design,])} & {cell(verify[design,])} & {audit_median:.2f} \\\\", file=stream)
        print(r"\bottomrule", file=stream)
    if csv_out:
        write_csv(csv_out / "placement_summary.csv", summary)

    if per_model["C-Sol"].keys() != per_model["C-OPA"].keys():
        raise ValueError("The controlled variants registered different model sets")
    same_state = sum(per_model["C-Sol"][key][1] == per_model["C-OPA"][key][1] for key in per_model["C-Sol"])
    gas_gap = [per_model["C-Sol"][key][0] - per_model["C-OPA"][key][0] for key in per_model["C-Sol"]]

    equivalence = read_rows(run / "policy_equivalence.csv")
    if any(row["c_sol"] != row["c_opa"] or row["c_sol"] != row["expected"] for row in equivalence):
        raise ValueError("The controlled variants disagree on a policy-equivalence case")
    admission = defaultdict(lambda: [0, 0])
    for row in read_rows(run / "registration_cases.csv"):
        counts = admission[row["design"], row["scenario"]]
        counts[0] += row["accepted"] == "False"
        counts[1] += 1
    for scenario in ("clean_candidate", "unknown_parent", "unlisted_dataset", "unauthorized_publisher"):
        if admission["C-Sol", scenario] != admission["C-OPA", scenario]:
            raise ValueError(f"The controlled variants differ on admission scenario {scenario}")
    rejected = sum(admission["C-Sol", scenario][0]
                   for scenario in ("unknown_parent", "unlisted_dataset", "unauthorized_publisher"))
    violations = sum(admission["C-Sol", scenario][1]
                     for scenario in ("unknown_parent", "unlisted_dataset", "unauthorized_publisher"))
    return {
        "PlacementEquivalenceCases": f"{len(equivalence):,}",
        "PlacementSameStateModels": f"{same_state:,}",
        "PlacementModels": f"{models:,}",
        "PlacementGasGapMin": f"{min(gas_gap):,}",
        "PlacementGasGapMax": f"{max(gas_gap):,}",
        "PlacementGasGapMedian": f"{statistics.median(gas_gap):,.0f}",
        "PlacementCleanRejected": f"{admission['C-Sol', 'clean_candidate'][0]:,}/"
                                  f"{admission['C-Sol', 'clean_candidate'][1]:,}",
        "PlacementViolationsRejected": f"{rejected:,}/{violations:,}",
    }


def ancestry(run, batched, out, csv_out):
    manifest = read_manifest(run, "full")
    extra = read_manifest(batched, "full")
    if not manifest.get("full_ancestry") or not extra.get("batched_target"):
        raise ValueError("Expected a full-ancestry run and a batched-target run")
    if extra["model_indices"] != manifest["model_indices"] or extra["configurations"] != [
            f"D3-{size}" for size in ANCHOR_SIZES]:
        raise ValueError("The batched-target run must replay the same workload for the D3 configurations")
    models = len(manifest["model_indices"])

    def timing(directory, name, metric):
        return grouped(read_rows(directory / name), metric, "design", "batch_size")

    sources = {
        "storage": (timing(run, "verify_latency.csv", "milliseconds"),
                    timing(run, "audit_throughput.csv", "models_per_second"), run),
        "target_single": (timing(run, "verify_latency.csv", "milliseconds"),
                          timing(run, "audit_throughput.csv", "models_per_second"), run),
        "ancestry": (timing(run, "ancestry_latency.csv", "milliseconds"),
                     timing(run, "ancestry_throughput.csv", "models_per_second"), run),
        "target": (timing(batched, "target_batch_latency.csv", "milliseconds"),
                   timing(batched, "target_batch_throughput.csv", "models_per_second"), batched),
        "ancestry_repeat": (timing(batched, "ancestry_latency.csv", "milliseconds"),
                            timing(batched, "ancestry_throughput.csv", "models_per_second"), batched),
    }
    scope = defaultdict(list)
    for row in read_rows(run / "scope_gas.csv"):
        scope[row["design"], row["batch_size"], row["procedure"]].append(row)
    repeat = {(row["design"], row["batch_size"], row["procedure"], row["model_index"]): row["gas"]
              for row in read_rows(batched / "scope_gas.csv")}
    for (design, size, procedure), group in list(scope.items()):
        if design == "D3" and any(repeat[design, size, procedure, row["model_index"]] != row["gas"]
                                  for row in group):
            raise ValueError("The two runs measured different on-chain gas for the same D3 calls")
    timed_targets = defaultdict(set)
    for row in read_rows(run / "verify_gas.csv"):
        timed_targets[row["design"], row["batch_size"]].add(row["model_index"])

    rows = [("D1", "1", "storage"), ("D2", "1", "storage")]
    for size in ANCHOR_SIZES:
        rows += [("D3", size, "target"), ("D3", size, "ancestry")]
    reported = rows + [("D3", size, procedure) for size in ANCHOR_SIZES
                       for procedure in ("target_single", "ancestry_repeat")]
    labels = {"storage": "Full ancestry (storage)", "target": "Target only", "ancestry": "Full ancestry (proofs)"}
    summary = []
    with (out / "ancestry_rows.tex").open("w", encoding="utf-8") as stream:
        for design, size, procedure in reported:
            key = design, size
            latency, throughput, source = sources[procedure]
            gas_procedure = {"target_single": "target", "ancestry_repeat": "ancestry"}.get(procedure, procedure)
            calls = scope[design, size, gas_procedure]
            if not calls or {row["model_index"] for row in calls} != timed_targets[key]:
                raise ValueError(f"Scope gas does not cover the timed targets for {design} k={size} {procedure}")
            call_count = statistics.median(int(row["calls"]) for row in calls)
            gas = statistics.median(int(row["gas"]) for row in calls)
            summary.append({
                "design": design, "batch_size": size, "procedure": procedure, "run": source.name,
                "targets": len(calls), "median_calls": call_count, "median_scope_gas": gas,
                **columns("verify_ms", latency[key]), **columns("audit_models_per_second", throughput[key]),
                "audit_models": models,
            })
            if (design, size, procedure) in rows:
                label = design if design != "D3" else f"D3 ($k={size}$)"
                print(f"{label} & {labels[procedure]} & {call_count:,.0f} & {gas:,.0f} & {cell(latency[key])} & "
                      f"{statistics.median(throughput[key]):.2f} \\\\", file=stream)
        print(r"\bottomrule", file=stream)
    if csv_out:
        write_csv(csv_out / "ancestry_summary.csv", summary)

    depth = defaultdict(list)
    for directory, name, procedure in ((run, "verify_latency.csv", None), (run, "ancestry_latency.csv", "ancestry"),
                                       (batched, "target_batch_latency.csv", "target")):
        for row in read_rows(directory / name):
            label = procedure or ("target_single" if row["design"] == "D3" else "storage")
            depth[row["design"], row["batch_size"], label, int(row["depth"])].append(float(row["milliseconds"]))
    if csv_out:
        write_csv(csv_out / "ancestry_by_depth.csv", [
            {"design": key[0], "batch_size": key[1], "procedure": key[2], "depth": key[3],
             "observations": len(values), "median_ms": statistics.median(values)}
            for key, values in sorted(depth.items())
        ])

    integrity = defaultdict(lambda: [0, 0])
    for row in read_rows(run / "ancestry_integrity.csv"):
        counts = integrity[row["scenario"]]
        counts[0] += row["verified"] == "False"
        counts[1] += 1
    altered = [integrity[name] for name in ("altered_weights", "altered_dataset", "different_parent")]

    def transactions(path):
        return [((row["design"], row["batch_size"], row["operation"], row["model_indices"]),
                 (row["gas"], row["new_state_bytes"])) for row in read_rows(path)]

    reference, current = transactions(REFERENCE_RUN / "gas.csv"), transactions(run / "gas.csv")
    if [key for key, _ in reference] != [key for key, _ in current]:
        raise ValueError("The full-ancestry run and the reference run contain different transactions")
    matching = sum(old == new for (_, old), (_, new) in zip(reference, current))
    return {
        "AncestryCleanRejected": f"{integrity['clean'][0]:,}/{integrity['clean'][1]:,}",
        "AncestryAlteredRejected": f"{sum(c[0] for c in altered):,}/{sum(c[1] for c in altered):,}",
        "ReplayMatchingTransactions": f"{matching:,}",
        "ReplayTransactions": f"{len(reference):,}",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--placement", type=Path, required=True, help="Completed full placement_replay.py run")
    parser.add_argument("--ancestry", type=Path, required=True, help="Completed replay.py --full-ancestry run")
    parser.add_argument("--target-batched", type=Path, required=True,
                        help="Completed D3-only replay.py --full-ancestry --batched-target run")
    parser.add_argument("--out", type=Path, required=True, help="Directory for the LaTeX inputs")
    parser.add_argument("--csv-out", type=Path, help="Optional directory for the summary CSV files")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.csv_out:
        args.csv_out.mkdir(parents=True, exist_ok=True)
    counts = placement(args.placement, args.out, args.csv_out) | ancestry(args.ancestry, args.target_batched, args.out,
                                                                    args.csv_out)
    (args.out / "controlled_counts.tex").write_text(
        "".join(f"\\newcommand{{\\{name}}}{{{value}}}\n" for name, value in counts.items()), encoding="utf-8")


if __name__ == "__main__":
    main()
