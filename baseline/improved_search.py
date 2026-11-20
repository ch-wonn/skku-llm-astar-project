"""Live GPT LLM-A* with the pre-registered selective waypoint rule."""

import copy
import math
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from selective_waypoint import GOAL_WEIGHT, TARGET_WEIGHT, select_waypoint
from llmastar.pather import LLMAStar


class ImprovedLLMAStar(LLMAStar):
    """Use the original GPT prompt/API and search loop with a waypoint gate.

    The original model response is parsed and filtered by LLMAStar. The gate
    selects at most one LLM waypoint. No additional model request is made.
    """

    def _initialize_parameters(self, input_data):
        # Upstream mutates range maxima, so retain the untouched map for gating.
        self._gate_query = copy.deepcopy(input_data)
        super()._initialize_parameters(input_data)

    def _initialize_llm_paths(self):
        super()._initialize_llm_paths()
        self.source_waypoints = list(self.target_list)
        chosen, eligible = select_waypoint(self._gate_query, self.target_list)
        self.selected_waypoint = chosen
        self.eligible_waypoints = eligible
        if chosen is None:
            self.target_list = [self.s_start, self.s_goal]
        else:
            self.target_list = [self.s_start, chosen, self.s_goal]
        self.i = 1
        self.s_target = self.target_list[1]

    def f_value(self, state):
        goal_distance = math.hypot(self.s_goal[0] - state[0],
                                   self.s_goal[1] - state[1])
        if self.selected_waypoint is None:
            return self.g[state] + GOAL_WEIGHT * goal_distance
        target_distance = math.hypot(self.s_target[0] - state[0],
                                     self.s_target[1] - state[1])
        return self.g[state] + (GOAL_WEIGHT * goal_distance
                                + TARGET_WEIGHT * target_distance)
