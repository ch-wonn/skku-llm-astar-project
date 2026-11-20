"""Audit whether the archived GPT baseline actually used LLM waypoints."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = args.baseline_results
    calls = [json.loads(path.read_text(encoding="utf-8"))
             for path in (folder / "api_calls").glob("*.json")]
    cases = [json.loads((folder / "cases" / f"{i:04d}_llm.json").read_text(
        encoding="utf-8")) for i in range(1000)]
    report = {
        "model_requested": Counter(c.get("model_requested") for c in calls),
        "model_returned": Counter(c.get("model_returned") for c in calls),
        "recorded_api_responses": len(calls),
        "responses_with_nested_waypoint_list": sum(bool(re.search(
            r"\[\[.*?\]\]", c.get("response_text", ""), re.S)) for c in calls),
        "responses_with_generated_path_marker": sum(
            "Generated Path" in c.get("response_text", "") for c in calls),
        "response_finish_reasons": Counter(c.get("finish_reason") for c in calls),
        "valid_case_records": sum(c["status"] == "valid" for c in cases),
        "intermediate_waypoints_per_case": Counter(max(
            0, len(c["result"]["llm_output"]) - 2) for c in cases),
        "start_goal_only_cases": sum(
            c["result"]["llm_output"] == [c["query"]["start"], c["query"]["goal"]]
            for c in cases),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
