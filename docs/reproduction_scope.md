# Gemini reproduction scope and handoff

Agreed development model: `gemini-3.5-flash-lite` through the Gemini API.
The research paper used GPT-3.5 Turbo and Llama3 8B, so these are **model
substitution** experiments. The course FAQ allows a substitute model but
asks that the Table 1 setup and sample count be kept. The later office-hour
notice limits required reproduction to the LLM-A* rows.

For one substitute model, reproduce the three LLM-A* prompting conditions:

| Paper label | Local option | Official prompt template |
| --- | --- | --- |
| Few-Shot | `standard` | 5 examples |
| Chain of Thought | `cot` | 3 examples |
| Recursive Path Evaluation | `repe` | 3 examples |

Use all 100 maps and 10 start/goal pairs each (1,000 cases per prompt) for
direct Table 1 comparison, if the API quota permits. A* must be run on the
same cases to form the operation, storage, and length ratios. The later
clarification does not require reproducing the LLM-only or Dynamic WA* rows.
Preserve every failed response and invalid path in the denominator. Report
geometric-mean ratios as in the paper, plus sample count and uncertainty.

The improvement experiment should use **the same saved model responses** as
the corresponding original LLM-A* condition. The simplest main comparison
can focus on Few-Shot, with CoT and RePE as robustness checks if time and
quota allow. Keep the model, prompt, temperature, output cap, source commit,
map set, and failures in the report.

The current `collect_waypoints.py` stores model responses for this purpose.
`waypoint_search.py` is an early standalone prototype with different metric
counting. The later `official_replay.py` follows the published search loop;
after correcting zero-length barrier handling, its original A*/LLM-A*
operation, storage, and length matched the teammate's archived implementation
on all 1,000 public cases. Only results from that aligned replay may be used
for a paper-style performance comparison.

## 2026-11-20 GPT baseline integration status

The teammate's merged GPT-4o mini run completed 1,000 public cases, but its
archived responses contain no parseable waypoint lists and every resulting
LLM-A* output has only start and goal. The original newline stop setting
and silent parser fallback explain this. It is an execution and path-validity
record, **not** a valid LLM waypoint reproduction. A connection fix is on
the `improvement` branch; it passed an offline mock but requires a new GPT
pilot and then a fresh 1,000-case run with the key holder. Use a new output
directory so the archived run and provenance remain intact. The fixed-run
instructions are in `baseline/README_DATASET.md`.
