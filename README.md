# LLM-A* reproduction and improvement project

## 보고서 작성자는 여기부터

**최종 개선 방법과 실험 인계는 이 저장소에 있습니다.** 보고서의 실험
흐름과 사용할 수치는 [보고서 담당자 안내](docs/REPORT_HANDOFF.md)를
먼저 보세요. Gemini 결과는 방법 개발을 위한 예비 실험이고, 최종
성능 비교는 팀원의 수정된 GPT-4o mini `reproduction_v2` 응답을
사용합니다. Git 커밋 순서와 오래된 결과 폴더를 보고 최종 성능표를
만들지 마세요. 저장된 응답을 이용한 추가 알고리즘 시도는
[후속 탐색 실험 기록](docs/gpt_followup_search_experiments.md)에 있습니다.
**제출용 개선 방법은 `start_visible_waypoint`로 고정했습니다.**
`--method improved`는 같은 방법의 짧은 별칭입니다.

## Current reproduction status

The first 1,000-case GPT-4o mini run in
`baseline/experiment_results/gpt4omini_standard/` is **not a valid LLM-guided
reproduction baseline**. All recorded responses lacked a waypoint array; a
newline stop condition and the original parser's silent default resulted in
endpoint-only targets. Preserve those logs for debugging, but do not use those
numbers as evidence of LLM waypoint benefits.

The corrected CPU/API reproduction workflow is documented in
[baseline/README_REPRODUCTION_V2.md](baseline/README_REPRODUCTION_V2.md).
The completed GPT-4o mini run evaluated 1,000 cases under each of standard,
CoT and RePE; saved manifests, per-case results and statistics are in
`baseline/experiment_results/reproduction_v2/`. The paired improvement
analysis, including the LLM-free control, is in
[docs/gpt_v2_improvement_evaluation.md](docs/gpt_v2_improvement_evaluation.md).

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

The [Ubuntu 22.04 / Python 3.11 CPU check](https://github.com/ch-wonn/skku-llm-astar-project/actions/runs/44775360474)
passed dependency installation, `pip check`, reproduction tests, and the
improvement test using saved responses. It does not make a live API request.

```bash
python baseline/test_reproduction.py
python baseline/test_improved_search.py
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
python baseline/run_query.py --method weighted_waypoint --prompt standard --query /path/to/query.json --output /path/to/weighted_waypoint.json
python baseline/run_query.py --method selective_waypoint --prompt standard --query /path/to/query.json --output /path/to/selective_waypoint.json
python baseline/run_query.py --method start_visible_waypoint --prompt standard --query /path/to/query.json --output /path/to/start_visible_waypoint.json
python baseline/run_query.py --method improved --prompt standard --query /path/to/query.json --output /path/to/improved.json
```

Input: a JSON object containing `start`, `goal`, `range_x`, `range_y`,
`horizontal_barriers`, `vertical_barriers`. The output includes `operation`,
`storage`, `length` and `llm_output` for the LLM methods. All improvement
methods use the same GPT call. `weighted_waypoint` keeps all filtered waypoints
with goal weight 2 and waypoint weight 0.5. `selective_waypoint` chooses at
most one eligible waypoint and otherwise uses the LLM-free weighted A*
priority. `start_visible_waypoint` relaxes its visibility test to the first
leg and is the selected submission method. It has a measured path-length
trade-off and was designed after viewing the saved GPT results, so its
published results are exploratory. The LLM-free control here uses
a **fixed** goal weight of 2; the paper's Table 1 uses a distinct Dynamic WA*
with a 0.99 weight decay. Their audit files record path validity; the gate audits also
records the original and selected waypoints. Diagnostics are
separate `.audit.json` files. The underlying
`searching(query, filepath)` method interface is retained. No particular map
count is required for single-query execution.

## Scope and team integration

The improvement candidates are implemented in `baseline/improved_search.py`
and checked against the offline replay on saved GPT responses. The selected
comparison is `start_visible_waypoint` versus the original LLM-A*, ordinary
A*, and static weighted A*. The earlier `weighted_waypoint` and
`selective_waypoint` experiments explain how the final method was chosen.
Recompute the final comparison from saved GPT responses with two steps:

```bash
mkdir -p results/recomputed
for prompt in standard cot repe; do
  python scripts/evaluate_gpt_v2.py \
    --results-root baseline/experiment_results/reproduction_v2 \
    --prompt "$prompt" \
    --output "results/recomputed/gpt_v2_${prompt}.jsonl" \
    --summary-output "results/recomputed/gpt_v2_${prompt}_summary.json"
  python scripts/evaluate_relaxed_gate.py \
    --results-root baseline/experiment_results/reproduction_v2 \
    --base-results "results/recomputed/gpt_v2_${prompt}.jsonl" \
    --prompt "$prompt" \
    --output "results/recomputed/gpt_relaxed_${prompt}.jsonl" \
    --summary-output "results/recomputed/gpt_relaxed_${prompt}_summary.json"
done
```

The first command computes the earlier candidate and the common controls;
the second computes the **selected final method**. These steps make no API
calls. The live improved
method requires the same GPT connection as the baseline; the automated CPU
check does not verify a live GPT call.

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
