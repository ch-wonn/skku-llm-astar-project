"""Fixed geometric gate for optional LLM waypoint guidance.

See docs/selective_waypoint_plan.md. The gate falls back to no-LLM weighted
A* unless a short, two-segment collision-free bypass is available.
"""

import math
import time

from official_replay import _official_obs, _official_targets, replay
from waypoint_search import Grid, _intersects


GOAL_WEIGHT = 2.0
TARGET_WEIGHT = 0.5
MAX_DETOUR = 1.25


def select_waypoint(query, raw_waypoints):
    """Return the one eligible bypass point and the number of eligible points."""
    grid = Grid(query)
    start, goal = tuple(query["start"]), tuple(query["goal"])
    direct_distance = math.dist(start, goal)
    chosen = None
    eligible = 0

    def clear(a, b):
        return not any(_intersects(a, b, c, d) for c, d in grid.segments)

    if direct_distance > 0 and not clear(start, goal):
        targets = _official_targets(query, raw_waypoints, _official_obs(query))
        options = []
        for point in targets[1:-1]:
            detour = (math.dist(start, point) + math.dist(point, goal)) / direct_distance
            if detour <= MAX_DETOUR and clear(start, point) and clear(point, goal):
                options.append((detour, point))
        eligible = len(options)
        if options:
            chosen = min(options)[1]
    return chosen, eligible


def gated_replay(query, raw_waypoints):
    started = time.perf_counter()
    chosen, eligible = select_waypoint(query, raw_waypoints)
    preprocess_seconds = time.perf_counter() - started
    start, goal = tuple(query["start"]), tuple(query["goal"])
    search_started = time.perf_counter()
    if chosen is None:
        result = replay(query, goal_weight=GOAL_WEIGHT)
    else:
        result = replay(query, [start, chosen, goal],
                        goal_weight=GOAL_WEIGHT, target_weight=TARGET_WEIGHT)
    search_seconds = time.perf_counter() - search_started
    result["gate_active"] = chosen is not None
    result["selected_waypoint"] = chosen
    result["eligible_waypoints"] = eligible
    result["preprocess_seconds"] = preprocess_seconds
    result["search_seconds"] = search_seconds
    return result
