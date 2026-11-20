#!/usr/bin/env python3
"""Place in baseline/. Evaluate the public cases without changing search logic.

Python 3.10+, Windows/Linux. Uses the existing openai==0.27.2 adapter.
No automatic retries. Each method/case is checkpointed separately.
"""
import argparse
import contextlib
import copy
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import time
import uuid

BASE = Path(__file__).resolve().parent


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire_run_lock(out):
    """Prevent concurrent writers to one result folder on Windows or Unix."""
    lock = (out / '.run.lock').open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        lock.close()
        raise
    return lock


def release_run_lock(lock):
    if os.name == 'nt':
        import msvcrt
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()


def load_cases(path):
    maps = json.loads(path.read_text(encoding='utf-8'))
    cases = []
    ids = set()
    if len(maps) != 100:
        raise ValueError('Expected exactly 100 maps')
    for m in maps:
        if len(m['start_goal']) != 10 or m['id'] in ids:
            raise ValueError('Expected unique map IDs and 10 pairs per map')
        ids.add(m['id'])
        for j, pair in enumerate(m['start_goal']):
            q = {k: copy.deepcopy(m[k]) for k in (
                'range_x', 'range_y', 'horizontal_barriers', 'vertical_barriers')}
            q.update(start=pair[0], goal=pair[1])
            cases.append({'index': len(cases), 'map_id': m['id'],
                          'pair_index': j, 'query': q})
    return cases


def validate_path(path, query, result):
    """Independent segment checks; same closed boundary convention as upstream."""
    from shapely.geometry import LineString
    p = [tuple(v) for v in path]
    start, goal = tuple(query['start']), tuple(query['goal'])
    if p and p[0] == goal and p[-1] == start:
        p.reverse()  # upstream A* returns goal-to-start
    if not p or p[0] != start or p[-1] != goal:
        return False, 'endpoints', p
    xmin, xmax = query['range_x'][0], query['range_x'][1] - 1
    ymin, ymax = query['range_y'][0], query['range_y'][1] - 1
    if any(not (xmin < x < xmax and ymin < y < ymax) for x, y in p):
        return False, 'boundary', p
    barriers = [LineString([(a, y), (b, y)])
                for y, a, b in query['horizontal_barriers']]
    barriers += [LineString([(x, a), (x, b)])
                 for x, a, b in query['vertical_barriers']]
    length = 0.0
    for a, b in zip(p, p[1:]):
        dx, dy = abs(a[0]-b[0]), abs(a[1]-b[1])
        if (dx, dy) not in {(0, 1), (1, 0), (1, 1)}:
            return False, 'motion', p
        if any(LineString([a, b]).intersects(wall) for wall in barriers):
            return False, 'collision', p
        length += math.dist(a, b)
    if not math.isclose(length, result['length'], rel_tol=1e-9, abs_tol=1e-9):
        return False, 'length', p
    return True, None, p


def summarize(out, cases):
    records = {}
    selected_indices = {case['index'] for case in cases}
    for p in sorted((out / 'cases').glob('*.json')):
        r = json.loads(p.read_text())
        key = (r['index'], r['method'])
        if key in records or r['index'] not in selected_indices:
            raise ValueError('Duplicate or unexpected case')
        records[key] = r
    report = {'expected_per_method': len(cases), 'selected_maps':
              len({case['map_id'] for case in cases}),
              'methods': {}, 'paired_valid': 0}
    for method in ['astar', 'llm']:
        rows = [r for (i, m), r in records.items() if m == method]
        valid = sum(r['status'] == 'valid' for r in rows)
        report['methods'][method] = {
            'attempted': len(rows), 'valid': valid,
            'invalid': sum(r['status'] == 'invalid' for r in rows),
            'error': sum(r['status'] == 'error' for r in rows),
            'unattempted': len(cases)-len(rows),
            'valid_percent_of_attempted': 100*valid/len(rows) if rows else None,
            'valid_percent_of_selected': 100*valid/len(cases)}
    llm_valid = [r for (i, method), r in records.items()
                 if method == 'llm' and r['status'] == 'valid']
    report['llm_waypoints'] = {
        'valid_cases_with_intermediate_waypoint': sum(
            len(r['result']['llm_output']) > 2 for r in llm_valid),
        'valid_cases_start_goal_only': sum(
            len(r['result']['llm_output']) == 2 for r in llm_valid),
    }
    paired = [(records[(i, 'astar')], records[(i, 'llm')])
              for i in (case['index'] for case in cases)
              if all((i, m) in records and records[(i, m)]['status'] == 'valid'
                     for m in ['astar', 'llm'])]
    report['paired_valid'] = len(paired)
    report['ratios_on_paired_valid_only'] = {}
    for field in ['operation', 'storage', 'length']:
        values = [b['result'][field]/a['result'][field] for a, b in paired
                  if a['result'][field] > 0 and b['result'][field] > 0]
        report['ratios_on_paired_valid_only'][field] = {
            'n': len(values), 'excluded': len(paired)-len(values),
            'geometric_mean_percent': 100*math.exp(statistics.mean(map(math.log, values)))
            if values else None}
    calls = [json.loads(p.read_text()) for p in (out/'api_calls').glob('*.json')]
    inputs = sum(c.get('usage', {}).get('prompt_tokens', 0) for c in calls)
    outputs = sum(c.get('usage', {}).get('completion_tokens', 0) for c in calls)
    report['api_usage'] = {
        'recorded_responses': len(calls), 'prompt_tokens': inputs,
        'completion_tokens': outputs,
        'responses_missing_usage': sum(not c.get('usage') for c in calls),
        'estimated_usd_no_cache_discount': inputs*0.15/1e6 + outputs*0.60/1e6,
        'note': 'Recorded responses only; interrupted or failed requests may incur unrecorded charges. Rates: 2026-11-19.'}
    save(out/'summary.json', report)
    with (out/'cases.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['index','map_id','pair_index','method','status','operation',
                         'storage','length','elapsed_seconds_including_plot','error_type'])
        for _, r in sorted(records.items()):
            result = r.get('result', {})
            writer.writerow([r['index'],r['map_id'],r['pair_index'],r['method'],r['status'],
                             result.get('operation'),result.get('storage'),result.get('length'),
                             r.get('elapsed_seconds_including_plot'),r.get('error_type')])
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=['astar','llm','both'], default='both')
    parser.add_argument('--prompt', choices=['standard', 'cot', 'repe'], default='standard')
    parser.add_argument('--pairs-per-map', type=int, default=10,
                        help='Use the first N start/goal pairs on each of the 100 maps')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--out', type=Path,
                        help='Default: baseline/experiment_results/gpt4omini_<prompt>_<N>pairs_fixed')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--summary-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error('--limit must be between 1 and 1000')
    if not 1 <= args.pairs_per_map <= 10:
        parser.error('--pairs-per-map must be between 1 and 10')
    dataset = BASE/'dataset'/'environment_50_30.json'
    all_cases = load_cases(dataset)
    cases = [case for case in all_cases
             if case['pair_index'] < args.pairs_per_map]
    print(f'Dataset: 100 maps, {len(all_cases)} cases; '
          f'selected {len(cases)} across all maps; SHA256={digest(dataset)}')
    if args.validate_only:
        return
    name = f'gpt4omini_{args.prompt}_{args.pairs_per_map}pairs_fixed'
    out = (args.out or BASE/'experiment_results'/name).resolve()
    if args.summary_only:
        if not (out/'manifest.json').is_file():
            parser.error('No existing experiment manifest')
        existing = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        if (existing.get('prompt') != args.prompt
                or existing.get('pairs_per_map') != args.pairs_per_map):
            parser.error('Prompt or pair selection differs from the saved run')
        summarize(out, cases)
        return
    if os.environ.get('OPENAI_MODEL', 'gpt-4o-mini') != 'gpt-4o-mini':
        parser.error('This experiment is fixed to gpt-4o-mini')
    if args.method != 'astar' and not os.environ.get('OPENAI_API_KEY'):
        parser.error('Set OPENAI_API_KEY before LLM evaluation')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import openai
    import llmastar
    from llmastar.pather import AStar, LLMAStar
    from llmastar.env.search.plotting import Plotting
    if Path(llmastar.__file__).resolve() != (BASE/'llmastar'/'__init__.py').resolve():
        raise RuntimeError('Wrong llmastar imported; use the local baseline source')
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    out.mkdir(parents=True, exist_ok=True)
    lock = acquire_run_lock(out)
    files = [Path(__file__).resolve()] + sorted((BASE/'llmastar').rglob('*.py'))
    manifest = {'dataset_sha256': digest(dataset), 'model': 'gpt-4o-mini',
                'prompt': args.prompt, 'pairs_per_map': args.pairs_per_map,
                'expected_cases': len(cases),
                'timeout_seconds_per_method': 180, 'automatic_retries': 0,
                'python': platform.python_version(),
                'packages': {n: importlib.metadata.version(n) for n in
                             ['openai','numpy','matplotlib','shapely']},
                'source_sha256': {str(p.relative_to(BASE)): digest(p) for p in files}}
    mp = out/'manifest.json'
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise RuntimeError('Code/environment changed. Use a NEW --out directory; do not mix runs.')
    if not mp.exists():
        save(mp, manifest)
        git = subprocess.run(['git','rev-parse','HEAD'], cwd=BASE, capture_output=True, text=True)
        upstream = BASE/'UPSTREAM_COMMIT.txt'
        save(out/'provenance.json', {'team_commit_at_start': git.stdout.strip(),
             'upstream_commit_file': upstream.read_text().strip() if upstream.exists() else None,
             'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    original_api = openai.ChatCompletion.create
    original_plot = Plotting.animation
    active = {}
    def tracked_api(*a, **kw):
        if kw.get('model') != 'gpt-4o-mini' or kw.get('max_tokens', 0) > 1000:
            raise ValueError('Unexpected model or output token limit')
        kw['request_timeout'] = 60
        t = time.perf_counter()
        response = original_api(*a, **kw)
        call = {'index': active['index'], 'method': active['method'],
                'model_requested': kw['model'], 'model_returned': response.get('model'),
                'elapsed_seconds': time.perf_counter()-t,
                'usage': dict(response.get('usage') or {}),
                'finish_reason': response['choices'][0].get('finish_reason'),
                'response_text': response['choices'][0]['message']['content']}
        save(out/'api_calls'/f'{uuid.uuid4().hex}.json', call)
        return response
    def capture_plot(self, path, *a, **kw):
        active['path'] = path
        if active['index'] < 10:
            return original_plot(self, path, *a, **kw)
    def timed_out(signum, frame):
        raise TimeoutError('180-second case limit')
    openai.ChatCompletion.create = tracked_api
    Plotting.animation = capture_plot
    has_alarm = hasattr(signal, 'SIGALRM')
    if has_alarm:
        signal.signal(signal.SIGALRM, timed_out)
    methods = ['astar','llm'] if args.method == 'both' else [args.method]
    (out/'plots').mkdir(exist_ok=True)
    try:
        for case in cases[:args.limit]:
            for method in methods:
                rp = out/'cases'/f'{case["index"]:04d}_{method}.json'
                if rp.exists():
                    print(f'SKIP {case["index"]:04d} {method}', flush=True)
                    continue
                active.clear()
                active.update(index=case['index'], method=method)
                row = dict(case, method=method, status='error')
                started = time.perf_counter()
                try:
                    if has_alarm:
                        signal.alarm(180)
                    algorithm = AStar() if method == 'astar' else LLMAStar(
                        llm='gpt', prompt=args.prompt)
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = algorithm.searching(copy.deepcopy(case['query']),
                            filepath=str(out/'plots'/f'{case["index"]:04d}_{method}.png'))
                    valid, reason, path = validate_path(active.get('path', []), case['query'], result)
                    row.update(result=result, path=path, validation_error=reason,
                               status='valid' if valid else 'invalid')
                except Exception as exc:
                    # Avoid saving exception messages that may contain credentials.
                    row['error_type'] = type(exc).__name__
                finally:
                    if has_alarm:
                        signal.alarm(0)
                    plt.close('all')
                row['elapsed_seconds_including_plot'] = time.perf_counter()-started
                save(rp, row)
                print(f'{case["index"]+1}/{args.limit} {method}: {row["status"]}', flush=True)
                if row.get('error_type') in {'AuthenticationError','PermissionError','InvalidRequestError','RateLimitError'}:
                    raise RuntimeError('API configuration/quota/rate error; stopped. Inspect saved error_type.')
    finally:
        openai.ChatCompletion.create = original_api
        Plotting.animation = original_plot
        summarize(out, cases)
    release_run_lock(lock)


if __name__ == '__main__':
    main()
