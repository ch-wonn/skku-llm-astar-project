#!/usr/bin/env python3
"""CPU evaluation, one method/prompt per directory, checkpointed per case."""
import argparse
import contextlib
import copy
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import uuid

BASE = Path(__file__).resolve().parent


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(path):
    maps=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(maps,list) or not maps:
        raise ValueError('Dataset must be a nonempty list of maps')
    cases=[]
    ids=set()
    for map_index,m in enumerate(maps):
        mid=m.get('id',map_index)
        if str(mid) in ids:
            raise ValueError('Duplicate map ID')
        ids.add(str(mid))
        for j,pair in enumerate(m['start_goal']):
            q={k:copy.deepcopy(m[k]) for k in (
                'range_x','range_y','horizontal_barriers','vertical_barriers')}
            q.update(start=copy.deepcopy(pair[0]),goal=copy.deepcopy(pair[1]))
            cases.append({'index':len(cases),'map_id':mid,'pair_index':j,'query':q})
    if not cases:
        raise ValueError('No cases')
    return maps,cases


def progress(out, expected):
    records=[json.loads(p.read_text()) for p in (out/'cases').glob('*.json')]
    counts={s:sum(r['status']==s for r in records) for s in ['valid','invalid','error']}
    calls=[json.loads(p.read_text()) for p in (out/'api_calls').glob('*.json')]
    parsed=sum(r.get('waypoint_audit',{}).get('parse_ok',False) for r in records)
    report=dict(expected=expected,attempted=len(records),unattempted=expected-len(records),
                **counts,parse_ok=parsed,
                cases_with_intermediate=sum(r.get('waypoint_audit',{}).get('intermediate_count',0)>0 for r in records),
                recorded_responses=len(calls),
                prompt_tokens=sum(c.get('usage',{}).get('prompt_tokens',0) for c in calls),
                completion_tokens=sum(c.get('usage',{}).get('completion_tokens',0) for c in calls),
                missing_usage=sum(not c.get('usage') for c in calls))
    save(out/'progress.json',report)
    print(json.dumps(report,indent=2),flush=True)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--method',choices=['astar','llm'],default='llm')
    ap.add_argument('--prompt',choices=['standard','cot','repe'],default='standard')
    ap.add_argument('--dataset',type=Path,default=BASE/'dataset/environment_50_30.json')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--limit',type=int)
    ap.add_argument('--max-tokens',type=int,default=1000)
    ap.add_argument('--case-timeout',type=int,default=180)
    ap.add_argument('--validate-only',action='store_true')
    ap.add_argument('--report-only',action='store_true')
    ap.add_argument('--require-public-count',action='store_true')
    ap.add_argument('--plots',type=int,default=3,help='first three natural case indices only')
    args=ap.parse_args()
    if args.max_tokens<1 or args.case_timeout<1 or args.plots<0:
        ap.error('Invalid token, timeout or plot limit')
    maps,cases=load_cases(args.dataset)
    print(f'{len(maps)} maps, {len(cases)} cases; dataset SHA256={sha(args.dataset)}')
    if args.require_public_count and (len(maps)!=100 or len(cases)!=1000 or any(len(m['start_goal'])!=10 for m in maps)):
        ap.error('Expected 100 maps with 10 pairs per map')
    if args.limit is not None and not 1<=args.limit<=len(cases):
        ap.error('Invalid --limit')
    if args.validate_only:
        return
    out=args.out.resolve()
    if args.report_only:
        if not (out/'manifest.json').exists():
            ap.error('No existing experiment')
        progress(out,len(cases)); return
    if args.method=='llm' and not os.environ.get('OPENAI_API_KEY'):
        ap.error('Set OPENAI_API_KEY externally')
    # This study fixes the requested output ceiling in the manifest.
    os.environ['LLM_MAX_OUTPUT_TOKENS']=str(args.max_tokens)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import openai
    from llmastar.env.search.plotting import Plotting
    from reproduction_support import AStar,AuditedLLMAStar,validate_path
    out.mkdir(parents=True,exist_ok=True)
    lock=(out/'.run.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    source=[BASE/'run_reproduction.py',BASE/'reproduction_support.py']+sorted((BASE/'llmastar').rglob('*.py'))
    model=os.environ.get('OPENAI_MODEL','gpt-4o-mini')
    manifest=dict(schema=2,method=args.method,prompt=args.prompt if args.method=='llm' else None,
        model=model if args.method=='llm' else None,temperature=0,stop=None,max_tokens=args.max_tokens,
        case_timeout=args.case_timeout,api_timeout=60,automatic_retries=0,plots_first_n=args.plots,
        api_base=os.environ.get('OPENAI_API_BASE','https://api.openai.com/v1'),
        expected=len(cases),map_count=len(maps),dataset_sha256=sha(args.dataset),
        python=platform.python_version(),packages={n:importlib.metadata.version(n) for n in ['openai','numpy','matplotlib','shapely']},
        source_sha256={str(p.relative_to(BASE)):sha(p) for p in source})
    mp=out/'manifest.json'
    if mp.exists() and json.loads(mp.read_text())!=manifest:
        lock.close()
        raise RuntimeError('Manifest mismatch: use a NEW output directory; never mix changed settings/code.')
    if not mp.exists():
        if any((out/'cases').glob('*.json')):
            lock.close()
            raise RuntimeError('Existing cases without a manifest')
        save(mp,manifest)
        git=subprocess.run(['git','rev-parse','HEAD'],cwd=BASE,text=True,capture_output=True)
        save(out/'provenance.json',{'team_commit_at_start':git.stdout.strip(),
            'upstream':(BASE/'UPSTREAM_COMMIT.txt').read_text().strip(),
            'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    # Spread smoke cases over maps; full run still covers every original case.
    n=args.limit or len(cases)
    selected=cases if n==len(cases) else [cases[i*len(cases)//n] for i in range(n)]
    original_api=openai.ChatCompletion.create
    original_plot=Plotting.animation
    active={}
    def tracked(*a,**kw):
        started=time.perf_counter()
        response=original_api(*a,**kw)
        choice=response['choices'][0]
        item={'index':active['index'],'model_requested':kw['model'],'model_returned':response.get('model'),
              'request_messages':kw['messages'],'temperature':kw.get('temperature'),
              'max_tokens':kw.get('max_tokens'),'stop':kw.get('stop'),
              'response_text':choice['message'].get('content'),'finish_reason':choice.get('finish_reason'),
              'usage':dict(response.get('usage') or {}),'seconds':time.perf_counter()-started}
        name=uuid.uuid4().hex+'.json'
        save(out/'api_calls'/name,item)
        active.setdefault('api_files',[]).append(name)
        return response
    def plot(self,path,*a,**kw):
        active['path']=copy.deepcopy(path)
        if active['index']<args.plots:
            return original_plot(self,path,*a,**kw)
    def timeout(signum,frame):
        raise TimeoutError('Local case deadline')
    openai.ChatCompletion.create=tracked
    Plotting.animation=plot
    signal.signal(signal.SIGALRM,timeout)
    (out/'plots').mkdir(exist_ok=True)
    consecutive_errors=0
    try:
        for case in selected:
            path=out/'cases'/f'{case["index"]:04d}.json'
            if path.exists():
                print(f'SKIP {case["index"]:04d}',flush=True);continue
            active.clear();active.update(index=case['index'])
            row=dict(case,status='error',method=args.method,prompt=manifest['prompt'])
            algorithm=None
            started=time.perf_counter()
            try:
                signal.alarm(args.case_timeout)
                algorithm=AStar() if args.method=='astar' else AuditedLLMAStar(llm='gpt',prompt=args.prompt)
                with contextlib.redirect_stdout(io.StringIO()):
                    result=algorithm.searching(copy.deepcopy(case['query']),filepath=str(out/'plots'/f'{case["index"]:04d}.png'))
                valid,reason,route=validate_path(active.get('path',[]),case['query'],result)
                row.update(result=result,path=route,status='valid' if valid else 'invalid',validation_error=reason)
            except Exception as exc:
                # Avoid serializing messages that could include credentials.
                row['error_type']=type(exc).__name__
            finally:
                signal.alarm(0)
                if algorithm is not None and hasattr(algorithm,'audit'):
                    row['waypoint_audit']=algorithm.audit
                row['api_files']=active.get('api_files',[])
                row['elapsed_seconds_including_plot_and_validation']=time.perf_counter()-started
                plt.close('all')
            save(path,row)
            audit=row.get('waypoint_audit',{})
            print(f'{case["index"]:04d} {args.method}/{args.prompt}: {row["status"]}; parse={audit.get("parse_ok")}; intermediate={audit.get("intermediate_count")}; error={row.get("error_type")}',flush=True)
            consecutive_errors=consecutive_errors+1 if row['status']=='error' else 0
            fatal=row.get('error_type') in {'AuthenticationError','PermissionError','InvalidRequestError','RateLimitError'}
            if fatal or consecutive_errors>=3:
                raise RuntimeError('Stopped after API configuration error or 3 consecutive errors. Inspect records before continuing.')
    finally:
        openai.ChatCompletion.create=original_api
        Plotting.animation=original_plot
        progress(out,len(cases))
        fcntl.flock(lock,fcntl.LOCK_UN)
        lock.close()


if __name__=='__main__':
    main()
