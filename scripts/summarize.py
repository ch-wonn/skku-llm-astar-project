"""Summarize recorded paired cases without fabricating missing outcomes."""

import argparse
import json
import math
import statistics
from pathlib import Path


def describe(values):
    if not values:
        return {"n": 0}
    n = len(values)
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if n > 1 else None
    margin = 1.96 * sd / math.sqrt(n) if sd is not None else None
    return {"n": n, "mean": mean, "sample_sd": sd,
            "ci95_normal": [mean - margin, mean + margin] if margin is not None else None,
            "geometric_mean": math.exp(statistics.mean(math.log(value) for value in values))
            if all(value > 0 for value in values) else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        parser.error("No records in JSONL")
    ok = [row for row in rows if row.get("status") == "ok"]
    report = {"attempted": len(rows), "paired_success": len(ok),
              "successful_call_ratio_percent": 100 * len(ok) / len(rows)}
    for name, field in (("operation_ratio_percent", "operation"),
                        ("storage_ratio_percent", "storage"),
                        ("relative_path_length_percent", "length")):
        values = []
        for row in ok:
            denominator = row["astar"][field]
            if denominator > 0:
                values.append(100 * row["llm_astar"][field] / denominator)
        report[name] = describe(values)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
