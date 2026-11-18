"""Post-hoc heuristic ablation on previously saved Gemini waypoint responses.

This is explanatory analysis on cases already used to evaluate goal weight 2;
do not treat a best variant selected here as a new held-out result.
"""

import argparse
import json
from pathlib import Path

from compare_goal_weight import describe_ratios
from official_replay import replay
from waypoint_search import valid_path


VARIANTS = {
    "original": (1.0, 1.0),
    "goal_1_5": (1.5, 1.0),
    "current_goal_2": (2.0, 1.0),
    "goal_3": (3.0, 1.0),
    "target_half": (2.0, 0.5),
    "no_waypoint": (2.0, 0.0),
    "weighted_astar": (2.0, 0.0),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waypoint_files", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    seen = set()
    rows = []
    for path in args.waypoint_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            key = (item["map_id"], item["pair_index"])
            if key in seen:
                raise ValueError(f"Duplicate case {key}")
            seen.add(key)
            row = {"map_id": key[0], "pair_index": key[1],
                   "status": item["status"]}
            if item["status"] == "ok":
                for name, (goal_weight, target_weight) in VARIANTS.items():
                    result = (replay(item["query"], goal_weight=goal_weight)
                              if name == "weighted_astar" else
                              replay(item["query"], item["waypoints"],
                                     goal_weight=goal_weight,
                                     target_weight=target_weight))
                    result["path_valid"] = result["valid"] and valid_path(
                        item["query"], result["path"])
                    row[name] = result
            rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    success = [row for row in rows if row["status"] == "ok"]
    report = {"source_cases": len(rows), "failed_calls": len(rows) - len(success),
              "variants": {}}
    for name, (goal_weight, target_weight) in VARIANTS.items():
        report["variants"][name] = {
            "goal_weight": goal_weight,
            "target_weight": target_weight,
            "valid_paths": sum(row[name]["path_valid"] for row in success),
            "over_original": {
                field: describe_ratios(success, name, "original", field)
                for field in ("operation", "storage", "length")
            },
        }
    report["focused_comparisons"] = {}
    for candidate, control in (
        ("target_half", "current_goal_2"),
        ("target_half", "no_waypoint"),
        ("target_half", "weighted_astar"),
        ("current_goal_2", "weighted_astar"),
        ("goal_3", "current_goal_2"),
    ):
        report["focused_comparisons"][f"{candidate}_over_{control}"] = {
            field: describe_ratios(success, candidate, control, field)
            for field in ("operation", "storage", "length")
        }
    summary = json.dumps(report, indent=2)
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"Saved {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
