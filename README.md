# LLM-A* reproduction project (work in progress)

This repository contains early SWE3011 Introduction to AI (Fall 2026) reproduction work. An 89-case Gemini waypoint experiment has compared ordinary A*, original LLM-A*, and one candidate search priority; it is documented in [the goal-weight experiment plan](docs/goal_weight_experiment_plan.md) and [experiment log](docs/improvement_experiment_log.md). The full 1,000-case Table 1 reproduction and integrated final report remain team work.

## Sources and scope

- Assignment: `SWE3011_41 Assignment Notice.pdf` and the two Canvas clarification posts (course materials; do not redistribute without permission).
- Paper: Meng et al., [LLM-A*: Large Language Model Enhanced Incremental Heuristic Search on Path Planning](https://arxiv.org/pdf/2407.02511), Table 1 and §§4.1–4.4.
- Official MIT-licensed [implementation and dataset](https://github.com/SilinMeng0510/llm-astar), inspected at commit `9414ed894d774f71c36e8c0afd0e20e6033b95b1`. This project invokes the official package; it does not claim ownership of that code.

The paper uses 100 maps of size 50 × 30, each with 10 start/goal pairs (1,000 cases), with GPT-3.5 Turbo or Llama3 and Few-Shot/CoT/RePE prompts. Table 1 reports operation ratio, storage ratio, relative path length, and valid path ratio. The course subsequently clarified that only the **LLM-A*** rows need reproduction and that the model may differ. One notice says the sample count is flexible, while a later FAQ says to preserve the paper's count and setup; the default full run therefore uses all 1,000 cases. Smaller runs must be labelled exploratory and cannot be presented as a direct Table 1 reproduction.

## Environment

Use Python 3.11 on a machine with network access, matching the evaluation notice. The official repository pins the legacy `openai==0.27.2` interface and imports its Llama3 dependencies even for GPT runs. `requirements.txt` installs its source at the inspected commit and its declared dependencies. This installation has **not yet been verified end to end** in a clean Ubuntu 22.04 environment. The saved-waypoint improvement analysis uses only the Python standard library.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

Download the public dataset from the same official commit, preserving the file name:

```bash
mkdir -p data
curl -L https://raw.githubusercontent.com/SilinMeng0510/llm-astar/9414ed894d774f71c36e8c0afd0e20e6033b95b1/dataset/environment_50_30.json -o data/environment_50_30.json
python scripts/reproduce.py --dataset data/environment_50_30.json --validate-only
```

On Windows PowerShell, create the folder with `New-Item -ItemType Directory -Force data` and use `curl.exe -L ... -o data/environment_50_30.json` with the same URL above.

Check the expected 100 maps and 1,000 pairs printed by validation before a full experiment. The script accepts any map with the official `range_x`, `range_y`, barrier, and `start_goal` fields; it does not hard-code individual maps.

## Baseline run

Set `OPENAI_API_KEY` in your shell or an untracked local environment file. Never put a key in code, a command argument, Git, or the submission ZIP. The original `ChatGPT` class uses `openai.Completion` with `gpt-3.5-turbo-instruct` for waypoints, so the current runner uses the **original GPT connection and model**, not the course's eventual GPT-4o mini evaluation model. Updating this connection while preserving the official input/output contract is an outstanding team task.

```bash
# PowerShell, in your own local session:
$env:OPENAI_API_KEY = '<your key>'
python scripts/reproduce.py --dataset data/environment_50_30.json --prompt standard --output results/baseline_standard.jsonl
python scripts/summarize.py results/baseline_standard.jsonl
```

`--prompt` also accepts `cot` and `repe`. The runner writes one JSON line per map/start-goal case, with the original query, A* and LLM-A* return dictionaries, and any failure. It copies each query before calling the upstream methods because both mutate `range_x` and `range_y`. Output images go to `results/plots/`; raw outputs are ignored by Git by default. A failure is recorded, not silently omitted. For a labelled smoke run use `--limit 1`; remove it for the full 1,000 cases. The summary script reports the successful paired-case ratios, their geometric means (for comparison with Table 1), sample standard deviations, and 95% normal-approximation confidence intervals for arithmetic means. `successful_call_ratio_percent` is **not** a verified collision-free path ratio; validity needs a separate path checker because the official return value does not contain the path. These statistics are descriptive and must be reviewed before use in the report; failure rates, model version, prompt, sample count, and environment must also be reported.

## Required next work

1. Verify install and run one case with a valid API key; record exact package versions and any upstream errors.
2. Preserve the baseline's callable `searching(query, filepath)` input/output contract on unseen maps while adapting the designated model connection. Test this with a hidden-style held-out query.
3. Run the complete, paired 1,000-case Table 1 setting or document any deviation and the conflicting Canvas sample guidance. Never invent missing cases or results.
4. Integrate the tested goal-weight candidate with the team's final reproduction code, retain its measured trade-offs, and make the submission README match the final code.
5. Have each student keep a factual, separate contribution record; the assignment requires an individual report of at least half a page. Do not share individual contribution reports between teammates.

## Attribution

The paper and official code/data are by Meng et al. The runner and summary scripts in this repository are original project scaffolding. Report authors must cite external code and describe only work and experiments actually performed.
