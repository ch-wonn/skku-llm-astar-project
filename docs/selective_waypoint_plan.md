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

## Prospective new-pair check

After the 189-case exploratory run, the fixed gate reduced operations over
no-LLM weighted A* by 1.7% overall, with only 28/189 cases activating it.
The next check uses **pair index 2 on each of maps 0-99** (`--offset 2
--stride 10 --limit 100`), which was not present in the previous experiments.
Keep the gate and threshold exactly as above. Primary acceptance criterion:
the paired 95% log-ratio interval for operations, gate over no-LLM weighted
A*, lies below 1. Secondary checks: valid path ratio 100%, path-length
geometric ratio no worse than 1.01, storage ratio, activation rate, and
measured runtime. Report all 100 selected cases and any API failures. If
the operation interval includes 1 or the other checks fail, do not claim a
confirmed benefit over no-LLM weighted A*.

## Results and decision

The prospective pair-2 collection returned 100/100 parseable Gemini
responses. All four paths were valid in 100/100 cases. The official A* and
LLM-A* search classes matched the replay's operation, storage, and length
on all 100 cases under the common collision predicate. The gate activated
in only 11 cases.

| New pair-2 outcome, gate / no-LLM weighted A* | Geometric mean | 95% log-ratio interval |
| --- | ---: | ---: |
| Operations | 0.9989 | 0.9933-1.0046 |
| Storage | 0.9991 | 0.9963-1.0019 |
| Path length | 0.9996 | 0.9987-1.0004 |

The operation interval includes 1, so the predeclared primary acceptance
criterion fails. Mean local elapsed time was approximately 13.50 ms for
the gate and 13.37 ms for no-LLM weighted A*; this single-run timing is
descriptive and does not establish a timing difference. The gate's mean
preprocessing took about 0.044 ms. The method is therefore **rejected as a
confirmed LLM-specific improvement**, even though its earlier 189-case
exploratory result was favorable. We do not tune the threshold after this
result.

Saved model responses and summaries are in `experiments/selective_waypoint/`.
To repeat the offline comparison without an API call:

```text
python scripts/evaluate_selective_waypoint.py experiments/selective_waypoint/pair2_waypoints.jsonl --output results/selective_pair2_recomputed.jsonl --summary-output results/selective_pair2_summary_recomputed.json
```
