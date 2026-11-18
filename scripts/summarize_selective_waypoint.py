"""Pool saved selective-waypoint results; also report activated cases."""

import argparse
import json
import statistics
from pathlib import Path

from compare_goal_weight import describe_ratios


def summarize(rows):
    success = [row for row in rows if row["status"] == "ok"]
    active = [row for row in success if row["gate"]["gate_active"]]
    report = {"source_cases": len(rows), "failed_calls": len(rows) - len(success),
              "gate_active": len(active),
              "valid_paths": {name: sum(row[name]["path_valid"] for row in success)
                              for name in ("original", "always_on", "weighted_astar", "gate")},
              "mean_elapsed_seconds": {name: statistics.mean(
                  row[name]["elapsed_seconds"] for row in success)
                  for name in ("weighted_astar", "gate")},
              "mean_gate_preprocess_seconds": statistics.mean(
                  row["gate"]["preprocess_seconds"] for row in success),
              "gate_over_weighted_astar": {},
              "active_only_gate_over_weighted_astar": {}}
    for field in ("operation", "storage", "length"):
        report["gate_over_weighted_astar"][field] = describe_ratios(
            success, "gate", "weighted_astar", field)
        report["active_only_gate_over_weighted_astar"][field] = describe_ratios(
            active, "gate", "weighted_astar", field)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paired_files", type=Path, nargs="+")
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    groups = {}
    seen = set()
    for path in args.paired_files:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        for row in rows:
            key = (row["map_id"], row["pair_index"])
            if key in seen:
                raise ValueError(f"Duplicate case {key}")
            seen.add(key)
        groups[str(path)] = rows
    report = {name: summarize(rows) for name, rows in groups.items()}
    report["pooled"] = summarize([row for rows in groups.values() for row in rows])
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
