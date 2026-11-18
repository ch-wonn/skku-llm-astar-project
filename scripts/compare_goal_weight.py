"""Compare ordinary A*, original LLM-A*, and fixed goal-weight candidate."""

import argparse
import json
import math
import statistics
from pathlib import Path

from official_replay import replay
from waypoint_search import valid_path


def describe_ratios(rows, numerator, denominator, field):
    ratios = [row[numerator][field] / row[denominator][field]
              for row in rows if row[numerator]["path_valid"]
              and row[denominator]["path_valid"]
              and row[denominator][field] > 0]
    if not ratios:
        return {"n": 0}
    logs = list(map(math.log, ratios))
    n = len(ratios)
    log_mean = statistics.mean(logs)
    sd = statistics.stdev(ratios) if n > 1 else None
    log_sd = statistics.stdev(logs) if n > 1 else None
    margin = 1.96 * log_sd / math.sqrt(n) if log_sd is not None else None
    return {"n": n, "geometric_mean": math.exp(log_mean),
            "arithmetic_mean": statistics.mean(ratios), "sample_sd": sd,
            "ci95_log_normal_approx":
                [math.exp(log_mean - margin), math.exp(log_mean + margin)]
                if margin is not None else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waypoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = [json.loads(line) for line in args.waypoints.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    rows = []
    failed_calls = 0
    seen = set()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for item in source:
            key = (item["map_id"], item["pair_index"])
            if key in seen:
                raise ValueError(f"Duplicate case {key}")
            seen.add(key)
            if item.get("status") != "ok":
                failed_calls += 1
                continue
            query, waypoints = item["query"], item["waypoints"]
            row = {"map_id": key[0], "pair_index": key[1],
                   "model": item["model"], "prompt": item["prompt"]}
            for name, output in (
                ("astar", replay(query)),
                ("original_llm_astar", replay(query, waypoints, goal_weight=1)),
                ("candidate", replay(query, waypoints, goal_weight=2)),
            ):
                output["path_valid"] = (output["valid"]
                                        and valid_path(query, output["path"]))
                row[name] = output
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {"source_records": len(source), "failed_model_calls": failed_calls,
              "paired_cases": len(rows), "path_valid_counts": {
                  name: sum(row[name]["path_valid"] for row in rows)
                  for name in ("astar", "original_llm_astar", "candidate")},
              "ratios": {}}
    for label, numerator, denominator in (
            ("original_over_astar", "original_llm_astar", "astar"),
            ("candidate_over_original", "candidate", "original_llm_astar"),
            ("candidate_over_astar", "candidate", "astar")):
        report["ratios"][label] = {
            field: describe_ratios(rows, numerator, denominator, field)
            for field in ("operation", "storage", "length")}
    print(json.dumps(report, indent=2))
    print(f"Saved {len(rows)} paired cases to {args.output}")


if __name__ == "__main__":
    main()
