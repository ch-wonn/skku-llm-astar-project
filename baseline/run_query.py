#!/usr/bin/env python3
"""Single unseen query through the baseline searching(query, filepath) interface.
Writes the original return dictionary to --output; diagnostics are separate.
"""
import argparse
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from reproduction_support import AStar, AuditedLLMAStar
from run_reproduction import save


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--query',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--method',choices=['astar','llm'],default='llm')
    ap.add_argument('--prompt',choices=['standard','cot','repe'],default='standard')
    ap.add_argument('--max-tokens',type=int,default=1000)
    args=ap.parse_args()
    if args.max_tokens<1:
        ap.error('Invalid token limit')
    os.environ['LLM_MAX_OUTPUT_TOKENS']=str(args.max_tokens)
    q=json.loads(args.query.read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    alg=AStar() if args.method=='astar' else AuditedLLMAStar(llm='gpt',prompt=args.prompt)
    result=alg.searching(q,filepath=str(args.output.with_suffix('.png')))
    save(args.output,result)
    if hasattr(alg,'audit'):
        save(args.output.with_suffix('.audit.json'),alg.audit)


if __name__=='__main__':
    main()
