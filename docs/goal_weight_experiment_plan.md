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
closed-segment intersections; it still requires differential checking
against the installed official package before any final Table 1 claim.

If the held-out result is unfavorable or mixed, report it and test another
clearly motivated method. Do not relabel tuning cases as held-out results.
