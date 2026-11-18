# Improvement experiments: waypoint guidance

Status: offline diagnostic experiments completed on 2026-11-18; actual LLM
waypoint experiments and final method selection remain pending. See
`improvement_experiment_log.md` for results.

## Research question

Can a small correction to waypoint handling make LLM-A* more reliable or
efficient without a large path-length penalty on unseen maps?

The paper's LLM-A* adds distance to the current LLM waypoint to A*'s
`g + h` priority. It changes targets when a waypoint appears among an expanded
node's **neighbors**, before collision checking. The implementation can
therefore advance the target even when that motion is blocked. This is a
source-level observation and a hypothesis for experiments, not yet evidence
that it changes measured performance.

## Proposed improvement to test

First candidate: use the same LLM-produced waypoint list as the original
method, but advance to the next waypoint only when the search actually
expands the current waypoint, rather than merely finding it as a neighbor.
The model-free proxy experiment did **not** show a performance improvement,
so this is not yet the selected final method. For robustness, also consider:

1. Parse and validate each coordinate. Discard non-finite, out-of-bounds,
   blocked, repeated, and identical consecutive points. Always retain the
   input start and goal.
2. Keep the original guidance strength (`alpha = 1`) for the main comparison.
   A diagnostic `alpha = 0.5` run shortened paths but increased search work;
   it was not selected as a clear improvement.
3. If the LLM call fails or returns no usable intermediate points, fall back
   to goal-directed A*. Record this case explicitly. A fallback may improve
   completion but must not be counted as an LLM-guided success.

Use the original map representation, 8 motions, collision rule, and
`searching(query, filepath)` entry point. Do not tune rules to individual
public map IDs or start/goal pairs.

## Fair comparison

- Run A*, the reproduced LLM-A*, and each improved variant on the **same**
  map/start/goal cases. Reuse the same stored LLM response across methods so
  model randomness and API cost do not confound the search comparison.
- Reproduce the LLM-A* Table 1 setting with the paper's 100 maps of size
  50 x 30 and 10 start/goal pairs per map (1,000 cases), following the later
  FAQ. Label smaller development runs as exploratory.
- Check a small set of new maps or held-out cases for obvious overfitting.
  Fix their selection before looking at improvement results.
- Preserve failures and invalid paths in the denominator. Report operation
  and storage ratios to A*, relative path length, collision-free valid-path
  ratio, and paired sample count. Follow the paper's geometric-mean ratio
  for Table 1 comparison. Also report standard deviations and 95% confidence
  intervals, with the calculation method stated.
- Report wall-clock time and LLM calls separately. A reduction in search
  operations is not automatically a reduction in end-to-end time or cost.
- Keep model name/version, prompt, temperature, map source, code revision,
  dependency versions, failures, and exact commands with the results.

## Required implementation checks

1. Minimal maps: empty map, one barrier with a gap, blocked waypoint,
   malformed LLM output, start equals goal, and no valid path.
2. Check every returned path segment against the same barrier-intersection
   rule used for search; the upstream return value's `length` alone does not
   prove path validity.
3. Verify the final code and clean installation on Ubuntu 22.04 / Python
   3.11 / CPU with only `pip install -r requirements.txt`.
4. Collect development-model responses independently, using a local API key
   excluded from Git. Then replay the saved responses through both search
   variants and fill a paired results table. The reproduction teammate's work
   is not a prerequisite for this development experiment.

The standalone `scripts/waypoint_search.py` is an **offline prototype**. Its
operation and storage accounting differs from the official implementation;
its smoke-test numbers are only for debugging and must not be reported as
paper-comparable results. Align measurement in the final paired runner before
making performance claims.

## Sources

- Meng et al., *LLM-A*: Large Language Model Enhanced Incremental Heuristic
  Search on Path Planning*, Algorithm 1 and Table 1:
  https://arxiv.org/pdf/2407.02511
- Official implementation, inspected at commit
  `9414ed894d774f71c36e8c0afd0e20e6033b95b1`:
  https://github.com/SilinMeng0510/llm-astar
- Course assignment PDF and the later Canvas FAQ and office-hour notices.
