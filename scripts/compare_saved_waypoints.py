"""Replay identical saved LLM waypoints through two search variants.

The current engine is an offline prototype, so these results are paired
development evidence, not paper-comparable Table 1 numbers.
"""

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

from waypoint_search import search, valid_path


def ratio_stats(rows, field):
    by_map = defaultdict(list)
    for row in rows:
        a, b = row["control"], row["candidate"]
        if a["valid"] and b["valid"] and a[field] and b[field]:
            by_map[row["map_id"]].append(math.log(b[field] / a[field]))
    logs = [v for values in by_map.values() for v in values]
    if not logs:
        return {"n": 0}
    ratios = list(map(math.exp, logs))
    output = {"n": len(logs), "geometric_mean": math.exp(statistics.mean(logs)),
              "arithmetic_mean": statistics.mean(ratios),
              "sample_sd": statistics.stdev(ratios) if len(ratios) > 1 else None}
    # Map-cluster bootstrap reflects that 10 pairs on one map are related.
    if len(by_map) >= 10:
        rng = random.Random(3011)
        groups = list(by_map.values())
        estimates = []
        for _ in range(2000):
            sample = [v for _ in groups for v in rng.choice(groups)]
            estimates.append(math.exp(statistics.mean(sample)))
        estimates.sort()
        output["map_cluster_bootstrap_ci95"] = [estimates[49], estimates[1949]]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waypoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--control-alpha", type=float, default=1)
    parser.add_argument("--candidate-alpha", type=float, default=1)
    parser.add_argument("--control-switch", choices=("neighbor", "expanded"),
                        default="neighbor")
    parser.add_argument("--candidate-switch", choices=("neighbor", "expanded"),
                        default="expanded")
    args = parser.parse_args()
    source = [json.loads(line) for line in args.waypoints.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    rows = []
    source_failures = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for item in source:
            if item.get("status") != "ok":
                source_failures += 1
                continue
            query, waypoints = item["query"], item["waypoints"]
            control = search(query, waypoints, args.control_alpha, args.control_switch)
            candidate = search(query, waypoints, args.candidate_alpha, args.candidate_switch)
            if control["valid"] and not valid_path(query, control["path"]):
                raise AssertionError("Control path failed collision validation")
            if candidate["valid"] and not valid_path(query, candidate["path"]):
                raise AssertionError("Candidate path failed collision validation")
            row = {"map_id": item["map_id"], "pair_index": item["pair_index"],
                   "model": item["model"], "prompt_version": item["prompt_version"],
                   "waypoints": waypoints, "control": control,
                   "candidate": candidate}
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {"source_records": len(source), "source_failures": source_failures,
              "paired_cases": len(rows),
              "control_valid": sum(row["control"]["valid"] for row in rows),
              "candidate_valid": sum(row["candidate"]["valid"] for row in rows),
              "control": {"alpha": args.control_alpha, "switch": args.control_switch},
              "candidate": {"alpha": args.candidate_alpha, "switch": args.candidate_switch},
              "ratio_candidate_over_control": {
                  field: ratio_stats(rows, field)
                  for field in ("operation", "storage", "length")}}
    print(json.dumps(report, indent=2))
    print(f"Saved paired rows to {args.output}")


if __name__ == "__main__":
    main()
