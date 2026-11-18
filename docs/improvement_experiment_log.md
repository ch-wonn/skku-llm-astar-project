# Improvement experiment log

This log separates diagnostic runs from LLM experiments. Times use Korea
Standard Time. Results are descriptive; none are claimed as Table 1
reproduction or as improved LLM-A* performance yet.

## 2026-11-18: public data and source inspection

- Downloaded the official repository at commit
  `9414ed894d774f71c36e8c0afd0e20e6033b95b1`.
- Validated `environment_50_30.json`: 100 maps, 10 start/goal pairs per map,
  1,000 paired cases.
- Source observation: original LLM-A* advances a waypoint when it appears
  among neighbors, before checking whether the move crosses a barrier. This
  led to a hypothesis that advancing on actual expansion would be better.

## Diagnostic 1: waypoint-switch timing

Command:

```text
python scripts/probe_switch_rule.py --dataset data/environment_50_30.json --output results/probe_1000.jsonl
```

The probe used a deterministic free point nearest the start-goal midpoint,
**not LLM output**. Both variants used the same Python search implementation,
map cases, waypoint, and `alpha=1`; only switch timing changed. All 1,000
cases produced paths that passed the segment collision checker.

| Measure | Expanded-waypoint / neighbor-waypoint geometric mean |
| --- | ---: |
| Search operations | 1.0180 |
| Storage | 1.0116 |
| Path length | 1.0012 |

The revised switch rule changed operation count on 368 cases and path length
on 156 cases. It made these proxy metrics slightly worse on average. We
therefore rejected the assumption that the timing correction alone improves
performance. It may still fix a specific invalid-transition behavior, which
requires a targeted case and LLM-waypoint evaluation.

## Diagnostic 2: half-strength waypoint guidance

On the same 1,000 proxy cases, `alpha=0.5` was compared with `alpha=1`, with
neighbor-based switching in both. Geometric mean ratios for `0.5 / 1` were:
operations 1.1535, storage 1.0771, path length 0.9849. All paths were valid.
Shorter paths came at a substantial search cost. This is a trade-off, not a
clear improvement, so half-strength guidance was not selected as the method.

## Diagnostic 3: geometric waypoint filter

With a preselected 1.05 straight-line detour threshold, only 6 of the 1,000
proxy waypoints were rejected. The resulting ratios were essentially 1, so
this proxy experiment does not support the filter. LLM waypoints may have a
different distribution; this has not been tested.

## Next experiment and reporting boundary

Collect actual LLM waypoint responses once, then replay each saved response
through the original and improved search. The development model may be
Gemini under the course FAQ, but the model, prompt, quota, and failed calls
must be disclosed. The existing standalone search prototype does not yet
match the official implementation's operation/storage accounting and must
not be used to report paper-comparable Table 1 numbers. A final method will
be selected only after a paired LLM-waypoint comparison and clean-environment
verification.

## 2026-11-18: Gemini connection and three-prompt pilot

The project's chosen development model is `gemini-3.5-flash-lite`. The
previous default, `gemini-2.5-flash-lite`, returned HTTP 404 for this new
account even though it appeared in the model list. The replacement passed a
short connectivity check. The local key remained in untracked `.env` and was
not written to result files.

We copied the official repository's GPT prompt templates at the pinned
commit, under its MIT license, and used the `standard` (five examples), `cot`
(three examples), and `repe` (three examples) templates with Gemini. We
started at dataset case 10 to avoid the first public case, which matches a
demonstration in the standard prompt. Commands used the same structure:

```text
python scripts/collect_waypoints.py --dataset data/environment_50_30.json --output results/pilot_standard.jsonl --prompt standard --offset 10 --limit 5 --delay 1
python scripts/collect_waypoints.py --dataset data/environment_50_30.json --output results/pilot_cot.jsonl --prompt cot --offset 10 --limit 5 --delay 1
python scripts/collect_waypoints.py --dataset data/environment_50_30.json --output results/pilot_repe.jsonl --prompt repe --offset 10 --limit 5 --delay 1
```

All 15 calls returned parseable waypoint lists. The prototype waypoint
validator retained 19/22 points for Few-Shot, 19/20 for CoT, and 20/22 for
RePE, including enforced start and goal. Mean API latency was approximately
7.7, 6.9, and 12.8 seconds respectively. This is one map with five pairs per
prompt, so it is only a connectivity and format pilot.

Replaying each response through the prototype's neighbor-switch control and
expanded-switch candidate gave operation geometric-mean ratios of 1.069,
1.084, and 1.033 for Few-Shot, CoT, and RePE. All paths passed collision
checks. This again argues against selecting switch timing alone as the
performance improvement. The prototype's accounting still differs from the
official code, and these five-case figures are not report-ready performance
estimates.

## 2026-11-18: waypoint-count prompt pilot

Question: Does asking for more intermediate waypoints improve final search
efficiency? We used Gemini 3.5 Flash-Lite, the official GPT Few-Shot prompt,
temperature 0, and 10 fixed cases (one start/goal pair from each of maps
1-10). Four conditions used the same cases: original prompt, plus the same
prompt prefixed with a request for exactly 1, 3, or 5 intermediate points.
This changes only the count instruction. All 40 calls produced parseable
lists and all final paths passed collision checking.

The tracked source records are in `experiments/count_pilot/`. To recompute
the table from those saved LLM responses without making API calls:

```text
python scripts/analyze_waypoint_count.py --input-dir experiments/count_pilot --output results/count_paired.jsonl
```

The API collection used `collect_waypoints.py` with `--prompt standard
--offset 10 --stride 10 --limit 10` for each condition, adding
`--intermediate-count 1`, `3`, or `5` except for the original prompt.

| Condition | Mean valid intermediate points | Exact count followed | Operations / original prompt | Path length / original prompt |
| --- | ---: | ---: | ---: | ---: |
| Original prompt | 1.5 | - | 1.000 | 1.000 |
| Request 1 | 0.8 | 9/10 | 1.161 | 0.991 |
| Request 3 | 1.9 | 0/10 | 1.563 | 0.991 |
| Request 5 | 3.3 | 1/10 | 1.700 | 0.988 |

Ratios are geometric means of paired cases. The model generally returned
one fewer intermediate point than requested for the 3 and 5 conditions.
Asking for more points slightly shortened paths but substantially increased
search operations in this 10-case pilot. This does not support a blanket
increase in waypoint count as an efficiency improvement. The prototype's
operation accounting differs from the official repository, and 10 cases are
too few to claim a reliable population effect.

Follow-on diagnostic: from each five-point-request response, retain at most
two intermediate points with the largest turning angles, preserving order.
Compared with the original prompt, the paired operation ratio was 1.647 and
the path-length ratio was 0.984. This was a small improvement over keeping
all the longer response's points (1.700 and 0.988), but still increased
operations substantially relative to the original prompt. It was not
selected as the final method.

## 2026-11-18: goal-distance weight, saved Gemini waypoints

Motivation: the official LLM-A* search priority is
`g(s) + d(s, goal) + d(s, target)`. An imperfect waypoint can pull expansion
away from the final goal. We tested `g(s) + 2*d(s, goal) + d(s, target)` while
keeping the same Gemini response and every other search rule fixed. This
weight is a modest weighted-A* style change, not a new LLM prompting method.
The exploratory 10-map split selected weight 2; those cases are excluded
from the figures below. The selection and first held-out split were recorded
before collecting its responses. After inspecting the first 20 cases, we
fixed an additional 30-map extension with no parameter changes.

The evaluation uses map IDs 11-60, pair index 0, on the public official
50x30 dataset: 20 initial held-out and 30 subsequent extension cases. Gemini
3.5 Flash-Lite used the pinned official GPT Few-Shot prompt at temperature
0. There were 50/50 parseable model responses. Ordinary A*, original
LLM-A*, and the candidate all returned collision-checked paths for 50/50
cases. The candidate does not make extra model calls: both LLM-A* variants
replay each case's identical saved response. Raw responses and paired results
are in `experiments/goal_weight_holdout/`; exact commands are in
`docs/goal_weight_experiment_plan.md`.

| Split | Cases | Candidate/original operations | Storage | Path length |
| --- | ---: | ---: | ---: | ---: |
| Initial held-out | 20 | 0.768 (95% CI 0.561-1.052) | 0.852 (0.730-0.994) | 1.008 (0.993-1.024) |
| Later extension | 30 | 0.869 (0.694-1.088) | 0.892 (0.796-1.000) | 1.004 (0.987-1.022) |
| Pooled descriptive | 50 | 0.827 (0.689-0.994) | 0.876 (0.799-0.959) | 1.006 (0.994-1.018) |

Ratios are paired geometric means; lower operations and storage are better,
while 1.0 path length means equal length. Intervals are normal approximations
on log ratios, not a guarantee for new maps. In the 50 pooled cases,
candidate operation ratio had arithmetic mean 1.007 and sample SD 0.725.
It improved operation counts in 32 cases, tied in 6, and worsened them in
12. Thus the geometric mean gain is sensitive to large improvements in some
maps, while the arithmetic mean shows no average operation gain. Candidate
storage ratio had sample SD 0.261 and path-length ratio sample SD 0.045.
Path length improved in 8, tied in 27, and worsened in 15 cases. The method
is a measurable trade-off rather than a universal improvement.

For context, original LLM-A*/ordinary A* pooled geometric means were 0.477
operations, 0.688 storage, and 1.027 path length. The proposed candidate's
gain is *relative to original LLM-A** on these cases, not a claim to beat
ordinary A* in path optimality. A differential check against the pinned
official A* and LLM-A* search classes matched operation, storage, and length
on all 50 cases after injecting the same saved waypoints and collision
predicate. This validates search-loop/accounting fidelity, but it does not
independently validate the replacement geometry against Shapely. The sample
is one pair per map, not the paper's full 1,000-case Table 1 setup; model
and sample differences must be disclosed in the final report.

## 2026-11-18: final untouched-map check and stopping decision

Before collection we fixed the remaining dataset slice as `--offset 610
--stride 10 --limit 40`, with the same Gemini model, Few-Shot prompt,
temperature 0, and goal weight 2. The plan mistakenly described this as
40 maps, IDs 61-100. The public dataset is indexed 0-99, so the selected
slice contains **39 cases, maps 61-99**. We did not add a replacement case.
All 39 calls were parseable. All 39 paths for each of A*, original LLM-A*,
and the candidate passed collision validation. The pinned official search
classes and offline replay matched operation, storage, and path length on
all 39 cases under the common collision predicate.

| Split | Cases | Candidate/original operations | Storage | Path length |
| --- | ---: | ---: | ---: | ---: |
| Final untouched maps | 39 | 0.724 (95% CI 0.568-0.923) | 0.800 (0.705-0.908) | 1.003 (0.985-1.020) |
| All evaluation maps | 89 | 0.780 (0.673-0.904) | 0.842 (0.780-0.908) | 1.004 (0.994-1.015) |

The final 39-case operation ratio arithmetic mean was 0.929, sample SD
0.717; the candidate improved operations on 26 cases, tied on 4, and
worsened on 9. For all 89 evaluation cases, operation ratio arithmetic mean
was 0.973, sample SD 0.718, with 58 improvements, 10 ties, and 21 losses.
The 89-case storage ratio sample SD was 0.271, and path-length ratio sample
SD was 0.051. Original LLM-A*/ordinary A* ratios on the 89 cases were
0.500 operations, 0.702 storage, and 1.031 path length (geometric means).
The final untouched maps support the goal-weight candidate's efficiency
effect, with a small, uncertain increase in path length. Because the method
is simple and explainable and the independent final split agrees with the
earlier direction, we stop searching for further variants. The final report
must still state that this is an 89-case, one-pair-per-map Gemini evaluation,
not the 1,000-case Table 1 reproduction, and must discuss the 21 maps where
the candidate increased operation count.

## 2026-11-18: post-hoc heuristic ablation

After the 89-case goal-weight study, we ran an offline ablation on the same
saved Gemini responses to test whether the benefit was specifically due to
LLM waypoints. This is explanatory, **not** an independent test for selecting
a new final method. Detailed parameters and the next untested-pair plan are
in `docs/next_improvement_experiment.md`.

Compared with original LLM-A*, geometric-mean operation ratios were 0.975
for goal weight 1.5, 0.780 for goal weight 2, and 0.620 for goal weight 3,
all with waypoint weight 1. Goal weight 3 had path-length ratio 1.009, a
larger detour than goal weight 2's 1.004. With goal weight 2 and waypoint
weight 0.5, operations were 0.707 and path length 0.992. True no-LLM
weighted A* at goal weight 2 achieved operations 0.704 and length 0.997.
Thus reducing waypoint influence looks promising, but the current evidence
does not show an operation advantage from the LLM waypoint itself. A new
100-pair confirmation is needed before revising the selected method.

## 2026-11-18: new-pair confirmation run by project member

The project member ran the fixed next test locally: pair index 1 on each of
the 100 public maps, using Gemini 3.5 Flash-Lite and the same Few-Shot
prompt. The 100/100 responses parsed, with no duplicate cases. All tested
paths were valid in all 100 cases. The saved responses were replayed offline
through the original LLM-A*, goal weight 2 with waypoint weights 1 and 0.5,
and true no-LLM weighted A*. The replay matched the pinned official A* and
LLM-A* counts and lengths for all 100 cases under the common collision
predicate. Recomputing the ablation from the raw responses gave byte-for-byte
identical paired and summary outputs.

Compared with original LLM-A*, the new `(goal=2, waypoint=0.5)` candidate
had geometric-mean operation ratio 0.626, storage 0.775, length 0.999.
Compared with the first `(2, 1)` candidate, its ratios were 0.858, 0.930,
and 0.987 respectively. However, compared with no-LLM weighted A* at goal
weight 2, the new candidate was **worse in all three metrics**: operations
1.084 (95% interval 1.015-1.158), storage 1.034 (1.007-1.063), and length
1.010 (1.003-1.017). This is an unfavorable result for the hypothesis that
Gemini waypoints themselves improve search under these weights. The report
should separate the gain from search weighting from any claim about LLM
guidance; the latter is not established here. Detailed results and the
1,000-case guidance are in `docs/next_improvement_experiment.md`.

## 2026-11-18: selective waypoint gate, exploratory 189 cases

To test whether Gemini waypoints help in a restricted situation, we fixed a
geometric gate before replaying the 89 earlier map-pair-0 cases and the 100
map-pair-1 confirmation cases. The gate uses goal weight 2 and falls back to
no-LLM weighted A* unless a model waypoint describes a short collision-free
two-leg bypass around a blocked direct line. The exact criterion, including
the 1.25 detour threshold, is in `docs/selective_waypoint_plan.md`.

The gate activated on 13/89 and 15/100 cases. All paths were valid. Gate over
no-LLM weighted A* operation geometric means were 0.974 (95% interval
0.956-0.993) in the first group, 0.990 (0.979-1.001) in the second, and
0.983 (0.972-0.993) pooled. Pooled storage and length ratios were 0.994
and 0.999. Among the 28 activated cases, operation ratio was 0.889
(0.836-0.945). This is a small overall gain, not a confirmed new-sample
result: these cases were previously examined for other methods. Mean local
runtime was about 17.6 ms for the gate and 17.1 ms for weighted A*, with
the gate's geometry preprocessing around 0.075 ms per case. These timings
are descriptive and depend on the local Windows/Python environment.

The gate and acceptance criterion were fixed before collecting a new pair-2
case from each map. That prospective check is underway; no claim of a
confirmed LLM contribution is made from these 189 cases alone.

## 2026-11-18: selective gate, prospective pair-2 check

We kept the gate, 1.25 detour threshold, model, and Few-Shot prompt fixed,
then collected pair index 2 for all 100 maps. All 100 Gemini responses
parsed and all four comparison methods returned collision-checked paths.
The gate activated on 11/100 cases. The pinned official A* and LLM-A*
classes matched the offline replay's counts and lengths on all 100 cases
under the shared collision predicate.

The gate/no-LLM weighted A* paired geometric-mean operation ratio was
0.9989 with 95% log-ratio interval 0.9933-1.0046, including 1. Storage
ratio was 0.9991 (0.9963-1.0019) and path-length ratio 0.9996
(0.9987-1.0004). Mean measured runtime was about 13.50 ms for the gate
versus 13.37 ms for weighted A* in this local run. The primary predeclared
criterion failed, so we rejected the gate as a confirmed LLM-specific
improvement and did not tune it further. This reconciles the favorable but
small 189-case exploratory result with the new-sample finding. The negative
result is retained in `docs/selective_waypoint_plan.md` and the raw
responses in `experiments/selective_waypoint/`.
