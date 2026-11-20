"""Replay teammate's corrected GPT-4o mini baseline with improvement rules.

Requires the completed baseline/experiment_results/reproduction_v2 directory
from branch baseline/jooha-reproduction-v2. Makes no API calls.
"""

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

from official_replay import replay
from selective_waypoint import gated_replay
from waypoint_search import valid_path


METHODS = ("astar", "original", "goal_2", "goal_2_target_half",
           "weighted_astar", "selective_gate")
COMPARISONS = (
    ("original_over_astar", "original", "astar"),
    ("goal_2_over_original", "goal_2", "original"),
    ("goal_2_target_half_over_original", "goal_2_target_half", "original"),
    ("goal_2_over_weighted_astar", "goal_2", "weighted_astar"),
    ("goal_2_target_half_over_weighted_astar", "goal_2_target_half", "weighted_astar"),
    ("selective_gate_over_weighted_astar", "selective_gate", "weighted_astar"),
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _ratios(rows, numerator, denominator, field, *, seed):
    by_map = defaultdict(list)
    ratios = []
    for row in rows:
        a, b = row[numerator], row[denominator]
        if a["path_valid"] and b["path_valid"] and b[field] > 0:
            ratio = a[field] / b[field]
            if ratio <= 0:
                raise ValueError(f"Nonpositive {field} ratio")
            ratios.append(ratio)
            by_map[row["map_id"]].append(math.log(ratio))
    if not ratios:
        return {"n": 0}
    gm = math.exp(statistics.mean(map(math.log, ratios)))
    maps = sorted(by_map, key=str)
    rng = random.Random(seed)
    boot = []
    for _ in range(5000):
        sampled = [rng.choice(maps) for _ in maps]
        values = [log_ratio for map_id in sampled
                  for log_ratio in by_map[map_id]]
        boot.append(math.exp(statistics.mean(values)))
    boot.sort()
    return {"n": len(ratios), "geometric_mean": gm,
            "arithmetic_mean": statistics.mean(ratios),
            "sample_sd": statistics.stdev(ratios) if len(ratios) > 1 else None,
            "map_bootstrap_ci95": [boot[124], boot[4874]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--prompt", choices=("standard", "cot", "repe"),
                        required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be 1..1000")
    root = args.results_root
    manifest = _load(root / args.prompt / "manifest.json")
    if (manifest["model"] != "gpt-4o-mini" or manifest["prompt"] != args.prompt
            or manifest["expected"] != 1000 or manifest["stop"] is not None):
        raise ValueError("Unexpected GPT reproduction manifest")
    rows = []
    for index in range(args.limit):
        a = _load(root / "astar" / "cases" / f"{index:04d}.json")
        l = _load(root / args.prompt / "cases" / f"{index:04d}.json")
        if (a["index"] != index or l["index"] != index
                or a["query"] != l["query"] or a["map_id"] != l["map_id"]
                or a["pair_index"] != l["pair_index"] or a["status"] != "valid"):
            raise ValueError(f"Invalid paired case {index}")
        row = {"index": index, "map_id": a["map_id"],
               "pair_index": a["pair_index"], "prompt": args.prompt,
               "baseline_status": l["status"],
               "baseline_error_type": l.get("error_type")}
        if l["status"] == "valid":
            query, waypoints = a["query"], l["result"]["llm_output"]
            outputs = {
                "astar": replay(query),
                "original": replay(query, waypoints),
                "goal_2": replay(query, waypoints, goal_weight=2),
                "goal_2_target_half": replay(query, waypoints,
                                             goal_weight=2, target_weight=0.5),
                "weighted_astar": replay(query, goal_weight=2),
                "selective_gate": gated_replay(query, waypoints),
            }
            for name, result in outputs.items():
                result["path_valid"] = (result["valid"]
                                        and valid_path(query, result["path"]))
                if not result["path_valid"]:
                    raise AssertionError(f"Invalid replay path: {index} {name}")
                row[name] = result
            row["recorded_metric_match"] = {}
            row["recorded_metric_delta"] = {}
            for name, recorded in (("astar", a), ("original", l)):
                row["recorded_metric_match"][name] = True
                row["recorded_metric_delta"][name] = {}
                for field in ("operation", "storage", "length"):
                    actual, expected = row[name][field], recorded["result"][field]
                    matches = math.isclose(actual, expected,
                                           rel_tol=1e-12, abs_tol=1e-12)
                    row["recorded_metric_match"][name] &= matches
                    row["recorded_metric_delta"][name][field] = actual - expected
                row["recorded_path_match"] = {
                    name: [tuple(point) for point in result["path"]]
                    == [tuple(point) for point in recorded["path"]]
                    for name, result, recorded in (("astar", row["astar"], a),
                                                   ("original", row["original"], l))}
        rows.append(row)
        if (index + 1) % 100 == 0:
            print(f"Checked {index + 1}/{args.limit}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    valid = [row for row in rows if row["baseline_status"] == "valid"]
    report = {"source_branch": "baseline/jooha-reproduction-v2",
              "source_commit": "1aba737500008778868dde1896ea3c8514c84ff5",
              "model": "gpt-4o-mini", "prompt": args.prompt,
              "attempted": len(rows), "baseline_valid": len(valid),
              "baseline_error": len(rows) - len(valid),
              "intermediate_waypoint_cases": sum(
                  len(row["original"]["llm_output"]) > 2 for row in valid),
              "gate_active": sum(row["selective_gate"]["gate_active"]
                                 for row in valid),
              "recorded_metric_matches": {
                  name: sum(row["recorded_metric_match"][name] for row in valid)
                  for name in ("astar", "original")},
              "recorded_metric_mismatch_examples": {
                  name: [row["index"] for row in valid
                         if not row["recorded_metric_match"][name]][:20]
                  for name in ("astar", "original")},
              "recorded_path_matches": {
                  name: sum(row["recorded_path_match"][name] for row in valid)
                  for name in ("astar", "original")},
              "valid_paths": {name: sum(row[name]["path_valid"] for row in valid)
                              for name in METHODS},
              "ratios": {}}
    for label, numerator, denominator in COMPARISONS:
        report["ratios"][label] = {
            field: _ratios(valid, numerator, denominator, field,
                           seed=2026 + 100 * COMPARISONS.index((label, numerator, denominator))
                           + ("operation", "storage", "length").index(field))
            for field in ("operation", "storage", "length")}
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(report, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "prompt", "attempted", "baseline_valid", "baseline_error",
        "intermediate_waypoint_cases", "gate_active",
        "recorded_metric_matches", "recorded_metric_mismatch_examples",
        "recorded_path_matches")}, indent=2))
    print(f"Saved {args.output} and {args.summary_output}")


if __name__ == "__main__":
    main()
