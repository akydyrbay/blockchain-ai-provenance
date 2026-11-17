#!/usr/bin/env python3
"""Download a Hugging Face model family tree and the hashes needed to register it.

Walks the Hub breadth-first from a base model over every `base_model` relation
(finetune, adapter, quantized, merge), then fetches each model's file list to read
the SHA-256 values the Hub publishes for weight files. No weights are downloaded.

Writes:
  <out>/hf_tree.csv        one row per model: parents, relations, depth, licence,
                           declared datasets, weights/dataset/metadata hashes, status
  <out>/hf_tree_meta.json  pull time, limits, whether the walk was truncated,
                           request counts, library versions, summary statistics

Merges keep all of their parents. A parent outside the walked family is added as an
extra root ("external_root") but its own ancestors are not walked.

Status values (first matching rule wins):
  ok                      registrable
  cycle                   the parent links contain a cycle
  info_unavailable        the model's file list could not be read (gated, deleted)
  no_weight_hashes        no weight file with a published SHA-256
  duplicate_weights       same weights hash as an earlier model (in BFS order)
  ancestor_excluded       a parent is not registrable

Set HF_TOKEN to use an access token (higher rate limit); it is never written out.
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

API = 'https://huggingface.co/api'
ROOT = Path(__file__).resolve().parents[1]
RELATIONS = ('finetune', 'adapter', 'quantized', 'merge')
WEIGHT_EXTENSIONS = ('.safetensors', '.bin', '.pt', '.pth', '.h5', '.msgpack', '.onnx',
                     '.gguf', '.ckpt', '.keras', '.tflite', '.ot')
NOT_WEIGHTS = re.compile(
    r'(^|/)(training_args|optimizer|scheduler|scaler|rng_state[^/]*|trainer_state)\.[^/]+$')
SKIPPED_DIRS = re.compile(r'(^|/)(runs|checkpoint-[^/]+|logs|\.ipynb_checkpoints)/')
ZERO = '0x' + '00' * 32
UNDECLARED_DATASETS = 'dataset:undeclared'
FIELDS = ['model_id', 'depth', 'bfs_depth', 'n_parents', 'parents', 'relations', 'license',
          'datasets', 'data_ref_hash', 'n_weight_files', 'weights_hash', 'meta_hash', 'repo_sha',
          'created_at', 'library', 'pipeline_tag', 'status']


class Hub:
    """Small Hub API client that respects the published rate limit."""

    def __init__(self, token: str | None, min_interval: float):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'provenance-research-client'
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'
        self.min_interval = min_interval
        self.last = 0.0
        self.requests = 0
        self.waits = 0

    def get(self, url: str, params=None) -> requests.Response | None:
        for attempt in range(8):
            delay = self.min_interval - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=60)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            self.requests += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                self.waits += 1
                time.sleep(self._reset_seconds(resp) if resp.status_code == 429 else 2 ** attempt)
                continue
            return resp
        return None

    @staticmethod
    def _reset_seconds(resp: requests.Response) -> float:
        match = re.search(r't=(\d+)', resp.headers.get('RateLimit', ''))
        if match:
            return int(match.group(1)) + 1
        return float(resp.headers.get('Retry-After', 30))

    def children(self, model_id: str) -> list[dict]:
        url = f'{API}/models'
        params = {'filter': f'base_model:{model_id}', 'limit': 1000,
                  'expand[]': ['cardData', 'tags', 'createdAt', 'library_name', 'pipeline_tag']}
        found = []
        while url:
            resp = self.get(url, params)
            if resp is None or resp.status_code != 200:
                raise RuntimeError(f'listing children of {model_id} failed')
            found.extend(resp.json())
            url = resp.links.get('next', {}).get('url')
            params = None  # the next link already carries the query
        return found

    def info(self, model_id: str) -> dict | None:
        resp = self.get(f'{API}/models/{quote(model_id, safe="/")}', {'blobs': 'true'})
        if resp is None or resp.status_code != 200:
            return None
        return resp.json()


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v]


def parents_of(entry: dict) -> dict[str, str]:
    """Map each declared parent to its relation, from card data and Hub tags."""
    relations = {}
    for tag in entry.get('tags', []):
        parts = tag.split(':', 2)
        if len(parts) == 3 and parts[0] == 'base_model' and parts[1] in RELATIONS:
            relations[parts[2]] = parts[1]
    for parent in as_list((entry.get('cardData') or {}).get('base_model')):
        relations.setdefault(parent, 'unspecified')
    return relations


def licence_of(entry: dict) -> str:
    card = entry.get('cardData') or {}
    value = card.get('license')
    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        for tag in entry.get('tags', []):
            if tag.startswith('license:'):
                value = tag.split(':', 1)[1]
                break
    return (value or '').strip().lower()


def datasets_of(entry: dict) -> list[str]:
    card = entry.get('cardData') or {}
    names = set(as_list(card.get('datasets')))
    names.update(t.split(':', 1)[1] for t in entry.get('tags', []) if t.startswith('dataset:'))
    return sorted(names)


def is_weight_file(name: str) -> bool:
    return (name.lower().endswith(WEIGHT_EXTENSIONS)
            and not NOT_WEIGHTS.search(name) and not SKIPPED_DIRS.search(name))


def weight_hashes(info: dict) -> list[tuple[str, str]]:
    files = []
    for sibling in info.get('siblings', []):
        name = sibling.get('rfilename', '')
        sha = (sibling.get('lfs') or {}).get('sha256')
        if sha and is_weight_file(name):
            files.append((name, sha))
    return sorted(files)


def sha256_hex(text: str) -> str:
    return '0x' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def weights_hash(files: list[tuple[str, str]]) -> str:
    """SHA-256 over sorted 'path:sha256' lines of all weight files."""
    if not files:
        return ZERO
    return sha256_hex(''.join(f'{name}:{sha}\n' for name, sha in files))


def data_ref_hash(datasets: list[str]) -> str:
    """SHA-256 over sorted dataset names, or over a fixed sentinel if none are declared."""
    return sha256_hex('\n'.join(datasets) if datasets else UNDECLARED_DATASETS)


def meta_hash(model_id: str, repo_sha: str, licence: str, relations: dict[str, str]) -> str:
    """SHA-256 of canonical JSON {id, repo_sha, license, relations} (sorted keys, no spaces).

    `relations` maps each parent to its relation; it is empty for every root.
    """
    record = {'id': model_id, 'repo_sha': repo_sha, 'license': licence, 'relations': relations}
    return sha256_hex(json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False))


def walk(hub: Hub, base: str, max_models: int, max_depth: int):
    """Breadth-first walk; returns (nodes in BFS order, entries, bfs depth, truncated)."""
    entries = {base: {'id': base}}
    bfs_depth = {base: 0}
    order = [base]
    queue = collections.deque([base])
    truncated = False
    while queue:
        model = queue.popleft()
        if bfs_depth[model] >= max_depth:
            continue
        for child in hub.children(model):
            cid = child['id']
            if cid in bfs_depth:
                continue
            if len(order) >= max_models:
                truncated = True
                break
            entries[cid] = child
            bfs_depth[cid] = bfs_depth[model] + 1
            order.append(cid)
            queue.append(cid)
        if truncated:
            break
        print(f'\rwalked {len(order)} models, queue {len(queue)}, requests {hub.requests}',
              end='', file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return order, entries, bfs_depth, truncated or bool(queue and len(order) >= max_models)


def topological_depths(order: list[str], parents: dict[str, list[str]]):
    """Longest-path depth from any root; nodes on a cycle get None."""
    depth, state = {}, {}

    def visit(node: str) -> int | None:
        if node in depth:
            return depth[node]
        if state.get(node) == 'active':
            return None
        state[node] = 'active'
        result = 0
        for parent in parents.get(node, []):
            d = visit(parent)
            if d is None:
                result = None
                break
            result = max(result, d + 1)
        state[node] = 'done'
        depth[node] = result
        return result

    sys.setrecursionlimit(max(10000, 4 * len(order)))
    for node in order:
        visit(node)
    return depth


def classify(order, rows) -> None:
    """Assign status in a parents-first pass so exclusions propagate to descendants."""
    seen_weights = {}
    position = {m: i for i, m in enumerate(order)}
    ranked = sorted(order, key=lambda m: (rows[m]['depth'] is None, rows[m]['depth'] or 0,
                                          position[m]))
    for model in ranked:
        row = rows[model]
        if row['depth'] is None:
            row['status'] = 'cycle'
        elif row['status'] == 'info_unavailable':
            pass
        elif row['weights_hash'] == ZERO:
            row['status'] = 'no_weight_hashes'
        elif row['weights_hash'] in seen_weights:
            row['status'] = 'duplicate_weights'
        elif any(rows[p]['status'] != 'ok' for p in row['_parents']):
            row['status'] = 'ancestor_excluded'
        else:
            row['status'] = 'ok'
        if row['status'] == 'ok':
            seen_weights[row['weights_hash']] = model


def summarize(order, rows) -> dict:
    ok = [m for m in order if rows[m]['status'] == 'ok']
    relation_counts = collections.Counter()
    for m in order:
        for rel in rows[m]['relations'].split(';'):
            relation_counts[rel or 'root'] += 1
    with_parents = [m for m in order if rows[m]['_parents']]
    child_counts = collections.Counter(p for m in order for p in rows[m]['_parents'])
    return {
        'n_models': len(order),
        'n_external_roots': sum(rows[m]['relations'] == 'external_root' for m in order),
        'max_depth': max((rows[m]['depth'] or 0) for m in order),
        'models_per_depth': dict(sorted(collections.Counter(
            str(rows[m]['depth']) for m in order).items())),
        'models_per_relation': dict(relation_counts.most_common()),
        'models_per_status': dict(collections.Counter(rows[m]['status'] for m in order)
                                  .most_common()),
        'n_multi_parent': sum(rows[m]['n_parents'] > 1 for m in order),
        'n_multi_parent_registrable': sum(rows[m]['n_parents'] > 1 for m in ok),
        'share_with_weights_hash': round(
            sum(rows[m]['weights_hash'] != ZERO for m in order) / len(order), 4),
        'share_declaring_datasets': round(
            sum(bool(rows[m]['datasets']) for m in order) / len(order), 4),
        'share_declaring_license': round(
            sum(bool(rows[m]['license']) for m in order) / len(order), 4),
        'licenses': dict(collections.Counter(rows[m]['license'] or '(none)' for m in order)
                         .most_common()),
        'mean_children_of_parents': round(
            sum(child_counts.values()) / max(len(child_counts), 1), 2),
        'n_registrable': len(ok),
        'share_registrable': round(len(ok) / len(order), 4),
        'registrable_per_depth': dict(sorted(collections.Counter(
            str(rows[m]['depth']) for m in ok).items())),
        'n_with_parents': len(with_parents),
    }


def survey(base, order, entries, bfs_depth, truncated, hub) -> None:
    """Print a quick tree profile from the walk alone (used to choose a base model)."""
    parents = {m: list(parents_of(entries[m])) if m != base else [] for m in order}
    in_tree = set(order)
    depth = topological_depths(order, {m: [p for p in ps if p in in_tree] for m, ps in parents.items()})
    result = {
        'base_model': base,
        'n_models': len(order),
        'truncated': truncated,
        'max_depth': max(depth.values(), key=lambda d: d or 0),
        'models_per_depth': dict(sorted(collections.Counter(str(d) for d in depth.values()).items())),
        'n_multi_parent': sum(len(ps) > 1 for ps in parents.values()),
        'n_with_external_parent': sum(any(p not in in_tree for p in ps) for ps in parents.values()),
        'requests': hub.requests,
    }
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--base', default='TinyLlama/TinyLlama-1.1B-Chat-v1.0')
    parser.add_argument('--max-models', type=int, default=6000)
    parser.add_argument('--max-depth', type=int, default=12)
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--min-interval', type=float, default=0.62,
                        help='seconds between requests (500 per 5 min = 0.6 s)')
    parser.add_argument('--survey', action='store_true',
                        help='walk only (no file lists, no CSV); print tree size, depth and merges')
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    hub = Hub(os.environ.get('HF_TOKEN'), args.min_interval)
    order, entries, bfs_depth, truncated = walk(hub, args.base, args.max_models, args.max_depth)
    if args.survey:
        survey(args.base, order, entries, bfs_depth, truncated, hub)
        return

    parents = {m: list(parents_of(entries[m])) if m != args.base else [] for m in order}
    relations = {m: parents_of(entries[m]) if m != args.base else {} for m in order}

    # Parents outside the walked family become extra roots (not walked further).
    in_tree = set(order)
    for m in list(order):
        for p in parents[m]:
            if p not in in_tree:
                in_tree.add(p)
                order.append(p)
                entries[p] = {'id': p}
                parents[p], relations[p] = [], {}
                bfs_depth[p] = None

    depth = topological_depths(order, parents)
    rows = {}
    for i, m in enumerate(order, 1):
        info = hub.info(m)
        entry = entries[m]
        if info:
            entry = {**info, **{k: v for k, v in entry.items() if v}}
        files = weight_hashes(info) if info else []
        datasets = datasets_of(entry)
        external = bfs_depth[m] is None
        licence = licence_of(entry)
        repo_sha = (info or {}).get('sha', '')
        rows[m] = {
            'model_id': m,
            'depth': depth[m],
            'bfs_depth': bfs_depth[m] if bfs_depth[m] is not None else '',
            'n_parents': len(parents[m]),
            'parents': ';'.join(parents[m]),
            'relations': 'external_root' if external else ';'.join(relations[m][p] for p in parents[m]),
            'license': licence,
            'datasets': ';'.join(datasets),
            'data_ref_hash': data_ref_hash(datasets),
            'n_weight_files': len(files),
            'weights_hash': weights_hash(files),
            'meta_hash': meta_hash(m, repo_sha, licence, relations[m]),
            'repo_sha': repo_sha,
            'created_at': entry.get('createdAt', ''),
            'library': entry.get('library_name', '') or '',
            'pipeline_tag': entry.get('pipeline_tag', '') or '',
            'status': '' if info else 'info_unavailable',
            '_parents': parents[m],
        }
        print(f'\rfile lists {i}/{len(order)}, requests {hub.requests}',
              end='', file=sys.stderr, flush=True)
    print(file=sys.stderr)
    classify(order, rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / 'hf_tree.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for m in order:
            writer.writerow(rows[m])

    meta = {
        'base_model': args.base,
        'pulled_at_utc': started.isoformat(timespec='seconds'),
        'finished_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'limits': {'max_models': args.max_models, 'max_depth': args.max_depth},
        'truncated': truncated,
        'relations_followed': list(RELATIONS),
        'weight_extensions': list(WEIGHT_EXTENSIONS),
        'weights_hash_rule': "SHA-256 over sorted 'path:sha256\\n' lines of weight files",
        'data_ref_hash_rule': f"SHA-256 over sorted dataset names joined by '\\n'; "
                              f"'{UNDECLARED_DATASETS}' if none",
        'meta_hash_rule': "SHA-256 of canonical JSON {id, repo_sha, license, relations: "
                          "{parent: relation}} (sorted keys, no spaces)",
        'requests': hub.requests,
        'rate_limit_waits': hub.waits,
        'python': platform.python_version(),
        'requests_version': requests.__version__,
        'summary': summarize(order, rows),
    }
    meta_path = args.out_dir / 'hf_tree_meta.json'
    meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(meta['summary'], indent=2))
    print(f'Wrote {csv_path} and {meta_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
