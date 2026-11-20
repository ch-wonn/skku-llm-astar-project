"""Check the live improved search against the saved-response replay."""

import contextlib
import copy
import io
import json
import math
import sys
from pathlib import Path

from llmastar.env.search import plotting
from improved_search import (ImprovedLLMAStar, StartVisibleWaypointLLMAStar,
                             WeightedWaypointLLMAStar)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from selective_waypoint import gated_replay
from official_replay import replay


class DummyPlot:
    def __init__(self, *args):
        pass

    def animation(self, *args):
        pass


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def ask(self, **kwargs):
        self.calls += 1
        return json.dumps(self.response)


def main():
    root = Path(__file__).resolve().parent / "experiment_results" / "reproduction_v2"
    original_plot = plotting.Plotting
    plotting.Plotting = DummyPlot
    try:
        # One gate-off and one gate-on example from each prompt.
        examples = (("standard", 0), ("standard", 4),
                    ("cot", 0), ("cot", 2), ("cot", 4),
                    ("repe", 0), ("repe", 2), ("repe", 4))
        for prompt, index in examples:
            item = json.loads((root / prompt / "cases" / f"{index:04d}.json").read_text())
            if item["status"] != "valid":
                continue
            query, points = item["query"], item["result"]["llm_output"]
            expected = gated_replay(query, points)
            model = FakeModel(points)
            alg = ImprovedLLMAStar.__new__(ImprovedLLMAStar)
            alg.llm, alg.prompt, alg.model = "gpt", prompt, model
            with contextlib.redirect_stdout(io.StringIO()):
                actual = alg.searching(copy.deepcopy(query), filepath="ignored.png")
            assert model.calls == 1
            assert alg.selected_waypoint == expected["selected_waypoint"]
            assert actual["operation"] == expected["operation"]
            assert actual["storage"] == expected["storage"]
            assert math.isclose(actual["length"], expected["length"], abs_tol=1e-10)
            assert alg.extract_path(alg.PARENT) == expected["path"]
            weighted = WeightedWaypointLLMAStar.__new__(WeightedWaypointLLMAStar)
            weighted.llm, weighted.prompt = "gpt", prompt
            weighted.model = FakeModel(points)
            weighted_expected = replay(query, points, goal_weight=2,
                                       target_weight=0.5)
            with contextlib.redirect_stdout(io.StringIO()):
                weighted_actual = weighted.searching(copy.deepcopy(query),
                                                     filepath="ignored.png")
            assert weighted.model.calls == 1
            assert weighted_actual["operation"] == weighted_expected["operation"]
            assert weighted_actual["storage"] == weighted_expected["storage"]
            assert math.isclose(weighted_actual["length"],
                                weighted_expected["length"], abs_tol=1e-10)
            assert weighted.extract_path(weighted.PARENT) == weighted_expected["path"]
            relaxed = StartVisibleWaypointLLMAStar.__new__(StartVisibleWaypointLLMAStar)
            relaxed.llm, relaxed.prompt = "gpt", prompt
            relaxed.model = FakeModel(points)
            relaxed_expected = gated_replay(query, points,
                                            require_goal_visible=False)
            with contextlib.redirect_stdout(io.StringIO()):
                relaxed_actual = relaxed.searching(copy.deepcopy(query),
                                                   filepath="ignored.png")
            assert relaxed.model.calls == 1
            assert relaxed.selected_waypoint == relaxed_expected["selected_waypoint"]
            assert relaxed_actual["operation"] == relaxed_expected["operation"]
            assert relaxed_actual["storage"] == relaxed_expected["storage"]
            assert math.isclose(relaxed_actual["length"],
                                relaxed_expected["length"], abs_tol=1e-10)
            assert relaxed.extract_path(relaxed.PARENT) == relaxed_expected["path"]
            print(f"{prompt} case {index}: gate={alg.selected_waypoint is not None}, "
                  f"operation={actual['operation']}")
    finally:
        plotting.Plotting = original_plot


if __name__ == "__main__":
    main()
