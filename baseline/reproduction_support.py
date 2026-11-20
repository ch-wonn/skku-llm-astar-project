"""Diagnostics and validation around unchanged search algorithms."""
import copy
import math
from llmastar.pather import AStar, LLMAStar


class AuditedLLMAStar(LLMAStar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit = {'parse_ok': False, 'target_transitions': []}

    def _filter_valid_nodes(self, nodes):
        self.audit['parse_ok'] = True
        self.audit['parsed_nodes'] = copy.deepcopy(nodes)
        kept = super()._filter_valid_nodes(nodes)
        self.audit['filtered_nodes_before_endpoint_insertion'] = copy.deepcopy(kept)
        return kept

    def _initialize_llm_paths(self):
        super()._initialize_llm_paths()
        self.audit['final_targets'] = copy.deepcopy(self.target_list)
        self.audit['intermediate_count'] = sum(
            tuple(p) not in {self.s_start, self.s_goal} for p in self.target_list)
        self.audit['initial_target'] = self.s_target
        self.audit['fallback_used'] = False

    def _update_target(self):
        before = self.s_target
        super()._update_target()
        self.audit['target_transitions'].append({'from': before, 'to': self.s_target})


def validate_path(path, query, result):
    from shapely.geometry import LineString
    p = [tuple(v) for v in path]
    start, goal = tuple(query['start']), tuple(query['goal'])
    if p and p[0] == goal and p[-1] == start:
        p.reverse()
    if not p or p[0] != start or p[-1] != goal:
        return False, 'endpoints', p
    xmin, xmax = query['range_x'][0], query['range_x'][1] - 1
    ymin, ymax = query['range_y'][0], query['range_y'][1] - 1
    if any(not (xmin < x < xmax and ymin < y < ymax) for x, y in p):
        return False, 'boundary', p
    walls = [LineString([(a,y),(b,y)]) for y,a,b in query['horizontal_barriers']]
    walls += [LineString([(x,a),(x,b)]) for x,a,b in query['vertical_barriers']]
    length = 0.
    for a,b in zip(p,p[1:]):
        if (abs(a[0]-b[0]),abs(a[1]-b[1])) not in {(0,1),(1,0),(1,1)}:
            return False, 'motion', p
        if any(LineString([a,b]).intersects(w) for w in walls):
            return False, 'collision', p
        length += math.dist(a,b)
    if not math.isclose(length,result['length'],rel_tol=1e-9,abs_tol=1e-9):
        return False,'length',p
    return True,None,p
