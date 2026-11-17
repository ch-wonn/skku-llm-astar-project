"""Run the official A*/LLM-A* pair on each public dataset case."""

import argparse
import copy
import json
import os
from pathlib import Path


REQUIRED = {"range_x", "range_y", "horizontal_barriers", "vertical_barriers", "start_goal"}
UPSTREAM_COMMIT = "9414ed894d774f71c36e8c0afd0e20e6033b95b1"


def load_cases(path):
    maps = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(maps, list) or not maps:
        raise ValueError("Dataset must be a nonempty list of maps")
    cases = []
    for map_index, item in enumerate(maps):
        missing = REQUIRED - item.keys()
        if missing:
            raise ValueError(f"Map {map_index} missing {sorted(missing)}")
        if not isinstance(item["start_goal"], list):
            raise ValueError(f"Map {map_index} has invalid start_goal")
        for pair_index, pair in enumerate(item["start_goal"]):
            if not isinstance(pair, list) or len(pair) < 2:
                raise ValueError(f"Map {map_index}, pair {pair_index} is invalid")
            query = {key: copy.deepcopy(item[key]) for key in REQUIRED - {"start_goal"}}
            query["start"], query["goal"] = pair[:2]
            cases.append((item.get("id", map_index), pair_index, query))
    return len(maps), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--prompt", choices=("standard", "cot", "repe"), default="standard")
    parser.add_argument("--output", type=Path, default=Path("results/baseline_standard.jsonl"))
    parser.add_argument("--limit", type=int, help="Exploratory run only; omit for full dataset")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    map_count, cases = load_cases(args.dataset)
    print(f"Validated {map_count} maps and {len(cases)} start/goal cases")
    if args.validate_only:
        return
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY must be set for the original GPT baseline")

    import matplotlib
    matplotlib.use("Agg")
    from llmastar.pather import AStar, LLMAStar

    args.output.parent.mkdir(parents=True, exist_ok=True)
    plot_dir = args.output.parent / "plots"
    plot_dir.mkdir(exist_ok=True)
    selected = cases[:args.limit] if args.limit else cases
    with args.output.open("w", encoding="utf-8") as stream:
        for map_id, pair_index, query in selected:
            row = {"map_id": map_id, "pair_index": pair_index, "query": query,
                   "prompt": args.prompt, "llm": "gpt-3.5-turbo-instruct",
                   "upstream_commit": UPSTREAM_COMMIT, "status": "error"}
            stem = f"map_{map_id}_pair_{pair_index}"
            try:
                row["astar"] = AStar().searching(copy.deepcopy(query),
                    filepath=str(plot_dir / f"{stem}_astar.png"))
                row["llm_astar"] = LLMAStar(llm="gpt", prompt=args.prompt).searching(
                    copy.deepcopy(query), filepath=str(plot_dir / f"{stem}_llm_astar.png"))
                row["status"] = "ok"
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{stem}: {row['status']}")
    print(f"Wrote {len(selected)} records to {args.output}")


if __name__ == "__main__":
    main()
