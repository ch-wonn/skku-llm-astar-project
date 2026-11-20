"""Strict waypoint parsing: never fabricate coordinates on parse failure."""
import ast
import math
import re


class WaypointParseError(ValueError):
    pass


def _number(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _number(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
    # Safe support for coordinate additions/subtractions present in some outputs.
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left, right = _number(node.left), _number(node.right)
        return left + right if isinstance(node.op, ast.Add) else left - right
    raise WaypointParseError('Non-numeric coordinate expression')


def parse_waypoints(text):
    if not isinstance(text, str) or not text.strip():
        raise WaypointParseError('Empty response')
    markers = list(re.finditer(r'Generated\s+Path\s*:', text, re.I))
    part = text[markers[-1].end():] if markers else text
    candidates = re.findall(r'\[\s*\[.*?\]\s*\]', part, re.S)
    if not candidates:
        raise WaypointParseError('No complete waypoint array')
    try:
        tree = ast.parse(candidates[-1], mode='eval').body
        if not isinstance(tree, ast.List) or len(tree.elts) < 2:
            raise WaypointParseError('Expected at least two coordinates')
        points = []
        for node in tree.elts:
            if not isinstance(node, ast.List) or len(node.elts) != 2:
                raise WaypointParseError('Each coordinate must be [x, y]')
            pair = [_number(v) for v in node.elts]
            if not all(math.isfinite(v) for v in pair):
                raise WaypointParseError('Non-finite coordinate')
            points.append(pair)
        return points
    except (SyntaxError, OverflowError, RecursionError, TypeError) as exc:
        raise WaypointParseError('Malformed waypoint array') from exc
