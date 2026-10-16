#!/usr/bin/env python3
"""Collect actual Sepolia receipt gasUsed into a reproducible CSV."""
import argparse
import csv
import os
from pathlib import Path
from web3 import Web3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tx', action='append', required=True,
                        help='operation_name:0xtransactionhash (repeat for each transaction)')
    parser.add_argument('--rpc-url', default=os.environ.get('SEPOLIA_RPC_URL'))
    parser.add_argument('--chain-id', type=int, default=11155111)
    parser.add_argument('--output', type=Path, default=Path('results/gas.csv'))
    args = parser.parse_args()
    if not args.rpc_url:
        parser.error('Set SEPOLIA_RPC_URL or --rpc-url')
    w3 = Web3(Web3.HTTPProvider(args.rpc_url, request_kwargs={'timeout': 30}))
    if not w3.is_connected() or w3.eth.chain_id != args.chain_id:
        raise RuntimeError('RPC unreachable or chain ID mismatch')
    rows = []
    for item in args.tx:
        label, tx_hash = item.split(':', 1)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt['status'] != 1:
            raise RuntimeError(f'Transaction reverted: {tx_hash}')
        tx = w3.eth.get_transaction(tx_hash)
        rows.append({
            'operation': label, 'tx_hash': tx_hash,
            'block_number': receipt['blockNumber'],
            'gas_used': receipt['gasUsed'],
            'effective_gas_price_wei': receipt['effectiveGasPrice'],
            'fee_eth': f"{receipt['gasUsed'] * receipt['effectiveGasPrice'] / 10**18:.18f}",
            'input_bytes': (len(bytes(tx['input']))),
            'chain_id': args.chain_id,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} verified transaction receipts to {args.output}')


if __name__ == '__main__':
    main()
