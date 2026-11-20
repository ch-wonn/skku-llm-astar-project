"""Replay saved GPT-4o mini LLM-A* waypoints and compare search variants.

Reads the teammate's 1,000-case baseline artifacts. Makes no API calls.
Fails if the replay does not reproduce the recorded original A*/LLM-A*
operation, storage, or path length for every case.
"""

import argparse
import json
import math
from pathlib import Path

from compare_goal_weight import describe_ratios
from official_replay import replay
from waypoint_search import valid_path


VARIANTS = ("astar", "original", "goal_2", "goal_2_target_half",
            "weighted_astar")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-results", type=Path, required=True,
                        help="Baseline experiment_results/gpt4omini_standard")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    source = args.baseline_results / "cases"
    cases_with_intermediate_waypoints = sum(
        len(json.loads((source / f"{index:04d}_llm.json").read_text(
            encoding="utf-8"))["result"]["llm_output"]) > 2
        for index in range(1000))
    if cases_with_intermediate_waypoints == 0:
        raise ValueError("All 1,000 LLM outputs contain only start and goal; "
                         "the archived run did not use model waypoints")
    rows = []
    for index in range(1000):
        a_path = source / f"{index:04d}_astar.json"
        l_path = source / f"{index:04d}_llm.json"
        a = json.loads(a_path.read_text(encoding="utf-8"))
        l = json.loads(l_path.read_text(encoding="utf-8"))
        if (a["index"] != index or l["index"] != index
                or a["query"] != l["query"]
                or a["map_id"] != l["map_id"]
                or a["pair_index"] != l["pair_index"]
                or a["status"] != "valid" or l["status"] != "valid"):
            raise ValueError(f"Invalid paired baseline case {index}")
        query = a["query"]
        waypoints = l["result"]["llm_output"]
        row = {"index": index, "map_id": a["map_id"],
               "pair_index": a["pair_index"], "model": "gpt-4o-mini",
               "prompt": "standard"}
        for name, output in (
            ("astar", replay(query)),
            ("original", replay(query, waypoints)),
            ("goal_2", replay(query, waypoints, goal_weight=2)),
            ("goal_2_target_half", replay(query, waypoints,
                                          goal_weight=2, target_weight=0.5)),
            ("weighted_astar", replay(query, goal_weight=2)),
        ):
            output["path_valid"] = output["valid"] and valid_path(
                query, output["path"])
            row[name] = output
        for name, official in (("astar", a), ("original", l)):
            for field in ("operation", "storage", "length"):
                measured = row[name][field]
                expected = official["result"][field]
                if not math.isclose(measured, expected,
                                    rel_tol=1e-12, abs_tol=1e-12):
                    raise AssertionError(f"case {index} {name} {field}: "
                                         f"replay={measured} baseline={expected}")
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {
        "source": str(args.baseline_results),
        "model": "gpt-4o-mini", "prompt": "standard",
        "cases": len(rows), "baseline_replay_exact_matches": len(rows),
        "cases_with_intermediate_waypoints": cases_with_intermediate_waypoints,
        "valid_paths": {name: sum(row[name]["path_valid"] for row in rows)
                        for name in VARIANTS},
        "ratios": {},
    }
    for label, numerator, denominator in (
        ("original_over_astar", "original", "astar"),
        ("goal_2_over_original", "goal_2", "original"),
        ("goal_2_target_half_over_original", "goal_2_target_half", "original"),
        ("goal_2_target_half_over_weighted_astar", "goal_2_target_half", "weighted_astar"),
        ("weighted_astar_over_original", "weighted_astar", "original"),
    ):
        report["ratios"][label] = {
            field: describe_ratios(rows, numerator, denominator, field)
            for field in ("operation", "storage", "length")
        }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(report, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
