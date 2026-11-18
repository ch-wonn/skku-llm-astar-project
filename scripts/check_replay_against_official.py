"""Differential check of the offline replay against the pinned official code.

Loads the official search classes with inert model/plotting adapters, then
injects the same saved waypoints. This checks search logic and metric counts
without requiring API calls, Torch, Transformers, or Matplotlib.
"""

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import math
import sys
import types
from pathlib import Path

from official_replay import replay
from waypoint_search import _intersects


def _package(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def official_classes(source):
    for name in ("llmastar", "llmastar.env", "llmastar.env.search",
                 "llmastar.pather", "llmastar.pather.a_star",
                 "llmastar.pather.llm_a_star"):
        _package(name)
    env_module = _load("llmastar.env.search.env",
                       source / "llmastar/env/search/env.py")
    plotting = types.ModuleType("llmastar.env.search.plotting")

    class Plotting:
        def __init__(self, *args):
            pass

        def animation(self, *args):
            pass

    plotting.Plotting = Plotting
    sys.modules[plotting.__name__] = plotting
    sys.modules["llmastar.env.search"].env = env_module
    sys.modules["llmastar.env.search"].plotting = plotting
    utils = types.ModuleType("llmastar.utils")
    utils.is_lines_collision = lambda a, b: _intersects(*a, *b)
    utils.list_parse = lambda text: json.loads(text)
    sys.modules[utils.__name__] = utils
    model = types.ModuleType("llmastar.model")

    class DummyModel:
        def __init__(self, *args, **kwargs):
            pass

    model.ChatGPT = model.Llama3 = DummyModel
    sys.modules[model.__name__] = model
    _load("llmastar.pather.llm_a_star.prompt",
          source / "llmastar/pather/llm_a_star/prompt.py")
    astar = _load("llmastar.pather.a_star.a_star",
                  source / "llmastar/pather/a_star/a_star.py").AStar
    llmastar = _load("llmastar.pather.llm_a_star.llm_a_star",
                     source / "llmastar/pather/llm_a_star/llm_a_star.py").LLMAStar
    return astar, llmastar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-source", type=Path, required=True)
    parser.add_argument("--waypoints", type=Path, required=True)
    args = parser.parse_args()
    official_astar, official_llmastar = official_classes(args.official_source)
    rows = [json.loads(line) for line in args.waypoints.read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line).get("status") == "ok"]
    checked = 0
    for row in rows:
        query, waypoints = row["query"], row["waypoints"]
        instance = official_llmastar(llm="gpt", prompt="standard")

        def fixed_waypoints():
            instance.target_list = instance._filter_valid_nodes(waypoints)
            if not instance.target_list or instance.target_list[0] != instance.s_start:
                instance.target_list.insert(0, instance.s_start)
            if instance.target_list[-1] != instance.s_goal:
                instance.target_list.append(instance.s_goal)
            instance.i = 1
            instance.s_target = instance.target_list[1]

        instance._initialize_llm_paths = fixed_waypoints
        with contextlib.redirect_stdout(io.StringIO()):
            actual_a = official_astar().searching(copy.deepcopy(query))
            actual_l = instance.searching(copy.deepcopy(query))
        expected_a = replay(query)
        expected_l = replay(query, waypoints, goal_weight=1)
        for label, actual, expected in (("A*", actual_a, expected_a),
                                        ("LLM-A*", actual_l, expected_l)):
            for field in ("operation", "storage", "length"):
                a, b = actual[field], expected[field]
                if not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
                    raise AssertionError(
                        f"map={row['map_id']} pair={row['pair_index']} "
                        f"{label} {field}: official={a}, replay={b}")
        checked += 1
    print(f"MATCH: {checked} paired cases, A* and LLM-A* operation/storage/length")


if __name__ == "__main__":
    main()
