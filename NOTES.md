# WE NEED TO PUT THIS INTO README.md files


# HOW TO USE FORGE
forge -vvv > forge_test_outputs/vvv.txt
or 
forge -vvv

forge test --gas-report > test_outputs/gas_report.txt
or 
forge test --gas-report

forge coverage > test_outputs/coverage.txt
or 
forge coverage

# WHY WE DONT USE MYTHRIL
I tried downloading mythril via "apt install" -> didnt work -> broken dependencies
Tried pulling docker image of mythril -> didnt work -> compiler cannot download appropriate version from the official site
We can add this to the paper's limitation section -> Methodology Note on Static Analysis:
We intended to perform both static analysis (Slither) and symbolic execution (Mythril). However, Mythril could not be successfully installed in our environment due to unresolved dependency conflicts and a failure of its Solidity compiler downloader (solc binary) to fetch the required version. We therefore report only Slither's results. This is a limitation: symbolic execution explores deeper path-dependent vulnerabilities (e.g., integer overflows across complex call chains) that static analysis may miss. Our contract's simple, append-only design reduces exposure to these classes of bugs, but future work should incorporate a successful Mythril run.


# HOW TO USE SLITHER and SOLC 
pip install slither-analyzer solc-select
solc-select install 0.8.24
solc-select use 0.8.24

# We can add this script for RUNNING SLITHER
# scripts/run_slither.sh
#!/bin/bash
source .venv/bin/activate
slither . --json slither-report.json
echo "Slither report generated at slither-report.json"

# HOW TO DEPLOY

forge script script/Deploy.s.sol:DeployScript \
  --rpc-url <YOUR_RPC_URL> \
  --account deployer \
  --broadcast


# ACTUAL DEPLOY LOGS 

forge script scripts/Deploy.s.sol:DeployScript   --rpc-url https://eth-sepolia.g.alchemy.com/v2/alch_-k8pfLV1aesiuzZhp8kgW   --account deployer   --broadcast


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


# HOW TO VERIFY WITH ETHERSCAN

forge verify-contract 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71 src/ModelRegistry.sol:AIModelRegistry \
  --chain sepolia \
  --etherscan-api-key <ETHERSCAN_API_KEY> \
  --watch


# VERIFY LOGS
forge verify-contract 0xED1FE6C0EDbd2d0eb424C5Fe8B543FA7F5FF7d71 src/ModelRegistry.sol:AIModelRegistry \
  --chain sepolia \
  --etherscan-api-key <ETHERSCAN_API_KEY> \
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