# Goal-distance weight experiment

Date: 2026-11-18 KST. This plan was fixed before collecting the held-out
Gemini responses below.

## Motivation and hypothesis

The original LLM-A* priority is `g(s) + d(s, goal) + d(s, target)`. When a
waypoint is imperfect, the extra target distance may steer search away from
the actual goal. We test a small, explainable change: double only the goal
distance, yielding `g(s) + 2*d(s, goal) + d(s, target)`. Model calls,
waypoint filtering, collision rules, target-switching, and output format
remain the same. The hypothesis is fewer operations and less storage with
little or no path-length increase; path validity must stay 100%.

This resembles weighted A*, so it is an incremental method rather than a
novel search paradigm. It may produce longer paths on other maps. The report
must discuss that risk and compare against ordinary A* and original LLM-A*.

## Selection and confirmation split

- Exploratory selection: one start/goal pair from each of maps 1-10 using
  saved Few-Shot Gemini 3.5 Flash-Lite responses. We inspected goal weights
  1.25, 1.5, and 2, and selected 2 because it was the only tested weight
  that reduced both operations and path length in this split. These are
  tuning results, not confirmation evidence.
- Held-out confirmation: one fixed start/goal pair from each of maps 11-30
  (`--offset 110 --stride 10 --limit 20`). No candidate parameter is changed
  after seeing these results.
- Prospective extension fixed after inspecting the 20-case result: one pair
  from each of maps 31-60 (`--offset 310 --stride 10 --limit 30`). Keep goal
  weight 2, the same prompt and model, and report these 30 separately as well
  as pooled with maps 11-30. This adds precision; it does not erase the
  initial 20-case outcome or make the selection split confirmatory.
- Final untouched-map check fixed after inspecting the 50-case results: one
  pair from each remaining map (`--offset 610 --stride 10 --limit 40`). The
  prerecord mistakenly called this maps 61-100 and 40 cases. The dataset's
  IDs are 0-99, so this slice actually yields maps 61-99, 39 cases. We kept
  the original selection expression, added no replacement case, and report
  39 final cases and 89 evaluation cases total. No method, prompt, model, or
  metric definition changed after seeing these cases. This is the final
  candidate check; stop method selection here and retain unfavorable outcomes.
- Same model response is replayed for original LLM-A* (goal weight 1) and
  the candidate (goal weight 2). Ordinary A* runs on the same query.
- Primary outcome: paired geometric-mean operation ratio, candidate over
  original LLM-A*. Secondary: storage ratio, path-length ratio, and valid
  path counts. Preserve failures. Include sample SD and a 95% interval on
  log ratios for the confirmation split.

## Implementation boundary

`scripts/official_replay.py` mechanically follows the official source at
commit `9414ed894d774f71c36e8c0afd0e20e6033b95b1`, with model calls
and plotting removed so recorded responses can be reused. It retains the
official heap-pop operation count and `g`-dictionary storage count, including
blocked neighbors. The geometry is separately implemented with exact
closed-segment intersections. The differential checker matches the official
A* and LLM-A* search loops on all 89 evaluation cases for
operations, storage, and length, using saved waypoints. It replaces the
official Shapely collision function with the same segment predicate used by
the replay, so the check establishes search and counting parity conditional
on collision geometry. The 89-case Gemini study is not a Table 1 reproduction.

2026-11-20 update: a direct comparison with the teammate's Shapely-based
GPT-4o mini baseline exposed zero-length barrier handling. After skipping
those degenerate segments, replayed A* and original LLM-A* operation,
storage, and length match the archived implementation on all 1,000 cases.
The saved Gemini responses were replayed again with this correction; only
6 method/case operation counts changed in this 89-case experiment, leaving
the rounded conclusions unchanged. The GPT archive has no intermediate
waypoints and cannot yet confirm any improvement with GPT guidance.

If the held-out result is unfavorable or mixed, report it and test another
clearly motivated method. Do not relabel tuning cases as held-out results.

## Reproduce this experiment

The saved model responses and paired outcomes are tracked in
`experiments/goal_weight_holdout/`. Offline summarization needs only Python
3.11 standard-library packages. From the repository root:

```text
python scripts/compare_goal_weight.py --waypoints experiments/goal_weight_holdout/initial_waypoints.jsonl --output results/initial_paired_recomputed.jsonl
python scripts/compare_goal_weight.py --waypoints experiments/goal_weight_holdout/extension_waypoints.jsonl --output results/extension_paired_recomputed.jsonl
python scripts/compare_goal_weight.py --waypoints experiments/goal_weight_holdout/final_waypoints.jsonl --output results/final_paired_recomputed.jsonl
python scripts/summarize_goal_weight.py experiments/goal_weight_holdout/initial_paired.jsonl experiments/goal_weight_holdout/extension_paired.jsonl experiments/goal_weight_holdout/final_paired.jsonl
```

The first three commands regenerate results from saved waypoints. The summary
command needs no API key. To repeat the LLM calls, set `GEMINI_API_KEY`
locally and run `collect_waypoints.py` with the fixed offsets/strides/limits
above, `--prompt standard`, and model `gemini-3.5-flash-lite`. Model responses
can change even with temperature 0. The official-source differential checker
also needs the upstream repository at the pinned commit above.
