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
