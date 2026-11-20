"""Explore switching LLM waypoints on expansion rather than neighbor discovery.

Uses the teammate's saved GPT-4o mini waypoints; no API calls. This is an
exploratory follow-up, not an untouched confirmation set.
"""

import argparse
import json
from pathlib import Path

from evaluate_gpt_v2 import _ratios
from official_replay import replay
from waypoint_search import valid_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--prompt", choices=("standard", "cot", "repe"), required=True)
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--summary-output", type=Path, required=True)
    args = ap.parse_args()
    rows = []
    for index in range(args.limit):
        source = json.loads((args.results_root / args.prompt / "cases" /
                             f"{index:04d}.json").read_text(encoding="utf-8"))
        row = {"index": index, "map_id": source["map_id"],
               "baseline_status": source["status"]}
        if source["status"] == "valid":
            query, points = source["query"], source["result"]["llm_output"]
            variants = {
                "original": replay(query, points),
                "expanded_original": replay(query, points, switch_mode="expanded"),
                "weighted_waypoint": replay(query, points, goal_weight=2,
                                            target_weight=0.5),
                "expanded_weighted": replay(query, points, goal_weight=2,
                                            target_weight=0.5,
                                            switch_mode="expanded"),
                "weighted_astar": replay(query, goal_weight=2),
            }
            for result in variants.values():
                result["path_valid"] = result["valid"] and valid_path(
                    query, result["path"])
                if not result["path_valid"]:
                    raise AssertionError(f"Invalid path at {args.prompt} {index}")
            row.update(variants)
        rows.append(row)
        if (index + 1) % 100 == 0:
            print(f"{args.prompt}: {index + 1}/{args.limit}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row) + "\n" for row in rows),
                           encoding="utf-8")
    valid = [row for row in rows if row["baseline_status"] == "valid"]
    pairs = (("expanded_over_original", "expanded_original", "original"),
             ("expanded_weighted_over_weighted_waypoint", "expanded_weighted",
              "weighted_waypoint"),
             ("expanded_weighted_over_weighted_astar", "expanded_weighted",
              "weighted_astar"))
    summary = {"prompt": args.prompt, "attempted": len(rows),
               "valid_source": len(valid), "comparisons": {}}
    for name, numerator, denominator in pairs:
        summary["comparisons"][name] = {
            metric: _ratios(valid, numerator, denominator, metric,
                            seed=20261121 + 10 * pairs.index((name, numerator,
                                                               denominator)) + i)
            for i, metric in enumerate(("operation", "storage", "length"))}
        summary["comparisons"][name]["operation_help_equal_hurt"] = {
            label: sum((row[numerator]["operation"] < row[denominator]["operation"]
                        if label == "help" else
                        row[numerator]["operation"] == row[denominator]["operation"]
                        if label == "equal" else
                        row[numerator]["operation"] > row[denominator]["operation"])
                       for row in valid)
            for label in ("help", "equal", "hurt")}
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps({name: {field: round(data[field]["geometric_mean"], 4)
                             for field in ("operation", "storage", "length")}
                      for name, data in summary["comparisons"].items()}, indent=2))


if __name__ == "__main__":
    main()
