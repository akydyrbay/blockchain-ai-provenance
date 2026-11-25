#!/usr/bin/env python3
"""Generate paper tables from the completed local validation receipts."""
import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

CONFIGURATIONS = (("D1", "1"), ("D2", "1"), ("D3", "1"), ("D3", "16"), ("D3", "128"))


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def expected_ids(plan):
    seen = set()
    eligible = set()
    sequence = []
    for row in read_rows(plan):
        index = int(row["plan_index"])
        parents = {int(value) for value in row["parent_indices"].split(";") if value}
        if index in seen or not parents <= seen:
            raise ValueError(f"Invalid parent order at plan index {index}")
        if parents and seen - parents:
            eligible.add(index)
        seen.add(index)
        sequence.append(index)
    if not eligible or not sequence:
        raise ValueError("The plan must include an applicable parent substitution")
    candidates = set(random.Random(42).sample(sequence, min(100, len(sequence))))
    return (
        dict(clean=seen, altered_weights=seen, altered_dataset=seen, different_parent=eligible),
        dict.fromkeys(("clean_candidate", "unknown_parent", "unlisted_dataset", "unauthorized_publisher"),
                      candidates),
    )


def collect(runs, filename, outcome, expected):
    groups = defaultdict(dict)
    for run in runs:
        for row in read_rows(run / filename):
            config = row["design"], row["batch_size"]
            scenario = row["scenario"]
            index = int(row["model_index"])
            decision = row[outcome]
            if config not in CONFIGURATIONS or scenario not in expected:
                raise ValueError(f"Unexpected configuration or scenario: {config}, {scenario}")
            group = groups[config, scenario]
            if index in group or decision not in ("True", "False"):
                raise ValueError(f"Invalid or duplicate observation: {config}, {scenario}, {index}")
            group[index] = decision == "True"
    for config in CONFIGURATIONS:
        for scenario, indices in expected.items():
            if groups[config, scenario].keys() != indices:
                raise ValueError(f"Incomplete or unexpected model set for {config}, {scenario}")
    return groups


def write_table(path, groups, scenarios):
    with path.open("w", encoding="utf-8") as stream:
        for design, batch in CONFIGURATIONS:
            label = design if design != "D3" else f"D3 ($k={batch}$)"
            cells = []
            for scenario in scenarios:
                decisions = groups[(design, batch), scenario]
                rejected = len(decisions) - sum(decisions.values())
                cells.append(f"{rejected:,}/{len(decisions):,}")
            print(" & ".join([label, *cells]), r"\\", file=stream)
        print(r"\bottomrule", file=stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="Directories containing disjoint check configurations")
    parser.add_argument("--plan", type=Path, default=Path("data/registration_plan.csv"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    integrity, admission = expected_ids(args.plan)
    audit_groups = collect(args.runs, "integrity_cases.csv", "verified", integrity)
    admission_groups = collect(args.runs, "registration_cases.csv", "accepted", admission)
    args.out.mkdir(parents=True, exist_ok=True)
    write_table(args.out / "integrity_rows.tex", audit_groups, integrity)
    write_table(args.out / "admission_rows.tex", admission_groups, admission)
    total = len(integrity["clean"])
    applicable = len(integrity["different_parent"])
    (args.out / "validation_counts.tex").write_text(
        f"\\newcommand{{\\ParentCaseCount}}{{{applicable:,}}}\n"
        f"\\newcommand{{\\AuditModelCount}}{{{total:,}}}\n"
        f"\\newcommand{{\\ParentApplicability}}{{{100 * applicable / total:.1f}\\%}}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
