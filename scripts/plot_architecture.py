#!/usr/bin/env python3
"""Draw the D1/D2/D3 architecture figure used in the paper.

The figure shows where each design evaluates policy, what it keeps on-chain,
and which checks the timed auditor path performs. It uses no measurement data.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Neutral palette that prints well in greyscale.
INK = "#1f2933"
MUTED = "#52606d"
OFF = "#f5f7fa"      # off-chain region
ON = "#e8eef7"       # on-chain region
BOX = "#ffffff"
ACCENT = "#2f6fb2"   # D3 off-chain components
EDGE = "#7b8794"


def box(ax, x, y, w, h, title, body="", face=BOX, edge=INK, title_color=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012",
                                linewidth=0.9, edgecolor=edge, facecolor=face))
    if body:
        ax.text(x + w / 2, y + h - 0.022, title, ha="center", va="top",
                fontsize=7.6, fontweight="bold", color=title_color)
        ax.text(x + w / 2, y + h - 0.052, body, ha="center", va="top",
                fontsize=6.4, color=MUTED, linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=7.6, fontweight="bold", color=title_color)


def arrow(ax, start, end, label="", dashed=False, label_offset=(0.0, 0.012), rad=0.0):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=8,
                                 linewidth=0.9, color=INK,
                                 linestyle=(0, (3, 2)) if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=1.5, shrinkB=1.5))
    if label:
        mx = (start[0] + end[0]) / 2 + label_offset[0]
        my = (start[1] + end[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=6.0, color=MUTED,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))


def draw(out: Path) -> None:
    fig = plt.figure(figsize=(7.2, 4.6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Column regions: input | admission (off-chain) | chain | audit (off-chain).
    cols = {"input": (0.01, 0.17), "admit": (0.20, 0.25), "chain": (0.47, 0.25), "audit": (0.74, 0.25)}
    for key, (x, w) in cols.items():
        face = ON if key == "chain" else OFF
        ax.add_patch(Rectangle((x, 0.03), w, 0.86, facecolor=face, edgecolor="none", zorder=0))
    headers = {"input": "Shared workload", "admit": "Admission (off-chain)",
               "chain": "EVM contract (on-chain)", "audit": "Audit (off-chain)"}
    for key, (x, w) in cols.items():
        ax.text(x + w / 2, 0.915, headers[key], ha="center", va="bottom",
                fontsize=8, fontweight="bold", color=INK)

    # Row labels and separators.
    rows = {"D1": 0.66, "D2": 0.38, "D3": 0.07}
    row_h = {"D1": 0.21, "D2": 0.21, "D3": 0.25}
    names = {"D1": "D1  Direct storage", "D2": "D2  Solidity policy", "D3": "D3  Attested Merkle batches"}
    for key, y in rows.items():
        ax.text(0.205, y + row_h[key] + 0.012, names[key], ha="left", va="bottom",
                fontsize=7.4, fontweight="bold", color=ACCENT if key == "D3" else INK)
    for y in (0.625, 0.345):
        ax.plot([0.19, 0.99], [y, y], color=EDGE, linewidth=0.6, linestyle=(0, (1, 2)))

    # Shared input.
    box(ax, 0.02, 0.33, 0.15, 0.40, "Registration plan",
        "TinyLlama Hub snapshot\nor synthetic workload\n\nparents-first records:\nweight, dataset and\nmetadata commitments,\nparent links,\npublisher, licence class")

    # D1 row.
    y = rows["D1"]
    box(ax, 0.215, y + 0.045, 0.22, 0.12, "Publisher account",
        "signs registration\ntransaction")
    box(ax, 0.485, y, 0.22, 0.21, "AIModelRegistry",
        "structural checks:\nparents exist, distinct,\nearlier; nonzero hashes\n\nstores record, version\nand parent IDs")
    box(ax, 0.755, y, 0.22, 0.21, "Storage verifier",
        "getLineage(target)\n+ read every ancestor's\nparents, model, version\n\ncompare each field with\nexpected input")
    arrow(ax, (0.435, y + 0.105), (0.485, y + 0.105), "tx")
    arrow(ax, (0.755, y + 0.105), (0.705, y + 0.105), "reads", label_offset=(0, 0.012))

    # D2 row.
    y = rows["D2"]
    box(ax, 0.215, y + 0.045, 0.22, 0.12, "Publisher account",
        "signs registration\ntransaction")
    box(ax, 0.485, y, 0.22, 0.21, "PolicyRegistry",
        "D1 checks + P1-P5 in\nSolidity; allowlist and\npublisher roles on-chain\n\nstores record, version,\nparent IDs, policy state")
    box(ax, 0.755, y, 0.22, 0.21, "Storage verifier",
        "same procedure as D1:\nevery ancestor checked\nagainst contract storage")
    arrow(ax, (0.435, y + 0.105), (0.485, y + 0.105), "tx")
    arrow(ax, (0.755, y + 0.105), (0.705, y + 0.105), "reads", label_offset=(0, 0.012))

    # D3 row.
    y = rows["D3"]
    box(ax, 0.215, y, 0.22, 0.25, "Attester",
        "parent/weight index\n\nOPA (Rego) decides\nP1-P5 per record\n\nbuilds Merkle batch of\npublisher-bound leaves;\nsigns EIP-712 root",
        edge=ACCENT, title_color=ACCENT)
    box(ax, 0.485, y + 0.055, 0.22, 0.17, "DAGAnchor",
        "checks attester signature\n\nstores batch root, size,\nsubmitter, timestamp")
    box(ax, 0.755, y + 0.125, 0.22, 0.125, "Target check (timed)",
        "recompute node hashes\nlocally (Eq. 1); one call:\ntarget inclusion + signature",
        edge=ACCENT, title_color=ACCENT)
    box(ax, 0.755, y, 0.22, 0.105, "Records and proofs",
        "kept off-chain; must stay\navailable to the auditor",
        edge=ACCENT, title_color=ACCENT)
    arrow(ax, (0.435, y + 0.14), (0.485, y + 0.14), "root +\nsignature", label_offset=(0, 0.01))
    arrow(ax, (0.755, y + 0.19), (0.705, y + 0.17), "verifyAnchored", label_offset=(0, 0.004))
    arrow(ax, (0.865, y + 0.105), (0.865, y + 0.125), dashed=True)
    arrow(ax, (0.325, y), (0.755, y + 0.03), "exports records, proofs",
          dashed=True, label_offset=(0.0, -0.045), rad=0.18)

    # Shared input feeds every admission path.
    for key in ("D1", "D2"):
        arrow(ax, (0.17, 0.53), (0.215, rows[key] + 0.105), rad=0.0)
    arrow(ax, (0.17, 0.53), (0.215, rows["D3"] + 0.125))

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "figures" / "architecture.pdf")
    args = parser.parse_args()
    draw(args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
