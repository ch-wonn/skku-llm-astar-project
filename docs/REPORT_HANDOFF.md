# 보고서 담당자 안내: 어떤 결과를 사용할까

**현재 기준 브랜치는 `improvement`입니다.** `main`에는 아래 통합 결과가
아직 없습니다. 이 문서와 링크된 재현 v2·개선 결과를 기준으로 작성하세요.
Git 커밋 순서를 보고서의 실험 순서로 옮기지 않아도 됩니다.

**제출용 개선 방법은 `start_visible_waypoint` (`--method improved`)입니다.**
GPT 결과에서 탐색량을 더 줄였지만 경로 길이가 조금 길어지는 교환이
있습니다. GPT 전체 결과를 본 뒤 설계했으므로 탐색적 성과라고
표기하세요. `weighted_waypoint`는 GPT 평가 전에 고정했던 비교 후보,
`selective_waypoint`는 이전의 더 엄격한 선택 규칙입니다.

## 보고서의 한 줄 흐름

1. **문제 발견:** 원본 LLM-A*는 목적지와 LLM 경유점까지의 거리를 같은
   비중으로 더한다. 경유점이 도움이 안 되는 지도에서는 탐색이 돌아갈 수
   있다.
2. **예비 개발:** Gemini로 목적지 비중과 경유점 비중을 탐색했다.
   `goal=2, waypoint=0.5`를 GPT 평가 전에 고정했다. 선택적 경유점
   규칙도 만들었으나 Gemini의 새 100개 사례에서는 가중 A* 대비 이득이
   확인되지 않았다. 이 숫자는 GPT 최종 표에 섞지 않는다.
3. **재현 기준:** 팀원이 GPT-4o mini로 같은 공개 지도 1,000개를
   standard(Few-Shot), CoT, RePE 각각 평가했다. 출처와 실패 사례는
   [재현 v2 안내](../baseline/README_REPRODUCTION_V2.md)에 있다.
4. **GPT 개선 비교:** 저장된 GPT 응답을 원본, `goal=2, waypoint=0.5`,
   LLM 없는 가중 A*, 선택적 경유점 방법에 **동일하게** 넣었다. 추가
   API 호출이나 프롬프트 수정은 없었다.
5. **결론:** 핵심 후보는 원본보다 탐색량을 크게 줄이고 경로 길이도
   소폭 줄였지만, LLM 없는 가중 A*보다 탐색량이 약간 많았다.
   선택적 경유점 방법은 GPT에서는 가중 A*보다 약 1~2% 적은 탐색량을
   보였지만 이득이 작고 Gemini에서는 확인되지 않았다. 두 한계를 모두
   적는다.

이후 [GPT 후속 탐색 실험](gpt_followup_search_experiments.md)을 추가했다.
경유점에 도달한 후 목표를 전환하는 시도는 탐색량이 늘어 기각했다.
출발점에서 보이는 경유점만 쓰는 새 규칙은 static weighted A* 대비
탐색 횟수를 약 3~5% 줄였지만 경로 길이를 약 0.2~0.5% 늘렸다.
**GPT 전체 결과를 이미 본 뒤 설계한 탐색적 후보**이므로 위의 주요
검증 결과와 구분해 적는다.

## 보고서용 핵심 숫자

모든 비율은 같은 문제에서 후보/대조군을 구한 뒤 기하평균한 값이다.
괄호의 성공 수는 1,000번의 GPT 시도 중 유효 경로를 얻은 사례다.
실패를 제외한 비교의 표본 크기를 반드시 함께 적는다.

| GPT 프롬프트 | 유효 사례 | 핵심 후보 / 원본: 탐색 횟수 | 저장 항목 | 경로 길이 | 핵심 후보 / LLM 없는 가중 A*: 탐색 횟수 |
|---|---:|---:|---:|---:|---:|
| standard | 878/1000 | 0.727 | 0.844 | 0.995 | 1.033 |
| CoT | 971/1000 | 0.739 | 0.854 | 0.997 | 1.022 |
| RePE | 944/1000 | 0.689 | 0.821 | 0.997 | 1.029 |

선택적 경유점 / LLM 없는 가중 A*의 탐색 횟수 비율은 standard 0.984,
CoT 0.984, RePE 0.987이다. 경유점 선택은 유효 사례 중 각각
165/878, 178/971, 160/944건에서만 작동했다. 정확한 95% 지도 단위
bootstrap 신뢰구간, 저장 항목과 길이의 부가 결과는
[GPT 개선 실험 기록](gpt_v2_improvement_evaluation.md)을 인용한다.

## 사용할 파일과 사용하지 않을 파일

| 용도 | 파일 |
|---|---|
| 재현 방법·실패 처리·성공률 | `baseline/README_REPRODUCTION_V2.md`, `baseline/experiment_results/reproduction_v2/summary/statistics.json` |
| GPT 기반 개선 방법·수치·한계 | `docs/gpt_v2_improvement_evaluation.md`, `experiments/gpt_v2_*_summary.json` |
| 개별 사례 확인 | `experiments/gpt_v2_*.jsonl` |
| 예비 실험을 설명할 때만 | `docs/next_improvement_experiment.md`, `docs/selective_waypoint_plan.md` |
| GPT 후속 알고리즘 시도 | `docs/gpt_followup_search_experiments.md`, `experiments/gpt_switch_standard_summary.json`, `experiments/gpt_relaxed_*_summary.json` |
| **최종 성능표에서 제외** | `baseline/experiment_results/gpt4omini_standard/`, Gemini 탐색 결과의 숫자 |

첫 GPT 실행 `gpt4omini_standard`는 1,000건 모두 경유점 배열 파싱에
실패했다. 재현 담당자가 수정해 새로 실행한 **`reproduction_v2`만**
정상 기준으로 사용한다.

## 구현과 아직 남은 확인

- `baseline/run_query.py --method weighted_waypoint`: 핵심 후보
  (`goal=2, waypoint=0.5`).
- `baseline/run_query.py --method selective_waypoint`: 선택적 경유점
  추가 실험의 이전 규칙.
- `baseline/run_query.py --method start_visible_waypoint`: GPT 후속 실험의
  제출용 개선 규칙. 탐색량이 줄지만 경로 길이가 조금 길어진다.
  `--method improved`는 같은 실행 방법의 별칭이다.
- `scripts/evaluate_gpt_v2.py`: 저장된 GPT 결과의 오프라인 비교.
  API 키가 필요 없다.
- 실제 GPT API를 통한 통합 개선 실행과 Ubuntu 22.04/Python 3.11
  빈 환경 설치·실행 검사는 아직 하지 않았다. 따라서 제출 전 검증 항목으로
  남겨둔다.

GPT 재현 결과는 Linux/Python 3.11에서 생성됐고 개선 비교는
Windows/Python 3.12에서 모든 후보를 다시 실행했다. 원본 수치도 일부
사례에서 경로/탐색 횟수의 작은 차이가 있어 같은 재실행 환경의 짝비교로
결론을 냈다. 원인을 모두 규명했다고 쓰지 않는다. 세 프롬프트는 같은
100개 지도에 대한 응답이므로 서로 독립적인 세 데이터셋도 아니다.

**논문의 가중 A*와 우리 대조군은 다르다.** 원 논문 Table 1의
Dynamic WA*는 초기 가중치 2에 0.99 감쇠를 쓴다. 여기서 말하는
static weighted A*는 가중치 2를 계속 유지한다. 논문에서는
GPT-3.5 Few-Shot LLM-A*의 탐색 비율이 57.39%, Dynamic WA*가
60.91%로 LLM-A*가 조금 앞섰다. 우리 GPT-4o mini 결과와 직접
같은 실험으로 취급하지 않는다.

## 추가 실험의 필요성

**저장된 GPT 응답만으로도 탐색 알고리즘의 후속 실험은 가능하다.**
위의 두 실험이 그런 예다. 프롬프트나 경유점 생성 자체를 개선하려면
새 API 호출이 필요하다. 이미 살펴본 GPT 결과에 맞춰 새 규칙을
설계했다면 결과를 탐색적으로 표기하고, 미공개 사례에서 확인된
성과라고 주장하지 않는다.
