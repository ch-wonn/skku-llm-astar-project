"""Analyze a paired pilot that asks for different waypoint counts.

This is a prompt ablation on an offline search prototype. It is not a
paper-comparable Table 1 result.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

from waypoint_search import Grid, clean_waypoints, search, valid_path


CONDITIONS = ("control", "1", "3", "5")


def geometric_mean(values):
    return math.exp(statistics.mean(map(math.log, values))) if values else None


def mean(values):
    return statistics.mean(values) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {}
    for condition in CONDITIONS:
        path = args.input_dir / f"count_{condition}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        sources[condition] = {(r["map_id"], r["pair_index"]): r for r in rows}
    common = set.intersection(*(set(source) for source in sources.values()))
    if not common:
        parser.error("No cases shared by all four conditions")
    records = []
    for case in sorted(common):
        items = {name: source[case] for name, source in sources.items()}
        if any(item["status"] != "ok" for item in items.values()):
            continue
        query = items["control"]["query"]
        if any(item["query"] != query for item in items.values()):
            raise ValueError(f"Mismatched query at {case}")
        start, goal = tuple(query["start"]), tuple(query["goal"])
        grid = Grid(query)
        astar = search(query, [start, goal], alpha=0)
        if not astar["valid"] or not valid_path(query, astar["path"]):
            raise AssertionError(f"A* path invalid at {case}")
        record = {"map_id": case[0], "pair_index": case[1], "astar": astar}
        for name, item in items.items():
            raw = item["waypoints"]
            cleaned = clean_waypoints(grid, start, goal, raw)
            result = search(query, raw, alpha=1, switch_mode="neighbor")
            if not result["valid"] or not valid_path(query, result["path"]):
                raise AssertionError(f"{name} path invalid at {case}")
            record[name] = {"requested": item.get("requested_intermediates"),
                            "raw_count": len(raw),
                            "valid_intermediate_count": len(cleaned) - 2,
                            "exact_request_met": (name == "control" or (
                                len(raw) == int(name) + 2 and raw[0] == query["start"]
                                and raw[-1] == query["goal"])),
                            "latency_seconds": item["latency_seconds"],
                            "search": result}
        records.append(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    report = {"common_cases": len(common), "complete_cases": len(records),
              "conditions": {}}
    for name in CONDITIONS:
        entries = [r[name] for r in records]
        detail = {"requested_intermediates": None if name == "control" else int(name),
                  "exact_request_met": sum(e["exact_request_met"] for e in entries),
                  "mean_valid_intermediates": mean([e["valid_intermediate_count"] for e in entries]),
                  "mean_latency_seconds": mean([e["latency_seconds"] for e in entries])}
        for field in ("operation", "storage", "length"):
            detail[field + "_ratio_to_astar_geomean"] = geometric_mean([
                r[name]["search"][field] / r["astar"][field]
                for r in records if r["astar"][field] > 0])
            detail[field + "_ratio_to_control_geomean"] = geometric_mean([
                r[name]["search"][field] / r["control"]["search"][field]
                for r in records if r["control"]["search"][field] > 0])
        report["conditions"][name] = detail
    print(json.dumps(report, indent=2))
    print(f"Saved {len(records)} paired cases to {args.output}")


if __name__ == "__main__":
    main()
