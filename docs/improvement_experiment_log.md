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
