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

## Completed public replay

The 32-model replay confirmed all 103 Sepolia transactions on chain
`11155111` across blocks `12204550–12204667`. The paired run
started at `2026-11-24T19:14:07.948505+00:00` and finished at `2026-11-24T19:39:02.286165+00:00`.
The source revision was `f6e1dc54f961730a70c974304867920c4bd537d6`.
The independent capacity-16 D3 audit verified merge model `2169` and
its two ancestors against the public anchor.

| Configuration | Verified source | Deployment transaction | Block |
| --- | --- | --- | ---: |
| D1 | [`0x60A43634945Bbb4BfcE1a8507c2a0bed86D6bbea`](https://sepolia.etherscan.io/address/0x60A43634945Bbb4BfcE1a8507c2a0bed86D6bbea#code) | [`0x20931362…`](https://sepolia.etherscan.io/tx/0x209313622d546523290e76e392f00b4f48fa89407f835e88ff0935c111d57ef1) | 12204550 |
| D2 | [`0xDf1d44582d6d0D3C04C39413800bbF5E2F9D39aB`](https://sepolia.etherscan.io/address/0xDf1d44582d6d0D3C04C39413800bbF5E2F9D39aB#code) | [`0x93a91883…`](https://sepolia.etherscan.io/tx/0x93a91883b22f33e6c9f398b0df186c40fb15c59767b8ecc9728d6495cb15f2d5) | 12204590 |
| D3, capacity 1 | [`0xa1b2965982494825945Ac7C101DCe0f1dCAd0B80`](https://sepolia.etherscan.io/address/0xa1b2965982494825945Ac7C101DCe0f1dCAd0B80#code) | [`0xb4b03f4a…`](https://sepolia.etherscan.io/tx/0xb4b03f4af0ce66af32b9f49ed0a0f6ada9408d686fd6577737dedeec55bd8c97) | 12204625 |
| D3, capacity 16 | [`0x766553d08eF196e5FEA0e64E45880110C047dd17`](https://sepolia.etherscan.io/address/0x766553d08eF196e5FEA0e64E45880110C047dd17#code) | [`0x6c61b377…`](https://sepolia.etherscan.io/tx/0x6c61b3777cbc840b78de161f7903d42cfb831a99f917d581f26670f40ae451e3) | 12204665 |

Etherscan listed published source for all four addresses with Solidity
0.8.24. The [receipt journal](../results/sepolia/sepolia_receipts.json),
[manifest](../results/sepolia/manifest.json) and
[paired comparison](../results/sepolia/chain_check.json) preserve the
full transaction and run details. Every paired transaction used more
gas on Sepolia. The Anvil sample executed under Cancun and the Sepolia
sample under Glamsterdam, so these are cross-fork observations.

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


## Independently audit a D3 merge

Each replay exports one proof bundle per D3 capacity. It records parent
indices, the committed hashes, publisher addresses, batch IDs, Merkle
siblings and attestation signatures for the selected records. The
independent verifier checks those commitments against the registration
plan, then validates the target and every ancestor on-chain. Supply the
expected chain ID and anchor address from the deployment evidence.
This checks the committed claims and the signatures of the attester
configured in the trusted contract.

```bash
python scripts/verify_anchor.py results/sepolia/sepolia_d3_k16_proofs.json \
  --chain-id 11155111 --anchor "$D3_ADDRESS" --model-index 2169
```

For a local replay, use `chain_check.py --save-anvil-state --out <new-directory>`.
After it finishes, run `anvil --chain-id 31337 --hardfork cancun --load-state <new-directory>/anvil_state.json`
in a separate terminal. Pass the local bundle, the anchor address from
the corresponding Anvil receipt, and `--chain-id 31337 --rpc-url http://127.0.0.1:8545`
to the verifier. The
[local audit evidence](../results/validation/d3-audit-2026-11-24/README.md)
records a successful merge audit and rejection of an altered attestation.
