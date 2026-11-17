#!/usr/bin/env python3
"""Check that the Hub's published weight-file SHA-256 values match the real bytes.

Picks registrable models (status ok in data/hf_tree.csv) with a fixed seed, lists
their weight files at the exact repository revision recorded in the pull, downloads
every weight file and hashes it while streaming (nothing is written to disk). For each
model it also recomputes the weights hash from the downloaded digests and compares it
with the value in hf_tree.csv.

Writes:
  <out>                  one row per weight file: hub vs. local SHA-256, size, match
  <out stem>_summary.json seed, sample, totals, per-model weights-hash result

Use --dry-run first to see how many bytes will be downloaded. Set HF_TOKEN for gated
repositories; it is never written out.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from hf_lineage import API, Hub, is_weight_file, weights_hash

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['model_id', 'repo_sha', 'file', 'size_bytes', 'hub_sha256', 'local_sha256',
          'match', 'seconds', 'error']
CHUNK = 8 * 1024 * 1024


def sample_models(tree: Path, n: int, seed: int) -> list[dict]:
    with tree.open(newline='', encoding='utf-8') as f:
        ok = [r for r in csv.DictReader(f) if r['status'] == 'ok']
    return random.Random(seed).sample(ok, n)


def weight_files(hub: Hub, model_id: str, revision: str) -> list[dict] | None:
    url = f'{API}/models/{quote(model_id, safe="/")}/revision/{revision}'
    resp = hub.get(url, {'blobs': 'true'})
    if resp is None or resp.status_code != 200:
        return None
    files = []
    for s in resp.json().get('siblings', []):
        lfs = s.get('lfs') or {}
        if lfs.get('sha256') and is_weight_file(s.get('rfilename', '')):
            files.append({'file': s['rfilename'], 'sha256': lfs['sha256'],
                          'size': lfs.get('size', s.get('size'))})
    return sorted(files, key=lambda f: f['file'])


def stream_sha256(hub: Hub, model_id: str, revision: str, name: str) -> str:
    url = (f'https://huggingface.co/{quote(model_id, safe="/")}/resolve/{revision}/'
           f'{quote(name, safe="/")}')
    digest = hashlib.sha256()
    with hub.session.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--tree', type=Path, default=ROOT / 'data' / 'hf_tree.csv')
    parser.add_argument('--n', type=int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'results' / 'anvil' / 'weight_spot_check.csv')
    parser.add_argument('--min-interval', type=float, default=0.62)
    parser.add_argument('--dry-run', action='store_true',
                        help='list the sample and its download size, download nothing')
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    hub = Hub(os.environ.get('HF_TOKEN'), args.min_interval)
    sample = sample_models(args.tree, args.n, args.seed)
    listed = {r['model_id']: weight_files(hub, r['model_id'], r['repo_sha']) for r in sample}
    total = sum(f['size'] or 0 for files in listed.values() if files for f in files)
    for r in sample:
        files = listed[r['model_id']]
        size = sum(f['size'] or 0 for f in files) if files else 0
        print(f"{r['model_id']}: {len(files) if files else 'listing failed'} files, "
              f'{size / 2**30:.2f} GiB', file=sys.stderr)
    print(f'total {total / 2**30:.2f} GiB', file=sys.stderr)
    if args.dry_run:
        return

    rows, models = [], []
    for r in sample:
        mid, rev = r['model_id'], r['repo_sha']
        files = listed[mid]
        if files is None:
            rows.append({'model_id': mid, 'repo_sha': rev, 'match': '',
                         'error': 'file listing failed'})
            models.append({'model_id': mid, 'weights_hash_match': None,
                           'error': 'file listing failed'})
            continue
        local = []
        for f in files:
            t0 = time.perf_counter()
            row = {'model_id': mid, 'repo_sha': rev, 'file': f['file'],
                   'size_bytes': f['size'], 'hub_sha256': f['sha256']}
            try:
                sha = stream_sha256(hub, mid, rev, f['file'])
                row.update(local_sha256=sha, match=sha == f['sha256'], error='')
                local.append((f['file'], sha))
            except Exception as exc:  # recorded as an operational error, not a mismatch
                row.update(local_sha256='', match='', error=f'{type(exc).__name__}: {exc}')
            row['seconds'] = round(time.perf_counter() - t0, 2)
            rows.append(row)
            print(f"{mid}/{f['file']}: {row['match'] if row['match'] != '' else row['error']}",
                  file=sys.stderr)
        complete = len(local) == len(files)
        models.append({
            'model_id': mid,
            'n_files': len(files),
            'weights_hash_csv': r['weights_hash'],
            'weights_hash_local': weights_hash(local) if complete else None,
            'weights_hash_match': weights_hash(local) == r['weights_hash'] if complete else None,
            'error': '' if complete else 'not every file downloaded',
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)

    checked = [r for r in rows if r.get('match') != '']
    summary = {
        'started_at_utc': started.isoformat(timespec='seconds'),
        'finished_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'tree': args.tree.resolve().relative_to(ROOT).as_posix()
                if args.tree.resolve().is_relative_to(ROOT) else str(args.tree),
        'tree_sha256': hashlib.sha256(args.tree.read_bytes()).hexdigest(),
        'seed': args.seed,
        'n_models': len(sample),
        'n_files': len(rows),
        'n_files_checked': len(checked),
        'n_files_matching': sum(r['match'] is True for r in checked),
        'n_operational_errors': len(rows) - len(checked),
        'bytes_downloaded': sum(r['size_bytes'] or 0 for r in checked),
        'all_match': bool(checked) and len(checked) == len(rows)
                     and all(r['match'] is True for r in checked),
        'models': models,
    }
    summary_path = args.out.with_name(args.out.stem + '_summary.json')
    summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'models'}, indent=2))


if __name__ == '__main__':
    main()
