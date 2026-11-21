"""Explore a start-visible LLM waypoint gate on saved GPT responses.

The strict gate requires both legs to be straight-line clear; this variant
requires only the first leg. This is exploratory analysis on previously viewed
GPT data, not independent confirmation.
"""

import argparse
import json
from pathlib import Path

from evaluate_gpt_v2 import _ratios
from selective_waypoint import gated_replay
from waypoint_search import valid_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--base-results", type=Path, required=True)
    ap.add_argument("--prompt", choices=("standard", "cot", "repe"), required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--summary-output", type=Path, required=True)
    args = ap.parse_args()
    rows = []
    for line in args.base_results.read_text(encoding="utf-8").splitlines():
        base = json.loads(line)
        row = {"index": base["index"], "map_id": base["map_id"],
               "baseline_status": base["baseline_status"]}
        if row["baseline_status"] == "valid":
            source = json.loads((args.results_root / args.prompt / "cases" /
                                 f"{row['index']:04d}.json").read_text())
            query = source["query"]
            points = source["result"]["llm_output"]
            relaxed = gated_replay(query, points, require_goal_visible=False)
            relaxed["path_valid"] = relaxed["valid"] and valid_path(
                query, relaxed["path"])
            if not relaxed["path_valid"]:
                raise AssertionError(f"Invalid path at {row['index']}")
            row.update({"relaxed": relaxed, "strict": base["selective_gate"],
                        "astar": base["astar"],
                        "weighted_astar": base["weighted_astar"],
                        "original": base["original"]})
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row) + "\n" for row in rows),
                           encoding="utf-8")
    valid = [row for row in rows if row["baseline_status"] == "valid"]
    pairs = (("relaxed_over_strict", "relaxed", "strict"),
             ("relaxed_over_astar", "relaxed", "astar"),
             ("relaxed_over_weighted_astar", "relaxed", "weighted_astar"),
             ("relaxed_over_original", "relaxed", "original"))
    summary = {"prompt": args.prompt, "valid_source": len(valid),
               "strict_active": sum(row["strict"]["gate_active"] for row in valid),
               "relaxed_active": sum(row["relaxed"]["gate_active"] for row in valid),
               "comparisons": {}}
    for j, (name, numerator, denominator) in enumerate(pairs):
        summary["comparisons"][name] = {
            field: _ratios(valid, numerator, denominator, field,
                           seed=20261121 + 10 * j + k)
            for k, field in enumerate(("operation", "storage", "length"))}
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps({"valid_source": len(valid),
                      "strict_active": summary["strict_active"],
                      "relaxed_active": summary["relaxed_active"],
                      "ratios": {name: {field: round(data[field]["geometric_mean"], 4)
                                        for field in ("operation", "storage", "length")}
                                 for name, data in summary["comparisons"].items()}},
                     indent=2))


if __name__ == "__main__":
    main()
