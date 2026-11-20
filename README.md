# LLM-A* reproduction and improvement project

## Current reproduction status

The first 1,000-case GPT-4o mini run in
`baseline/experiment_results/gpt4omini_standard/` is **not a valid LLM-guided
reproduction baseline**. All recorded responses lacked a waypoint array; a
newline stop condition and the original parser's silent default resulted in
endpoint-only targets. Preserve those logs for debugging, but do not use those
numbers as evidence of LLM waypoint benefits.

The corrected CPU/API reproduction workflow is documented in
[baseline/README_REPRODUCTION_V2.md](baseline/README_REPRODUCTION_V2.md).
Installing this update alone does not constitute completed experiments.
Completion is established by the generated manifests, case records and statistics.

## Evaluation environment and install

- Target: Ubuntu 22.04, Python 3.11, no GPU.
- In a fresh Python 3.11 environment, the only package installation required is:

```bash
pip install -r requirements.txt
```

The reproduction scripts import this submission's `baseline/llmastar` source
directly. Do not install the upstream Git package over the submitted code.
The optional local Llama3 backend still requires its own GPU packages; it is not
used by this GPT/API CPU workflow. Other OpenAI-compatible hosted models may be
selected through `OPENAI_MODEL` and, when needed, `OPENAI_API_BASE`.
This does not claim arbitrary local LLM backends have been implemented or tested.

## Offline checks

```bash
python baseline/test_reproduction.py
python baseline/run_reproduction.py --validate-only --require-public-count --out baseline/experiment_results/reproduction_v2/astar
```

## API configuration

Set `OPENAI_API_KEY` externally. No key is bundled or hard-coded.
`OPENAI_MODEL` defaults to `gpt-4o-mini`.
The evaluator must supply an authorized API connection for live LLM execution;
missing credentials cause an explicit error, not fabricated or cached results.
The teaching staff's API-key provisioning procedure should be confirmed separately.

## Reproduction entry points

From the repository root, run A* once and each of `standard`, `cot`, `repe` on
the identical public dataset. Full commands, smoke checks and statistics are in
the linked reproduction README. The original prompts and search equations are
unchanged. API termination and parse failure handling are corrected and disclosed.

For an unseen query using the baseline schema:

```bash
python baseline/run_query.py --method astar --query /path/to/query.json --output /path/to/astar.json
python baseline/run_query.py --method llm --prompt standard --query /path/to/query.json --output /path/to/llm.json
```

Input: a JSON object containing `start`, `goal`, `range_x`, `range_y`,
`horizontal_barriers`, `vertical_barriers`. The output is the baseline result
dictionary (`operation`, `storage`, `length`, plus `llm_output` for LLM-A*).
Diagnostics are separate `.audit.json` files. The underlying
`searching(query, filepath)` method interface is retained. No particular map
count is required for single-query execution.

## Scope and team integration

The supplied update covers the reproduction baseline. It does **not** implement
or claim completion of the team's improved method or final report. Before final
submission the team must add the improved method's exact execution instructions,
include any additional dependencies in this root requirements.txt, and retest
the combined code in a clean Python 3.11 CPU environment using that file alone.

The final team submission includes the ACL-format report and
`TeamName_CodeFile.zip` with code, README and requirements. Each student separately
submits their own contribution report of at least half a page without sharing it
with teammates. Follow the course notices for peer review and response submissions.

## Attribution

- Paper: Meng et al., LLM-A*, https://arxiv.org/abs/2407.02511
- Official code/data: https://github.com/SilinMeng0510/llm-astar
- Baseline revision: `baseline/UPSTREAM_COMMIT.txt`; original MIT license: `baseline/LICENSE`.
- Course: SWE3011 assignment notice and subsequent Canvas clarifications.

Legacy `scripts/reproduce.py`, `scripts/summarize.py`, `baseline/run_dataset.py`
and old README files are historical scaffolding, not the current evaluation workflow.
