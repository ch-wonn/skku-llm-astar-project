# 개선 실험 인계: 보고서 담당자용

## 최종 선택

제출용 개선 알고리즘은 `start_visible_waypoint` (`--method improved`)이다. 팀원의 **수정된 GPT-4o mini 재현 v2** 응답을 고정하고, 탐색 규칙만 바꿔 비교했다. 출발점에서 바로 갈 수 있고 우회가 지나치지 않은 LLM 경유점 하나를 선택한다. 적합한 점이 없으면 목적지 거리만 2배로 반영하는 가중 A*로 탐색한다. GPT 호출·프롬프트·파싱은 재현 v2와 같다.

이 방법은 GPT 전체 응답을 검토한 **뒤** 만든 탐색적 후보이다. 아래 신뢰구간은 저장된 지도에 대한 재표본 추출 결과이며, 미공개 지도에서의 성능을 보장하지 않는다. 장점은 탐색 횟수와 저장 항목 감소이고, 경로 길이에는 작은 비용이 있다.

## 왜 이 방법을 선택했는가: 실험 순서와 판단

1. **문제와 첫 가설.** 원본 LLM-A*는 목적지 거리와 현재 경유점 거리를 함께 휴리스틱에 넣는다. 경유점이 부적절하면 목표 방향과 다른 탐색이 생길 수 있다고 보았다. 경유점 수만 늘리는 실험은 호출·파싱 결과를 통제하기 어려워 주 개선 방향으로 채택하지 않았다.
2. **Gemini 예비 실험.** 팀의 GPT 재현이 완성되기 전에 Gemini 응답으로 목적지 가중치와 경유점 가중치를 살폈다. `goal=2, waypoint=0.5`를 GPT 비교 전에 고정했다. Gemini 결과는 방법을 고르는 자료이며 GPT 최종 표에 섞지 않는다. [초기 실험 기록](improvement_experiment_log.md), [가중치 실험](goal_weight_experiment_plan.md).
3. **공통 GPT 기준 확보.** 처음 GPT 실행(`gpt4omini_standard`)은 1,000건 모두 경유점 배열 파싱에 실패했다. 재현 담당자가 수정한 `reproduction_v2`의 standard/Few-Shot, CoT, RePE 각 1,000건만 사용했다. 유효 응답은 각각 878, 971, 944건이다. 실패를 성공으로 대체하지 않았다. [재현 v2 안내](../baseline/README_REPRODUCTION_V2.md).
4. **고정 가중치 후보 평가.** 저장된 **같은** GPT 응답과 지도에서 원본 LLM-A*, 일반 A*, LLM 없는 static weighted A* (`goal=2`), `weighted_waypoint` (`goal=2, waypoint=0.5`)를 비교했다. `weighted_waypoint`는 원본보다 탐색 횟수와 경로 길이를 줄였지만, LLM 없는 가중 A*보다 탐색 횟수가 2~3% 많았다. 따라서 단순 가중치 변경만 최종 개선으로 삼으면 LLM 경유점의 기여를 설명하기 어렵다. [첫 GPT 비교](gpt_v2_improvement_evaluation.md).
5. **엄격한 경유점 선택.** 출발점과 도착점 양쪽에서 직선으로 보이는 경유점만 허용하는 `selective_waypoint`를 시험했다. GPT에서는 static weighted A*보다 탐색 횟수가 약 1~2% 적었지만, Gemini의 별도 100개 사례에서는 이득이 확인되지 않았다. GPT 유효 사례에서 각각 165/878, 178/971, 160/944건만 경유점을 사용했다. 결론은 약한 근거로 취급했다.
6. **추가 탐색과 최종 선택.** 경유점 목표를 바꾸는 시점을 조정한 후보는 탐색 횟수가 늘어 기각했다. 엄격한 선택의 낮은 작동률을 개선하려고 **출발점에서 경유점이 보이는지**와 우회 거리만 확인하는 `start_visible_waypoint`를 시험했다. 경유점 사용은 621/878, 565/971, 506/944건으로 늘었다. static weighted A*보다 탐색 횟수는 약 3~5%, 저장 항목은 약 1~2% 적고, 경로는 약 0.2~0.5% 길었다. 이 교환을 명시하고 제출용으로 선택했다. [후속 시도와 기각 이유](gpt_followup_search_experiments.md).

## 최종 결과: 같은 지도에서의 짝비교

각 수치는 유효한 동일 사례에서 **최종 방법 / 대조군** 비율의 기하평균이다. 1보다 작으면 최종 방법이 해당 항목에서 작다. 지도 단위 bootstrap 95% 신뢰구간과 표본 표준편차는 [standard](../experiments/gpt_relaxed_standard_summary.json), [CoT](../experiments/gpt_relaxed_cot_summary.json), [RePE](../experiments/gpt_relaxed_repe_summary.json)의 `comparisons`에 있다. 세 프롬프트는 같은 1,000개 지도를 쓰므로 독립적인 데이터셋 셋으로 취급하지 않는다.

| 프롬프트 | 유효 사례 | 대조군 | 탐색 횟수 | 저장 항목 | 경로 길이 |
|---|---:|---|---:|---:|---:|
| standard | 878/1000 | 원본 LLM-A* | 0.6690 | 0.8192 | 0.9981 |
| standard | 878/1000 | static weighted A* | 0.9514 | 0.9776 | 1.0050 |
| standard | 878/1000 | 일반 A* | 0.3322 | 0.5559 | 1.0248 |
| CoT | 971/1000 | 원본 LLM-A* | 0.6981 | 0.8362 | 0.9969 |
| CoT | 971/1000 | static weighted A* | 0.9657 | 0.9841 | 1.0021 |
| CoT | 971/1000 | 일반 A* | 0.3347 | 0.5556 | 1.0225 |
| RePE | 944/1000 | 원본 LLM-A* | 0.6479 | 0.8029 | 0.9984 |
| RePE | 944/1000 | static weighted A* | 0.9678 | 0.9856 | 1.0032 |
| RePE | 944/1000 | 일반 A* | 0.3351 | 0.5548 | 1.0239 |

static weighted A* 대비 **탐색 횟수** 비율의 95% 신뢰구간은 standard [0.9385, 0.9648], CoT [0.9535, 0.9788], RePE [0.9555, 0.9806]이다. 최종 방법의 유효 사례 경로는 모두 검증을 통과했다. GPT 응답 자체가 실패한 건수는 여전히 실패로 남는다.

**대조군 구분:** 여기의 static weighted A*는 목적지 거리 가중치 2를 고정한다. 논문 Table 1의 Dynamic WA*는 초기 2에서 0.99씩 감쇠한다. 같은 알고리즘으로 이름 붙이지 않는다.

## 코드·자료·실행

- 실시간 단일 지도: `python baseline/run_query.py --method improved --prompt standard --query QUERY.json --output RESULT.json`. 외부에서 설정한 `OPENAI_API_KEY`가 필요하다. 키를 제출물에 넣지 않는다.
- 저장 응답 재계산: 먼저 `scripts/evaluate_gpt_v2.py`가 원본·가중치·A* 비교 파일을 만들고, 그 결과를 `scripts/evaluate_relaxed_gate.py --base-results ...`에 입력해 **최종 방법** 결과를 만든다. 정확한 명령은 [루트 README](../README.md)에 있다. API 호출은 없다.
- 제출용 구현: [개선 탐색](../baseline/improved_search.py), [실행 진입점](../baseline/run_query.py), [경유점 선택 규칙](../scripts/selective_waypoint.py). 각 사례는 `experiments/gpt_relaxed_*.jsonl`에 있다.
- 원본 재현의 방법·API 실패 수·환경은 [재현 v2 안내](../baseline/README_REPRODUCTION_V2.md)와 `baseline/experiment_results/reproduction_v2/summary/statistics.json`에 있다. `gpt4omini_standard`와 Gemini 숫자는 최종 성능표에서 제외한다.

## 검증 범위와 남은 확인

Ubuntu 22.04/Python 3.11 CI에서 `pip install -r requirements.txt`, `pip check`, 재현과 개선의 저장 응답 검사가 통과했다. 실제 GPT API 통합 실행은 키 없이 검사할 수 없었다. GPT 응답은 Linux/Python 3.11에서 수집했고 개선 후보의 검색 지표는 Windows/Python 3.12에서 **모든 후보를 같이 다시 실행**해 짝비교했다. 일부 사례에서 Linux 원본 기록과 재실행 사이에 작은 차이가 있다. 그 원인을 모두 규명했다고 주장하지 않는다.

과제 공지에는 평가 환경에서 API 키를 제공하지 않고 제출물에 개인 키를 넣지 말라고 적혀 있다. 최근 FAQ에는 baseline의 LLM 연결 방식과 README 실행 지시를 따른다고 되어 있지만, **실행에 쓸 인증 정보를 누가 어떻게 제공하는지는 명시하지 않는다**. 현 코드의 실시간 LLM 방법은 `OPENAI_API_KEY`가 없으면 실패한다. 팀은 제출 전에 조교에게 평가 연결 방법을 확인해야 한다. 저장 응답 재계산은 키 없이 가능하지만, 미공개 지도 실시간 실행을 대체하지 않는다.
