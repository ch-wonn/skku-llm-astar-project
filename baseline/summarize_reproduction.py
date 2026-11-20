#!/usr/bin/env python3
"""Table-1-style paired ratios; map-cluster bootstrap CIs (not repeated LLM trials)."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
from run_reproduction import save


def read_run(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    rows={}
    for p in (folder/'cases').glob('*.json'):
        r=json.loads(p.read_text())
        if r['index'] in rows:
            raise ValueError('Duplicate index')
        rows[r['index']]=r
    if len(rows)!=manifest['expected'] or set(rows)!=set(range(manifest['expected'])):
        raise ValueError(f'{folder}: incomplete; finish all cases before final statistics')
    return manifest,rows


def cluster_estimate(map_ids, nums, dens, draws, exponentiate=False):
    groups=sorted(set(map_ids),key=str)
    a=np.array([sum(v for k,v in zip(map_ids,nums) if k==g) for g in groups])
    b=np.array([sum(v for k,v in zip(map_ids,dens) if k==g) for g in groups])
    if b.sum()==0:
        return None
    resampled_den=b[draws].sum(axis=1)
    estimates=a[draws].sum(axis=1)[resampled_den>0]/resampled_den[resampled_den>0]
    if not len(estimates):
        return None
    if exponentiate:
        estimates=np.exp(estimates)
    return (100*np.quantile(estimates,[.025,.975])).tolist()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--bootstrap',type=int,default=5000)
    ap.add_argument('--seed',type=int,default=2026)
    args=ap.parse_args()
    if args.bootstrap<1000:
        ap.error('Use at least 1000 bootstrap resamples')
    root=args.root
    am,astar=read_run(root/'astar')
    if am['method']!='astar':
        raise ValueError('astar directory is not an A* run')
    report={'bootstrap_unit':'map (all start/goal pairs kept together)',
        'bootstrap_resamples':args.bootstrap,'seed':args.seed,
        'interpretation':'Across-map sampling uncertainty conditional on one observed response per case; NOT LLM repeatability.',
        'ci_warning':'An all-success or all-failure empirical dataset yields a degenerate bootstrap interval; it is not a guarantee for new maps.',
        'ratio_definition':'Geometric mean of per-case LLM-A*/A* ratios on paired valid cases only.',
        'methods':{},'invalid_old_run':'gpt4omini_standard: newline stop + parse fallback; excluded'}
    table=[]
    paired_csv=[]
    first_llm=None
    for name in ['astar','standard','cot','repe']:
        manifest,rows=(am,astar) if name=='astar' else read_run(root/name)
        if manifest['dataset_sha256']!=am['dataset_sha256']:
            raise ValueError('Different datasets')
        if name!='astar':
            if manifest['method']!='llm' or manifest['prompt']!=name:
                raise ValueError('Prompt/directory mismatch')
            settings={k:manifest[k] for k in ['model','temperature','stop','max_tokens','case_timeout','source_sha256','packages','python']}
            if first_llm is not None and settings!=first_llm:
                raise ValueError('Different model/runtime/settings between LLM prompts')
            first_llm=settings
        ordered=[rows[i] for i in sorted(rows)]
        for r in ordered:
            a=astar[r['index']]
            if any(r[k]!=a[k] for k in ['map_id','pair_index','query']):
                raise ValueError('Paired case mismatch')
        ids=[r['map_id'] for r in ordered]
        count=len(set(ids))
        draws=np.random.default_rng(args.seed).integers(0,count,(args.bootstrap,count))
        valid=[int(r['status']=='valid') for r in ordered]
        summary={'attempted':len(rows),'valid':sum(valid),
            'invalid':sum(r['status']=='invalid' for r in ordered),
            'error':sum(r['status']=='error' for r in ordered),
            'valid_percent':100*sum(valid)/len(rows),
            'valid_percent_map_bootstrap_ci95':cluster_estimate(ids,valid,[1]*len(ids),draws),
            'parse_ok':sum(r.get('waypoint_audit',{}).get('parse_ok',False) for r in ordered) if name!='astar' else None,
            'cases_with_intermediate':sum(r.get('waypoint_audit',{}).get('intermediate_count',0)>0 for r in ordered) if name!='astar' else None,
            'ratios':{}}
        values_for_table=[]
        for field in ['operation','storage','length']:
            ratios=[]; logs=[]; weights=[]
            for r in ordered:
                a=astar[r['index']]
                usable=r['status']=='valid' and a['status']=='valid'
                x=r.get('result',{}).get(field,0);y=a.get('result',{}).get(field,0)
                usable=usable and x>0 and y>0
                ratio=x/y if usable else None
                weights.append(int(usable));logs.append(math.log(ratio) if usable else 0.)
                if usable:
                    ratios.append(ratio)
                if field=='operation':
                    paired_csv.append([name,r['index'],r['map_id'],r['pair_index'],a['status'],r['status'],
                        *[100*r['result'][f]/a['result'][f] if r['status']=='valid' and a['status']=='valid' and a['result'][f]>0 else None for f in ['operation','storage','length']]])
            gm=100*math.exp(sum(logs)/sum(weights)) if sum(weights) else None
            item={'n':len(ratios),'excluded':len(rows)-len(ratios),'geometric_mean_percent':gm,
                  'geometric_mean_percent_map_bootstrap_ci95':cluster_estimate(ids,logs,weights,draws,True),
                  'sample_sd_of_case_percent_ratios':float(np.std(np.array(ratios)*100,ddof=1)) if len(ratios)>1 else None,
                  'arithmetic_mean_percent':float(np.mean(ratios)*100) if ratios else None}
            summary['ratios'][field]=item
            values_for_table.extend([gm,item['sample_sd_of_case_percent_ratios'],item['geometric_mean_percent_map_bootstrap_ci95']])
        calls=[json.loads(p.read_text()) for p in (root/name/'api_calls').glob('*.json')]
        summary['api_usage']={'recorded_responses':len(calls),
            'prompt_tokens':sum(c.get('usage',{}).get('prompt_tokens',0) for c in calls),
            'completion_tokens':sum(c.get('usage',{}).get('completion_tokens',0) for c in calls),
            'missing_usage':sum(not c.get('usage') for c in calls)}
        report['methods'][name]=summary
        table.append([name,manifest['model'],len(rows),sum(valid),summary['valid_percent'],
                      summary['valid_percent_map_bootstrap_ci95'],*values_for_table])
    out=root/'summary'
    save(out/'statistics.json',report)
    with (out/'table1.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['method','model','n','valid','valid_percent','valid_map_bootstrap_ci95',
                         *[f'{metric}_{suffix}' for metric in ['operation','storage','length'] for suffix in ['gm_percent','case_sd_percent','gm_map_bootstrap_ci95']]])
        writer.writerows(table)
    with (out/'paired_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['condition','index','map_id','pair_index','astar_status','condition_status','operation_ratio_percent','storage_ratio_percent','length_ratio_percent'])
        writer.writerows(paired_csv)
    print(f'Saved statistics and CSVs to {out}')
    for name,s in report['methods'].items():
        print(name,'valid=',s['valid'],'ratios=',{k:v['geometric_mean_percent'] for k,v in s['ratios'].items()})


if __name__=='__main__':
    main()
