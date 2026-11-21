# Sepolia sample comparison

The comparative run uses fresh deployments for D1, D2, D3 with capacity 1,
and D3 with capacity 16. The original Sepolia deployment remains recorded
in [the deployment notes](notes.md).

## Completed local validation

The sample contains the first 30 records plus the additional records in the
smallest ancestor-closed set containing a merge. Ties use the registration
plan indices. This selects 32 records on the current snapshot. The
[Anvil manifest](../results/anvil/2026-11-21-sepolia-sample/manifest.json)
lists the exact indices, input digest, and tool versions. All 103 local
transactions confirmed, and the verifier checked every selected lineage in
each configuration. A second local Anvil node using the Sepolia chain ID
exercised the full receipt-pairing path.
[Paired local validation](../results/anvil/2026-11-21-sepolia-sample/paired_local_validation.json)

The public run still needs the funded test wallet to be unlocked. The local Foundry wallet is stored in an encrypted keystore. The runner
accepts its password interactively. The prior broadcaster’s address had
test ETH at the read-only check. Public deployment addresses and explorer
verification results are pending.

## Run the paired replay

Export a valid `SEPOLIA_RPC_URL` or `ALCHEMY_SEPOLIA_URL` in your shell.
With Foundry, OPA 1.4.2, and the project virtual environment available, run
the following from an interactive terminal in the repository root.

```bash
python scripts/chain_check.py --broadcast \
  --keystore "$HOME/.foundry/keystores/deployer" \
  --out results/sepolia
```

Use a new output directory if that path already exists. The script reads
the same wallet address and workload on both chains, uses a separate
attester account, and refuses a remote chain ID other than 11155111. It
runs the Anvil side first. The receipt journal records the signed
transaction hash before sending, then updates its confirmation status.
If a run stops, look up any pending hash before starting a fresh run.

On completion, `chain_check.json` pairs gas used by design, batch capacity,
operation, and plan indices, including deployment and allowlist setup.
The manifest and receipt logs preserve the source revision, addresses,
transaction hashes, block numbers, and completion time.

The sample uses one funded publisher address on both chains so the
measurement has matching publisher identities. The full Anvil workload
uses a publisher address per Hub namespace. D3 signatures commit to the
chain ID and anchor address, which can change the number of zero bytes in
registration calldata. The comparison records calldata equality and zero-byte
counts alongside each gas delta. The local baseline uses Cancun execution
rules, and Sepolia activated Glamsterdam in October 2026. Account for fork
rules and calldata differences when interpreting public outcomes.
[Ethereum Foundation activation schedule](https://blog.ethereum.org/en/2026/09/17/glamsterdam-testnet-announcement)

## Verify the public contract sources

Once the run confirms, read each deployment address from
`sepolia_receipts.json` and export a valid `ETHERSCAN_API_KEY` in the shell.
Set `D1_ADDRESS`, `D2_ADDRESS`, and `D3_ADDRESS` from the deployment rows.
Set `ATTESTER_ADDRESS` from `manifest.json`. Run the D3 command for both
batch configurations.

```bash
forge verify-contract --chain sepolia --watch "$D1_ADDRESS" src/ModelRegistry.sol:AIModelRegistry
forge verify-contract --chain sepolia --watch "$D2_ADDRESS" src/PolicyRegistry.sol:PolicyRegistry
forge verify-contract --chain sepolia --watch \
  --constructor-args "$(cast abi-encode 'constructor(address)' "$ATTESTER_ADDRESS")" \
  "$D3_ADDRESS" src/DAGAnchor.sol:DAGAnchor
```
