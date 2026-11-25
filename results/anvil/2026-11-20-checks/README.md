# Full-workload integrity and admission checks

This directory contains the completed D1, D2, D3 k=1 and D3 k=16 result
rows from the local checks run. The process ended before writing its
final manifest. The final configuration has a separate
[run manifest](../2026-11-20-checks-d3-128/manifest.json) and raw CSVs.
Both runs checked the same committed registration plan.

To reproduce any configuration independently, run
`python scripts/replay.py --mode checks --configuration D1 --out results/anvil/my-d1-checks`.
The remaining configuration names are `D2`, `D3-1`, `D3-16`, and `D3-128`.
