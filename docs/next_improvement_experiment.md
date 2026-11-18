# Heuristic ablation and local confirmation

This note separates an **exploratory** analysis on already-seen cases from a
subsequently completed **confirmation** run. The exploratory analysis needs
no new LLM calls. The user ran the confirmation locally with their Gemini
key; no key is stored in this repository.

## Why examine another direction?

The original LLM-A* priority is `g + d_goal + d_waypoint`. Our first candidate
was `g + 2*d_goal + d_waypoint`. To determine whether its gain comes from
LLM-proposed waypoints or merely extra goal bias, compare these controls on
the identical 89 saved Gemini responses:

| Rule | Operations / original | Storage / original | Path length / original |
| --- | ---: | ---: | ---: |
| Original `1, 1` | 1.000 | 1.000 | 1.000 |
| Goal weight 1.5, waypoint 1 | 0.975 | 0.960 | 1.003 |
| Goal weight 2, waypoint 1 (first candidate) | 0.780 | 0.842 | 1.004 |
| Goal weight 3, waypoint 1 | 0.620 | 0.756 | 1.009 |
| Goal weight 2, waypoint 0.5 | 0.707 | 0.794 | 0.992 |
| Goal weight 2, waypoint 0 | 0.706 | 0.798 | 0.997 |
| Weighted A* without LLM, goal weight 2 | 0.704 | 0.798 | 0.997 |

All entries are paired geometric means, with valid paths in 89/89 cases for
every rule. The waypoint-0 rule retains the LLM-A* target-switching code;
the last row is a true no-LLM weighted A* control. Their five metric
differences among 89 cases show why both are included.

The `2, 0.5` rule improves the first candidate on the already-seen cases:
operation ratio 0.906, storage ratio 0.943, and length ratio 0.987. However,
its operation ratio against true no-LLM weighted A* is 1.003. Thus these
cases do **not** establish that LLM waypoints cause an operation reduction.
Weight 3 further reduces operations but lengthens paths. Because these
comparisons were made after examining the 89 cases, none may be presented as
a fresh held-out performance result or used to replace the first candidate
without a new confirmation set.

The tracked aggregate statistics are in
`experiments/heuristic_ablation/summary_89.json`; the per-case output can
be regenerated with the command below.

To reproduce this ablation without an API key, run from the repository root:

```powershell
& 'C:\Users\dkdis\anaconda3\python.exe' scripts/ablate_heuristic_weights.py experiments/goal_weight_holdout/initial_waypoints.jsonl experiments/goal_weight_holdout/extension_waypoints.jsonl experiments/goal_weight_holdout/final_waypoints.jsonl --output results/ablation_89.jsonl --summary-output results/ablation_89_summary.json
```

## Fixed next experiment: 100 new start/goal pairs (completed)

Before making any new calls, fix the candidate to `goal_weight=2` and
`target_weight=0.5`. Use pair index 1 from each of the 100 maps, which was
not used in the 89-case analysis. The chosen model remains
`gemini-3.5-flash-lite`, the prompt remains the pinned official GPT Few-Shot
template (`standard`), and temperature remains 0. Run original LLM-A*, the
first candidate, the new candidate, and true weighted A* on each saved
response. Report failures and path validity for all 100 selected cases.
Primary outcome: paired geometric-mean operation ratio of the new candidate
over original LLM-A*. Secondary outcomes: storage, length, and comparisons
with the first candidate and true weighted A*. Report sample SD and a 95%
interval. Do not change weights after viewing the 100 results.

The 100 local Gemini calls completed with 100 parseable responses and no
duplicate case IDs. All seven methods produced valid paths in all 100 cases.
The model calls took 966 seconds in total (9.66 seconds on average), plus
the configured inter-call delay; offline analysis of all methods took about
10 seconds. The saved responses and summary are tracked in
`experiments/confirmation_pair1/`.

| Method | Operations / original | Storage / original | Path length / original |
| --- | ---: | ---: | ---: |
| Original LLM-A* | 1.000 | 1.000 | 1.000 |
| Goal 2, waypoint 1 | 0.730 | 0.833 | 1.012 |
| Goal 2, waypoint 0.5 | 0.626 | 0.775 | 0.999 |
| No-LLM weighted A*, goal 2 | 0.578 | 0.749 | 0.989 |

The new candidate improved on our first candidate: paired operation ratio
0.858 (95% log-ratio interval 0.780-0.943), storage 0.930 (0.894-0.968),
length 0.987 (0.981-0.993). But compared with **no-LLM weighted A***, the
new candidate was worse: operations 1.084 (1.015-1.158), storage 1.034
(1.007-1.063), length 1.010 (1.003-1.017). All ratios are geometric means.
The confirmation therefore does not support an LLM-specific performance
benefit from these waypoint weights, despite improvement relative to the
published LLM-A* heuristic. This is a critical limitation for the report.

On this computer, from the repository root in PowerShell (the local `.env`
already supplies the private key; never paste it into commands or Git):

```powershell
& 'C:\Users\dkdis\anaconda3\python.exe' scripts/collect_waypoints.py --dataset data/environment_50_30.json --output results/confirm_pair1_waypoints.jsonl --prompt standard --offset 1 --stride 10 --limit 100 --delay 4
& 'C:\Users\dkdis\anaconda3\python.exe' scripts/ablate_heuristic_weights.py results/confirm_pair1_waypoints.jsonl --output results/confirm_pair1_ablation.jsonl --summary-output results/confirm_pair1_summary.json
```

The collector resumes an interrupted run with the same output file by
skipping recorded cases. It also records failed calls; **recorded failures
are skipped on rerun**, so inspect `failed_calls` in the summary. If there
are failures, keep the file and seek help rerunning only those cases rather
than deleting evidence. The analysis is offline and needs no API key.

## Full paper-sized run, if the team chooses it

The newer office-hour notice says no fixed sample count is required, but
the FAQ says to keep the paper's setup and count when claiming a Table 1
reproduction. Therefore use **1,000 start/goal pairs per prompt** for a
direct Table 1 reproduction. The improvement can be compared on the same
1,000 saved Few-Shot responses, with no extra LLM calls for the alternative
search rules. Coordinate with the reproduction teammate to avoid paying for
duplicate calls. The other two LLM-A* prompt rows, CoT and RePE, each need
their own 1,000 responses if the team reproduces all three prompt rows.

Do not make 1,000 additional API calls solely to promote the current
candidate: the confirmation already shows that no-LLM weighted A* can be
stronger. If the team needs a full Few-Shot collection for its reproduction,
seed it with the 100 pair-1
responses so they are not called again, then resume to 1,000:

```powershell
Copy-Item results/confirm_pair1_waypoints.jsonl results/full_standard_waypoints.jsonl
& 'C:\Users\dkdis\anaconda3\python.exe' scripts/collect_waypoints.py --dataset data/environment_50_30.json --output results/full_standard_waypoints.jsonl --prompt standard --all --delay 4
& 'C:\Users\dkdis\anaconda3\python.exe' scripts/ablate_heuristic_weights.py results/full_standard_waypoints.jsonl --output results/full_standard_ablation.jsonl --summary-output results/full_standard_summary.json
```

The full run can take many hours and may need multiple sessions depending
on account quota and response latency. Check that `source_cases` is 1,000,
`failed_calls` is reported, and paths are valid before using any averages
in the final report. This code was run locally with Python 3.12; the team's
submission still needs a clean Ubuntu 22.04/Python 3.11 check.
