"""Collect and cache Gemini waypoint suggestions for paired experiments.

Development model and prompt are deliberately explicit. This script is not a
claim of reproducing the paper's GPT-3.5/Llama3 Table 1 rows. Both the original
and improved search should consume the SAME saved responses.
"""

import argparse
import ast
import json
import os
import re
import runpy
import time
import urllib.error
import urllib.request
from pathlib import Path

from reproduce import load_cases


ROOT = Path(__file__).resolve().parents[1]
PROMPT_VERSION = "official-gpt-prompts@9414ed894d77"
PROMPTS = runpy.run_path(str(ROOT / "third_party" / "official_prompt.py"))["gpt_prompt"]


def local_key():
    """Read a private key without printing or putting it in a request URL."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def make_prompt(query, method):
    """Use the upstream GPT prompt text for the chosen Table 1 technique."""
    return PROMPTS[method].format(
        start=query["start"], goal=query["goal"],
        horizontal_barriers=query["horizontal_barriers"],
        vertical_barriers=query["vertical_barriers"],
    )


def parse_waypoints(text):
    matches = re.findall(r"\[\[.*?\]\]", text, flags=re.S)
    if not matches:
        raise ValueError("Response contains no waypoint list")
    points = ast.literal_eval(matches[-1])
    if not isinstance(points, list):
        raise ValueError("Waypoints must be a list")
    return points


def ask_gemini(key, model, prompt):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", model):
        raise ValueError("Invalid model name")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":generateContent")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1000},
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            parts = payload["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts), payload.get("usageMetadata", {})
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 503) or attempt == 3:
                raise RuntimeError(f"Gemini HTTP {exc.code}") from None
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("Unreachable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--prompt", choices=("standard", "cot", "repe"),
                        required=True, help="Paper's Few-Shot, CoT, or RePE prompt")
    parser.add_argument("--limit", type=int, default=20,
                        help="First N cases for a pilot; default 20")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip this many cases for a pilot")
    parser.add_argument("--all", action="store_true", help="Run all cases")
    parser.add_argument("--delay", type=float, default=4.0,
                        help="Seconds between API requests; adjust to your quota")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.offset < 0 or args.delay < 0:
        parser.error("--limit must be positive; --offset and --delay nonnegative")
    _, cases = load_cases(args.dataset)
    if args.all and args.offset:
        parser.error("--all requires --offset 0")
    selected = cases if args.all else cases[args.offset:args.offset + args.limit]
    if not selected:
        parser.error("No cases selected")
    print(f"Selected {len(selected)} cases; model={args.model}; "
          f"prompt={args.prompt}; source={PROMPT_VERSION}")
    if args.dry_run:
        print("Sample prompt:\n" + make_prompt(selected[0][2], args.prompt))
        return
    key = local_key()
    if not key:
        parser.error("Set GEMINI_API_KEY in the environment or an untracked .env file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if (row.get("model"), row.get("prompt_version"), row.get("prompt")) != (
                        args.model, PROMPT_VERSION, args.prompt):
                    parser.error("Existing output has a different model or prompt")
                done.add((row["map_id"], row["pair_index"]))
    with args.output.open("a", encoding="utf-8") as stream:
        for map_id, pair_index, query in selected:
            if (map_id, pair_index) in done:
                continue
            row = {"map_id": map_id, "pair_index": pair_index,
                   "model": args.model, "prompt_version": PROMPT_VERSION,
                   "prompt": args.prompt,
                   "status": "error", "query": query}
            started = time.monotonic()
            try:
                response, usage = ask_gemini(key, args.model,
                                             make_prompt(query, args.prompt))
                row["response"] = response
                row["usage"] = usage
                row["waypoints"] = parse_waypoints(response)
                row["status"] = "ok"
            except (ValueError, KeyError, IndexError, RuntimeError,
                    urllib.error.URLError, TimeoutError) as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["latency_seconds"] = round(time.monotonic() - started, 3)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"map={map_id} pair={pair_index}: {row['status']}")
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
