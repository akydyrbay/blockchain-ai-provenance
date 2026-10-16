#!/usr/bin/env python3
"""Independently compare the raw bytes of three files against on-chain hashes."""
import argparse
import json
import os
import sys
from pathlib import Path

from web3 import Web3
from hash_file import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-id', type=int, required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--training-script', type=Path, default=ROOT / 'scripts/train_demo.py')
    parser.add_argument('--rpc-url', default=os.environ.get('SEPOLIA_RPC_URL'))
    parser.add_argument('--contract', default=os.environ.get('REGISTRY_ADDRESS'))
    parser.add_argument('--chain-id', type=int, default=11155111, help='11155111 Sepolia, 31337 local Anvil')
    args = parser.parse_args()

    if args.model_id < 1 or args.version < 1:
        parser.error('model-id and version must be positive integers')
    if not args.rpc_url or not args.contract:
        parser.error('set SEPOLIA_RPC_URL and REGISTRY_ADDRESS or supply --rpc-url and --contract')

    w3 = Web3(Web3.HTTPProvider(args.rpc_url, request_kwargs={'timeout': 30}))
    if not w3.is_connected():
        raise RuntimeError('RPC unreachable')
    if w3.eth.chain_id != args.chain_id:
        raise RuntimeError(f'Wrong chain: expected {args.chain_id}, got {w3.eth.chain_id}')

    compiled_path = ROOT / 'out' / 'ModelRegistry.sol' / 'ModelRegistry.json'
    abi = json.loads(compiled_path.read_text(encoding='utf-8'))['abi']
    contract = w3.eth.contract(address=Web3.to_checksum_address(args.contract), abi=abi)
    name, owner, pending_owner, latest = contract.functions.getModel(args.model_id).call()
    record = contract.functions.getVersion(args.model_id, args.version).call()
    expected = {'data': bytes(record[0]), 'artifact': bytes(record[1]), 'metadata': bytes(record[2])}
    files = {'data': args.data, 'artifact': args.artifact, 'metadata': args.metadata}
    actual = {kind: sha256_bytes(file) for kind, file in files.items()}

    print(f'Chain {w3.eth.chain_id} | registry {contract.address} | model {args.model_id} ({name})')
    print(f'Current owner {owner} | latest version {latest} | checked version {args.version}')
    print(f'Recorded publisher {record[4]} | timestamp {record[3]}')
    ok = True
    for kind in ('data', 'artifact', 'metadata'):
        matches = actual[kind] == expected[kind]
        print(f'{kind.upper():8s} {"PASS" if matches else "FAIL"}  '
              f'local=0x{actual[kind].hex()}  chain=0x{expected[kind].hex()}')
        ok &= matches

    try:
        metadata = json.loads(args.metadata.read_text(encoding='utf-8'))
        checks = {
            'metadata version': metadata['version'] == args.version,
            'metadata parent_version': metadata['parent_version'] == args.version - 1,
            'metadata dataset hash': metadata['training_data_sha256'].lower() == ('0x' + actual['data'].hex()),
            'metadata artifact hash': metadata['artifact_sha256'].lower() == ('0x' + actual['artifact'].hex()),
            'metadata model name': metadata['name'] == name,
            'metadata training code': metadata['training_code_sha256'].lower() ==
                                      ('0x' + sha256_bytes(args.training_script).hex()),
        }
        for label, matches in checks.items():
            print(f'{label}: {"PASS" if matches else "FAIL"}')
            ok &= matches
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(f'Metadata content invalid: {exc}')
        ok = False

    print('VERIFIED' if ok else 'NOT VERIFIED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
