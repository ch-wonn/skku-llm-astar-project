"""Evaluate the predeclared waypoint gate on saved model responses."""

import argparse
import json
import statistics
import time
from pathlib import Path

from compare_goal_weight import describe_ratios
from official_replay import replay
from selective_waypoint import gated_replay
from waypoint_search import valid_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waypoint_files", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
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
            row = {"map_id": key[0], "pair_index": key[1], "status": item["status"]}
            if item["status"] == "ok":
                query, waypoints = item["query"], item["waypoints"]
                for name, run in (
                    ("original", lambda: replay(query, waypoints)),
                    ("always_on", lambda: replay(query, waypoints,
                                                 goal_weight=2, target_weight=0.5)),
                    ("weighted_astar", lambda: replay(query, goal_weight=2)),
                    ("gate", lambda: gated_replay(query, waypoints)),
                ):
                    started = time.perf_counter()
                    output = run()
                    output["elapsed_seconds"] = time.perf_counter() - started
                    output["path_valid"] = (output["valid"]
                                            and valid_path(query, output["path"]))
                    row[name] = output
            rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    success = [row for row in rows if row["status"] == "ok"]
    names = ("original", "always_on", "weighted_astar", "gate")
    report = {
        "source_cases": len(rows),
        "failed_calls": len(rows) - len(success),
        "gate_active": sum(row["gate"]["gate_active"] for row in success),
        "valid_paths": {name: sum(row[name]["path_valid"] for row in success)
                        for name in names},
        "mean_elapsed_seconds": {name: statistics.mean(row[name]["elapsed_seconds"]
                                   for row in success) for name in names},
        "mean_gate_preprocess_seconds": statistics.mean(
            row["gate"]["preprocess_seconds"] for row in success),
        "ratios": {},
    }
    for label, numerator, denominator in (
        ("gate_over_weighted_astar", "gate", "weighted_astar"),
        ("gate_over_original", "gate", "original"),
        ("gate_over_always_on", "gate", "always_on"),
        ("always_on_over_weighted_astar", "always_on", "weighted_astar"),
    ):
        report["ratios"][label] = {
            field: describe_ratios(success, numerator, denominator, field)
            for field in ("operation", "storage", "length")
        }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(report, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
