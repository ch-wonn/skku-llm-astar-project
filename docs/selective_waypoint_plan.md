# Selective waypoint experiment

Date: 2026-11-18 KST. The rule below is fixed before running it on saved
model responses. This is a new exploratory method; the previously used 89
and 100 cases are not a fresh held-out confirmation for it.

## Motivation

On 100 new start/goal pairs, goal weight 2 with waypoint weight 0.5 improved
over original LLM-A*, but no-LLM weighted A* at goal weight 2 was better in
operations, storage, and path length. Therefore always following Gemini's
waypoints appears to impose an unnecessary search cost on many cases.

## Fixed rule

For each case, use goal weight 2. First test whether the straight segment
from start to goal intersects a barrier. If it does not, run no-LLM weighted
A*. If it does, consider each model-suggested intermediate point after the
same official boundary/obstacle filter. Keep a point only if both straight
segments start-to-point and point-to-goal are collision-free and their sum
is no more than 1.25 times the direct Euclidean distance. If several pass,
choose the smallest detour ratio. Guide search through this one waypoint
with waypoint weight 0.5. If none passes, run no-LLM weighted A*.

The 1.25 threshold is a geometric safeguard, fixed before results. It is
not tuned on these cases. Its line checks add preprocessing work, which must
be disclosed; a lower search operation count alone does not imply lower
wall-clock time. The goal is to use an LLM waypoint only when it describes
a short collision-free bypass around a direct obstacle.

## Evaluation

Use the saved 89 map-pair-0 and 100 map-pair-1 Gemini Few-Shot responses,
reporting the two groups separately and pooled. Compare original LLM-A*,
always-on `(goal=2, waypoint=0.5)`, no-LLM weighted A*, and this gate on
the same queries. Primary comparison is gate versus no-LLM weighted A*
operations. Secondary: storage, path length, valid paths, gate activation
rate, and measured preprocessing/search time. If the gate does not clearly
beat the no-LLM control, reject it. Do not select a new threshold after
seeing these results.
