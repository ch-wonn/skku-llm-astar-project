"""Summarize saved, paired goal-weight experiments without API calls."""

import argparse
import json
from pathlib import Path

from compare_goal_weight import describe_ratios


def summarize(rows):
    names = ("astar", "original_llm_astar", "candidate")
    ratios = {}
    for label, numerator, denominator in (
        ("original_over_astar", "original_llm_astar", "astar"),
        ("candidate_over_original", "candidate", "original_llm_astar"),
        ("candidate_over_astar", "candidate", "astar"),
    ):
        ratios[label] = {
            field: describe_ratios(rows, numerator, denominator, field)
            for field in ("operation", "storage", "length")
        }
    delta = {}
    for field in ("operation", "storage", "length"):
        values = [row["candidate"][field] - row["original_llm_astar"][field]
                  for row in rows]
        delta[field] = {
            "better": sum(value < -1e-9 for value in values),
            "equal": sum(abs(value) <= 1e-9 for value in values),
            "worse": sum(value > 1e-9 for value in values),
        }
    return {
        "cases": len(rows),
        "path_valid": {name: sum(row[name]["path_valid"] for row in rows)
                       for name in names},
        "ratios": ratios,
        "candidate_vs_original_case_counts": delta,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paired", type=Path, nargs="+")
    args = parser.parse_args()
    groups = []
    seen = set()
    for path in args.paired:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        for row in rows:
            key = (row["map_id"], row["pair_index"])
            if key in seen:
                raise ValueError(f"Duplicate case {key}")
            seen.add(key)
        groups.append((str(path), rows))
    report = {name: summarize(rows) for name, rows in groups}
    report["pooled"] = summarize([row for _, rows in groups for row in rows])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
