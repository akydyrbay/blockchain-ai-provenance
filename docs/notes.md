# Validation and deployment notes


## Contract tests

Run from the repository root after installing Foundry. Tests are configured in `forge_test/` and the Solidity test dependency is pinned:

```bash
git submodule update --init --recursive
mkdir -p forge_test_outputs
```

The following commands regenerate the retained output files:

```bash
set -o pipefail
forge test -vvv 2>&1 | tee forge_test_outputs/function_check.txt
forge test --gas-report 2>&1 | tee forge_test_outputs/gas_report.txt
forge coverage 2>&1 | tee forge_test_outputs/coverage.txt

```

## Static analysis

Use the same project environment as the training and verification scripts:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
solc-select install 0.8.24
solc-select use 0.8.24
```

With Foundry available on PATH, run from the repository root:

```bash
mkdir -p results/slither
SLITHER_RUN_DIR=$(mktemp -d "$PWD/results/slither/run-XXXXXXXX")
set -o pipefail
slither . --json "$SLITHER_RUN_DIR/report.json" \
  2>&1 | tee "$SLITHER_RUN_DIR/slither.log"
```

Each run gets a new directory so Slither can write its JSON report without replacing earlier evidence. Retain tool versions, compiler settings, and the analyzed revision alongside the output. The [saved report](../results/slither/report.json) records success and no detector entries; it is not a complete security audit.

Mythril was attempted but could not be installed successfully in the teammate's environment. No symbolic-execution results are available. Report only the analyses actually completed.

## Deployment

Set `SEPOLIA_RPC_URL` to your own endpoint in the shell and import a test-wallet keystore named `deployer`. The original RPC credential was exposed in Git history: the account owner must revoke/rotate it. Redacting the copied command below does not revoke that credential.

```bash
forge script scripts/Deploy.s.sol:DeployScript \
  --rpc-url "$SEPOLIA_RPC_URL" \
  --account deployer \
  --broadcast
```

## Recorded deployment output

The historical deployment output below is retained as evidence; the RPC URL in the command has been replaced with an environment variable.

```text
forge script scripts/Deploy.s.sol:DeployScript   --rpc-url "$SEPOLIA_RPC_URL"   --account deployer   --broadcast


Enter keystore password:
[⠊] Compiling...
No files changed, compilation skipped
Script ran successfully.

== Logs ==
  AIModelRegistry deployed to: 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71

## Setting up 1 EVM.

==========================

Chain 11155111

Estimated max fee per gas: 0.525000025 gwei
Estimated base fee per gas: 0.000000019 gwei
Estimated max priority fee per gas: 0.524999987 gwei

Estimated total gas used for script: 9656532

Estimated amount required: 0.0050696795414133 ETH

==========================
##### sepolia✅  [Success] Hash: 0x83297ce46d1e6f3e8edd9df82b5a6f34861accfb379312eb2180dce4982d1d36Contract: AIModelRegistryContract Address: 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71Block: 12089282Paid: 0.003899753594568612 ETH (7428102 gas * 0.525000006 gwei)
✅ Sequence #1 on sepolia | Total Paid: 0.003899753594568612 ETH (7428102 gas * avg 0.525000006 gwei)

==========================

ONCHAIN EXECUTION COMPLETE & SUCCESSFUL.

Transactions saved to: /home/rajiv/Documents/Important/NU/My Courses/4 Course/1 Semester/CSCI 435 - Blockchain/project/blockchain-ai-provenance/broadcast/Deploy.s.sol/11155111/run-latest.json

Sensitive values saved to: /home/rajiv/Documents/Important/NU/My Courses/4 Course/1 Semester/CSCI 435 - Blockchain/project/blockchain-ai-provenance/cache/Deploy.s.sol/11155111/run-latest.json
```

## Explorer verification

Use your own Etherscan API key through `ETHERSCAN_API_KEY`.

```bash
forge verify-contract 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71 src/ModelRegistry.sol:AIModelRegistry \
  --chain sepolia \
  --etherscan-api-key "$ETHERSCAN_API_KEY" \
  --watch
```

## Recorded verification output

```text
forge verify-contract 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71 src/ModelRegistry.sol:AIModelRegistry \
  --chain sepolia \
  --etherscan-api-key "$ETHERSCAN_API_KEY" \
  --watch
Start verifying contract `0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71` deployed on sepolia

Verifying on etherscan...
Submitting verification for [src/ModelRegistry.sol:AIModelRegistry] 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71.
Submitted contract for verification:
        Response: `OK`
        GUID: `iiaxdfcrjeupp5a5x1gyyikpggacd73d6b5wer8h9zbc844vi7`
        URL: https://sepolia.etherscan.io/address/0xed1fe6c0edbd2d0eb424c5fe8b543fa7f5ff7d71
iiaxdfcrjeupp5a5x1gyyikpggacd73d6b5wer8h9zbc844vi7      https://sepolia.etherscan.io/address/0xed1fe6c0edbd2d0eb424c5fe8b543fa7f5ff7d71

Verifying on sourcify...
Submitting verification for [AIModelRegistry] 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71.
Submitted contract for verification:
        Verification Job ID: `8f95cdae-2d8f-452c-8479-71d683ad7752`
        URL: https://sourcify.dev/server/verify-ui/jobs/8f95cdae-2d8f-452c-8479-71d683ad7752
8f95cdae-2d8f-452c-8479-71d683ad7752    https://sourcify.dev/server/verify-ui/jobs/8f95cdae-2d8f-452c-8479-71d683ad7752

Waiting for etherscan verification result...
Contract verification status:
Response: `NOTOK`
Details: `Pending in queue`
Warning: Verification is still pending...; waiting 5 seconds before trying again (4 tries remaining)
Contract verification status:
Response: `OK`
Details: `Pass - Verified`
Contract successfully verified
```
