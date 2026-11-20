"""Offline waypoint-guided search for paired improvement experiments.

This module consumes a *recorded* LLM waypoint list. It makes no model call,
which lets several search variants use exactly the same LLM response. The
geometry follows the official repository's eight motions and closed line
intersection rule. This is an experiment component, not yet the final
submission entry point.
"""

from __future__ import annotations

import heapq
import math
from typing import Any


MOTIONS = ((-1, 0), (-1, 1), (0, 1), (1, 1),
           (1, 0), (1, -1), (0, -1), (-1, -1))


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        if not math.isfinite(v) or (isinstance(v, float) and not v.is_integer()):
            return None
    return int(value[0]), int(value[1])


def _orientation(a, b, c):
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (cross > 0) - (cross < 0)


def _on_segment(a, b, p):
    return (_orientation(a, b, p) == 0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _intersects(a, b, c, d):
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if ab_c == 0 and _on_segment(a, b, c):
        return True
    if ab_d == 0 and _on_segment(a, b, d):
        return True
    if cd_a == 0 and _on_segment(c, d, a):
        return True
    if cd_b == 0 and _on_segment(c, d, b):
        return True
    return ab_c != ab_d and cd_a != cd_b


class Grid:
    """Official-format map with barrier segments and boundary walls."""

    def __init__(self, query: dict[str, Any]):
        self.xlo, self.xhi = query["range_x"]
        self.ylo, self.yhi = query["range_y"]
        if not all(isinstance(v, int) for v in
                   (self.xlo, self.xhi, self.ylo, self.yhi)):
            raise ValueError("Grid bounds must be integers")
        if self.xhi - self.xlo < 3 or self.yhi - self.ylo < 3:
            raise ValueError("Grid is too small")
        # The official Env treats upper bounds as sizes; its boundary is hi-1.
        self.xmax, self.ymax = self.xhi - 1, self.yhi - 1
        self.segments = []
        for y, x1, x2 in query["horizontal_barriers"]:
            if x1 != x2:
                self.segments.append(((x1, y), (x2, y)))
        for x, y1, y2 in query["vertical_barriers"]:
            if y1 != y2:
                self.segments.append(((x, y1), (x, y2)))
        self.segments.extend((
            ((self.xlo, self.ylo), (self.xlo, self.ymax)),
            ((self.xmax, self.ylo), (self.xmax, self.ymax)),
            ((self.xlo, self.ylo), (self.xmax, self.ylo)),
            ((self.xlo, self.ymax), (self.xmax, self.ymax)),
        ))

    def contains(self, p):
        return self.xlo < p[0] < self.xmax and self.ylo < p[1] < self.ymax

    def free_point(self, p):
        return self.contains(p) and all(not _on_segment(a, b, p)
                                        for a, b in self.segments)

    def free_move(self, a, b):
        return (self.free_point(b)
                and all(not _intersects(a, b, c, d)
                        for c, d in self.segments))


def clean_waypoints(grid: Grid, start, goal, raw: Any):
    """Remove unusable LLM coordinates while preserving start and goal."""
    middle = []
    if isinstance(raw, (tuple, list)):
        for item in raw:
            p = _point(item)
            if p is not None and p not in (start, goal) and grid.free_point(p):
                if not middle or middle[-1] != p:
                    middle.append(p)
    return [start, *middle, goal]


def search(query: dict[str, Any], waypoints: Any, alpha: float = 1,
           switch_mode: str = "expanded"):
    """Search with g + Euclidean goal distance + alpha * target distance.

    Returns path and metrics. A failed search has ``valid=False`` and no
    length. ``operation`` counts expanded states; ``storage`` counts unique
    discovered states. These definitions match the upstream return fields.
    """
    if not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be finite and nonnegative")
    if switch_mode not in ("expanded", "neighbor"):
        raise ValueError("switch_mode must be expanded or neighbor")
    grid = Grid(query)
    start, goal = _point(query["start"]), _point(query["goal"])
    if start is None or goal is None or not grid.free_point(start) or not grid.free_point(goal):
        raise ValueError("Start and goal must be free grid points")
    targets = clean_waypoints(grid, start, goal, waypoints)
    target_index = 1
    g = {start: 0.0}
    parent = {start: start}
    expanded = set()
    heap = []
    serial = 0

    def priority(s):
        return (g[s] + math.dist(s, goal)
                + alpha * math.dist(s, targets[target_index]))

    def push(s):
        nonlocal serial
        serial += 1
        heapq.heappush(heap, (priority(s), serial, s, g[s]))

    def advance_target():
        nonlocal target_index
        target_index += 1
        heap.clear()
        for candidate in g:
            if candidate not in expanded:
                push(candidate)

    push(start)
    operations = 0
    while heap:
        _, _, current, stored_g = heapq.heappop(heap)
        if current in expanded or stored_g != g[current]:
            continue
        expanded.add(current)
        operations += 1
        if current == goal:
            path = [goal]
            while path[-1] != start:
                path.append(parent[path[-1]])
            path.reverse()
            length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
            return {"operation": operations, "storage": len(g),
                    "length": length, "valid": True, "path": path,
                    "llm_output": targets, "alpha": alpha,
                    "switch_mode": switch_mode}
        # Advance only after expanding the waypoint, not merely seeing it.
        if (switch_mode == "expanded" and current == targets[target_index]
                and target_index < len(targets) - 1):
            advance_target()
        for dx, dy in MOTIONS:
            nxt = (current[0] + dx, current[1] + dy)
            # The original implementation switches here, before collision
            # checking. Keep this option only as a controlled comparison.
            if (switch_mode == "neighbor" and nxt == targets[target_index]
                    and target_index < len(targets) - 1):
                advance_target()
            if nxt in expanded or not grid.free_move(current, nxt):
                continue
            candidate = g[current] + math.hypot(dx, dy)
            if candidate < g.get(nxt, math.inf):
                g[nxt] = candidate
                parent[nxt] = current
                push(nxt)
    return {"operation": operations, "storage": len(g), "length": None,
            "valid": False, "path": [], "llm_output": targets,
            "alpha": alpha, "switch_mode": switch_mode}


def valid_path(query: dict[str, Any], path: Any) -> bool:
    """Check endpoints, every eight-neighbor step, and all barrier crossings."""
    if not isinstance(path, list) or not path:
        return False
    grid = Grid(query)
    points = [_point(p) for p in path]
    if any(p is None for p in points):
        return False
    if points[0] != _point(query["start"]) or points[-1] != _point(query["goal"]):
        return False
    return (all(grid.free_point(p) for p in points)
            and all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
                    and grid.free_move(a, b)
                    for a, b in zip(points, points[1:])))
