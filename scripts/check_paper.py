#!/usr/bin/env python3
"""Regenerate the manuscript's data artifacts and check the tracked copies."""
import filecmp
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/anvil"


def run(script, *args):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                   cwd=ROOT, check=True)


def main():
    with TemporaryDirectory(prefix="provenance-paper-") as directory:
        out = Path(directory)
        run("summarize_replay.py", RESULTS / "2026-11-20-full", "--out", out)
        run("summarize_validation.py", RESULTS / "2026-11-20-checks",
            RESULTS / "2026-11-20-checks-d3-128", "--out", out)
        run("plot_synthetic_scaling.py", RESULTS / "2026-11-20-synthetic",
            "--out", out / "synthetic_scaling.pdf")
        run("summarize_sepolia.py", RESULTS.parent / "sepolia", "--out", out)
        mismatches = []
        for name in ("registration_rows.tex", "timing_rows.tex", "integrity_rows.tex",
                     "admission_rows.tex", "validation_counts.tex", "synthetic_scaling.pdf",
                     "sepolia_rows.tex", "sepolia_counts.tex"):
            tracked = ROOT / "paper" / name
            if tracked.is_file() and filecmp.cmp(out / name, tracked, shallow=False):
                print(f"PASS: {name}")
            else:
                mismatches.append(name)
        if mismatches:
            sys.exit("Paper artifacts differ from regenerated output: " + ", ".join(mismatches))


if __name__ == "__main__":
    main()
