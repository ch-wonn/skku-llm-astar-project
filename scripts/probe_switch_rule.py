"""Reproducible, model-free probe of the waypoint-switch rule.

This is a diagnostic experiment, not a Table 1 or LLM-A* result. It uses a
deterministic midpoint as a proxy waypoint so both switch rules see the same
input. Results should not be presented as evidence of LLM performance.
"""

import argparse
import copy
import json
import math
import statistics
from pathlib import Path

from reproduce import load_cases
from waypoint_search import Grid, search, valid_path


def proxy_waypoints(query):
    """Choose the free grid point closest to the start-goal midpoint."""
    grid = Grid(query)
    start, goal = query["start"], query["goal"]
    midpoint = ((start[0] + goal[0]) / 2, (start[1] + goal[1]) / 2)
    choices = ((x, y) for x in range(grid.xlo + 1, grid.xmax)
               for y in range(grid.ylo + 1, grid.ymax))
    choices = (p for p in choices if p != tuple(start) and p != tuple(goal)
               and grid.free_point(p))
    best = min(choices, key=lambda p: (math.dist(p, midpoint), p), default=None)
    return [start, best, goal] if best is not None else [start, goal]


def summary(rows):
    paired = [r for r in rows if r["neighbor"]["valid"] and r["expanded"]["valid"]]
    report = {"attempted": len(rows), "paired_valid": len(paired),
              "neighbor_valid": sum(r["neighbor"]["valid"] for r in rows),
              "expanded_valid": sum(r["expanded"]["valid"] for r in rows)}
    for field in ("operation", "storage", "length"):
        values = [r["expanded"][field] / r["neighbor"][field]
                  for r in paired if r["neighbor"][field] > 0]
        report[field + "_ratio_expanded_over_neighbor"] = {
            "n": len(values),
            "geometric_mean": math.exp(statistics.mean(map(math.log, values)))
            if values and all(v > 0 for v in values) else None,
            "arithmetic_mean": statistics.mean(values) if values else None,
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
        }
    report["changed_operation_count"] = sum(
        r["expanded"]["operation"] != r["neighbor"]["operation"] for r in paired)
    report["changed_length_count"] = sum(
        not math.isclose(r["expanded"]["length"], r["neighbor"]["length"])
        for r in paired)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    _, cases = load_cases(args.dataset)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        cases = cases[:args.limit]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with args.output.open("w", encoding="utf-8") as stream:
        for map_id, pair_index, query in cases:
            waypoints = proxy_waypoints(query)
            row = {"map_id": map_id, "pair_index": pair_index,
                   "waypoints": waypoints}
            for mode in ("neighbor", "expanded"):
                outcome = search(copy.deepcopy(query), waypoints,
                                 alpha=1, switch_mode=mode)
                if outcome["valid"] and not valid_path(query, outcome["path"]):
                    raise AssertionError(f"Invalid {mode} path: {map_id}/{pair_index}")
                row[mode] = outcome
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary(rows), indent=2))
    print(f"Wrote {len(rows)} paired cases to {args.output}")


if __name__ == "__main__":
    main()
