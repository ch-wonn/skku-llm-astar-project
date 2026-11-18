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
