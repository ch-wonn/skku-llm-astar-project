"""Replay the published A* and LLM-A* search logic with saved waypoints.

This follows the official implementation at commit 9414ed894d77, including
heap-pop operation counting and recording blocked neighbors in ``g``. Model
calls and plotting are removed so the SAME recorded LLM response can be
replayed through control and candidate search rules. The official code is
MIT licensed; see third_party/LICENSE.llm-astar.
"""

import heapq
import math

from waypoint_search import Grid, MOTIONS, _intersects


def _official_obs(query):
    xmax, ymax = query["range_x"][1], query["range_y"][1]
    obs = {(x, 0) for x in range(xmax)}
    obs.update((x, ymax - 1) for x in range(xmax))
    obs.update((0, y) for y in range(ymax))
    obs.update((xmax - 1, y) for y in range(ymax))
    for y, x1, x2 in query["horizontal_barriers"]:
        obs.update((x, y) for x in range(x1, x2))
    for x, y1, y2 in query["vertical_barriers"]:
        obs.update((x, y) for y in range(y1, y2))
    return obs


def _official_targets(query, raw, obs):
    start, goal = tuple(query["start"]), tuple(query["goal"])
    # The upstream filter is applied after range maxima are reduced by one.
    xmin, xmax = query["range_x"][0], query["range_x"][1] - 1
    ymin, ymax = query["range_y"][0], query["range_y"][1] - 1
    targets = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            x, y = item[:2]
            if (isinstance(x, int) and not isinstance(x, bool)
                    and isinstance(y, int) and not isinstance(y, bool)
                    and (x, y) not in obs
                    and xmin + 1 < x < xmax - 1
                    and ymin + 1 < y < ymax - 1):
                targets.append((x, y))
    if not targets or targets[0] != start:
        targets.insert(0, start)
    if targets[-1] != goal:
        targets.append(goal)
    return targets


def replay(query, waypoints=None, *, goal_weight=1.0, target_weight=1.0,
           switch_mode="neighbor"):
    """Run original-style search; ``None`` waypoints selects ordinary A*.

    ``goal_weight=1`` is the original LLM-A* priority. Other positive values
    are an experimental candidate that changes only the goal-distance weight.
    """
    if not math.isfinite(goal_weight) or goal_weight <= 0:
        raise ValueError("goal_weight must be positive and finite")
    if not math.isfinite(target_weight) or target_weight < 0:
        raise ValueError("target_weight must be nonnegative and finite")
    if switch_mode not in ("neighbor", "expanded"):
        raise ValueError("switch_mode must be neighbor or expanded")
    grid = Grid(query)
    start, goal = tuple(query["start"]), tuple(query["goal"])
    llm = waypoints is not None
    obs = _official_obs(query) if llm else None
    targets = _official_targets(query, waypoints, obs) if llm else None
    target_index = 1
    target = targets[target_index] if llm else None
    open_heap = []
    closed = []
    parent = {start: start}
    g = {start: 0.0}

    def f_value(state):
        h_goal = math.dist(state, goal)
        if llm:
            # Upstream computes g + heuristic, with both distances summed
            # inside heuristic. Preserve that grouping for heap tie ordering.
            return g[state] + (goal_weight * h_goal
                               + target_weight * math.dist(state, target))
        return g[state] + goal_weight * h_goal

    def cost(a, b):
        if any(_intersects(a, b, c, d) for c, d in grid.segments):
            return math.inf
        return math.dist(a, b)

    heapq.heappush(open_heap, (f_value(start), start))

    def advance_target():
        nonlocal target_index, target, open_heap
        target_index += 1
        if target_index < len(targets):
            target = targets[target_index]
        refreshed = []
        for _, queued_state in open_heap:
            heapq.heappush(refreshed, (f_value(queued_state), queued_state))
        open_heap = refreshed

    while open_heap:
        _, state = heapq.heappop(open_heap)
        closed.append(state)
        if state == goal:
            break
        if llm and switch_mode == "expanded" and state == target and goal != target:
            advance_target()
        for dx, dy in MOTIONS:
            neighbor = (state[0] + dx, state[1] + dy)
            if (llm and switch_mode == "neighbor" and neighbor == target
                    and goal != target):
                advance_target()
            if neighbor in closed:
                continue
            tentative = g[state] + cost(state, neighbor)
            if neighbor not in g:
                g[neighbor] = math.inf
            if tentative < g[neighbor]:
                g[neighbor] = tentative
                parent[neighbor] = state
                heapq.heappush(open_heap, (f_value(neighbor), neighbor))
    if goal not in parent:
        return {"valid": False, "operation": len(closed), "storage": len(g),
                "length": None, "path": [], "llm_output": targets}
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return {"valid": True, "operation": len(closed), "storage": len(g),
            "length": sum(math.dist(a, b) for a, b in zip(path, path[1:])),
            "path": path, "llm_output": targets}
