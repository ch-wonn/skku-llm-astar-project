import argparse
import json
import os
import time
from copy import deepcopy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import openai
from llmastar.pather import AStar, LLMAStar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--method",
        choices=["astar", "llm"],
        required=True
    )
    args = parser.parse_args()

    query = {
        "start": [5, 5],
        "goal": [27, 15],
        "size": [51, 31],
        "horizontal_barriers": [
            [10, 0, 25],
            [15, 30, 50]
        ],
        "vertical_barriers": [[25, 10, 22]],
        "range_x": [0, 51],
        "range_y": [0, 31]
    }

    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    if args.method == "llm":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        openai.api_key = key
        algorithm = LLMAStar(llm="gpt", prompt="standard")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        algorithm = AStar()
        model = None

    started = time.perf_counter()
    result = algorithm.searching(
        query=deepcopy(query),
        filepath=str(output_dir / f"{args.method}.png")
    )
    elapsed = time.perf_counter() - started

    record = {
        "method": args.method,
        "model": model,
        "prompt": "standard" if model else None,
        "query": query,
        "elapsed_seconds_including_plot": elapsed,
        "result": result
    }

    output_file = output_dir / f"{args.method}.json"
    output_file.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()