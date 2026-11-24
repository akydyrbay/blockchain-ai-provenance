# Independent D3 audit

The replay ran locally on Anvil chain 31337. A second Anvil process loaded
the replay's state snapshot after the original process stopped. A
separate `verify_anchor.py` process verified merge index 2169 and its
two ancestors using the included capacity-16 proof bundle and the
committed registration plan. Replacing the merge attestation's
signature component `r` with zero made the verifier exit with status 1.

The state snapshot can be regenerated locally using the
[deployment runbook](../../../docs/deployments.md). This bundle records
local evidence.
