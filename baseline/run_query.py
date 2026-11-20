#!/usr/bin/env python3
"""Single unseen query through the baseline searching(query, filepath) interface.
Writes the original return dictionary to --output; diagnostics are separate.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from reproduction_support import AStar, AuditedLLMAStar, validate_path
from improved_search import (ImprovedLLMAStar, StartVisibleWaypointLLMAStar,
                             WeightedWaypointLLMAStar)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--query',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--method',choices=['astar','llm','weighted_waypoint',
                                        'selective_waypoint','start_visible_waypoint',
                                        'improved'],default='llm')
    ap.add_argument('--prompt',choices=['standard','cot','repe'],default='standard')
    ap.add_argument('--max-tokens',type=int,default=1000)
    args=ap.parse_args()
    if args.max_tokens<1:
        ap.error('Invalid token limit')
    os.environ['LLM_MAX_OUTPUT_TOKENS']=str(args.max_tokens)
    q=json.loads(args.query.read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.method == 'astar':
        alg = AStar()
    elif args.method == 'llm':
        alg = AuditedLLMAStar(llm='gpt', prompt=args.prompt)
    elif args.method == 'weighted_waypoint':
        alg = WeightedWaypointLLMAStar(llm='gpt', prompt=args.prompt)
    elif args.method == 'start_visible_waypoint':
        alg = StartVisibleWaypointLLMAStar(llm='gpt', prompt=args.prompt)
    else:
        alg = ImprovedLLMAStar(llm='gpt', prompt=args.prompt)
    original_query = copy.deepcopy(q)
    result=alg.searching(q,filepath=str(args.output.with_suffix('.png')))
    save(args.output,result)
    if args.method in ('weighted_waypoint', 'selective_waypoint',
                       'start_visible_waypoint', 'improved'):
        path = alg.extract_path(alg.PARENT)
        valid, reason, normalized = validate_path(path, original_query, result)
        audit = {
            'path_valid': valid, 'invalid_reason': reason, 'path': normalized,
            'source_waypoints': getattr(alg, 'source_waypoints', alg.target_list),
        }
        if isinstance(alg, ImprovedLLMAStar):
            audit.update({
                'selected_waypoint': alg.selected_waypoint,
                'eligible_waypoints': alg.eligible_waypoints,
                'gate_active': alg.selected_waypoint is not None,
            })
        save(args.output.with_suffix('.audit.json'), audit)
        if not valid:
            raise RuntimeError(f'Improved path validation failed: {reason}')
    elif hasattr(alg,'audit'):
        save(args.output.with_suffix('.audit.json'),alg.audit)


if __name__=='__main__':
    main()
