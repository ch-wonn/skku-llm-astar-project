# 수정 재현 실행 안내

## 범위와 상태

Table 1 중 LLM-A*의 standard(Few-shot), CoT, RePE를 같은 공개 1,000개에서
평가하고 A*와 비교한다. GPT-4o mini 사용은 과제의 모델 교체 허용에 따른다.
LLM-only는 추가 공지에 따라 범위 밖이다. 이 README를 추가한 것만으로
실험 완료를 주장하지 않는다. 실제 완료 수와 실패는 결과 파일로 보고한다.

기존 `experiment_results/gpt4omini_standard`는 1,000건 모두 경유점 배열
추출에 실패한 이력이다. 삭제하거나 새 결과로 덮어쓰지 않는다.
해당 실행은 목표 경유점이 항상 goal이므로 `f=g+2*distance_to_goal` 형태였다.
기존 숫자를 LLM 경유점의 효과로 해석하거나 새 정상 baseline과 섞지 않는다.

## 수정 범위

- API: 기존 ChatCompletion 연결을 유지하고 newline stop을 제거한다.
- 모델·temperature=0·최대 출력 1000토큰을 기록한다. 원본 프롬프트 텍스트는 수정하지 않는다.
- `finish_reason=length` 등 미완료 응답은 명시적인 실패로 처리한다.
- 파서는 수치 좌표 배열을 엄격하게 읽고 실패 시 가짜 좌표를 반환하지 않는다.
- 파싱 실패 시 자동 A* fallback이나 재시도는 수행하지 않는다. 실패도 전체 분모에 포함한다.
- 원본의 장애물 필터, endpoint 삽입, 휴리스틱, OPEN 갱신 등 검색 로직은 유지한다.
- 파싱 전후 목록, 실제 타깃 전환, 최종 경로 유효성을 별도로 기록한다.
- Llama3 의존성은 해당 백엔드 생성 시에만 import하도록 바꿔 GPT 경로에서 GPU 패키지가 필요 없게 한다.
- 이 응답 처리/실패 정책 차이는 보고서에 명시한다. 제안 개선 알고리즘의 성과로 주장하지 않는다.

## 환경

평가 목표: Ubuntu 22.04, Python 3.11, CPU. 이미 Python 3.11 가상환경이
준비되어 있다고 가정한다. 프로젝트 최상위에서 패키지 설치는 한 줄뿐이다.

```bash
pip install -r requirements.txt
python -m pip check
python baseline/test_reproduction.py
```

이 업데이트는 작성 환경의 Linux/Python 3.11.18에서 새 가상환경 설치와
실제 탐색+모의 API 검사를 통과했다. 작성 환경 OS는 Debian 13이므로
사용자 측 Ubuntu 22.04 검증을 대체하지 않는다. 실 API 검사는 별도이다.

## API 설정

```bash
read -s -p "OpenAI API key: " OPENAI_API_KEY
export OPENAI_API_KEY
echo
export OPENAI_MODEL="gpt-4o-mini"
```

키를 코드, README, ZIP, Git에 넣지 않는다. 평가 시 외부 키 주입 방식은
조교에게 확인한다. 키 없이 성공 결과를 만들어내지 않는다.

## 데이터와 A*

```bash
python baseline/run_reproduction.py --validate-only --require-public-count --out baseline/experiment_results/reproduction_fresh/astar
python baseline/run_reproduction.py --method astar --require-public-count --out baseline/experiment_results/reproduction_fresh/astar
```

기본 데이터는 `baseline/dataset/environment_50_30.json`이다.
`--dataset`으로 같은 스키마의 다른 데이터도 지정할 수 있다.
`--require-public-count`는 공개 실험의 개수 검사일 뿐 알고리즘 입력 제한이 아니다.

## 세 조건의 소규모 검사

`--limit 10`은 원본 순서의 0,100,...,900번 문제를 고른다. 서로 다른
지도에 걸쳐 검사하며, 이후 full run은 나머지 모든 문제를 실행한다.

```bash
python baseline/run_reproduction.py --method llm --prompt standard --limit 10 --require-public-count --out baseline/experiment_results/reproduction_fresh/standard
python baseline/run_reproduction.py --method llm --prompt cot --limit 10 --require-public-count --out baseline/experiment_results/reproduction_fresh/cot
python baseline/run_reproduction.py --method llm --prompt repe --limit 10 --require-public-count --out baseline/experiment_results/reproduction_fresh/repe
```

전체 실행 전 api_calls/의 finish_reason과 response_text,
cases/의 error_type 및 waypoint_audit를 확인한다.
파싱 성공, 중간 경유점, 탐색 목표 전환 기록을 함께 검사한다.
개별 사례에 경유점이 없다는 사실만으로 실패로 분류하지 않는다.
출력 한도 초과는 실패로 보존하며, 모든 사례의 성공을 요구하지 않는다.
인증·호출 제한·연결 오류는 원인을 확인한 뒤 재개한다.
기존 check_smoke.py는 실패 및 None 처리 문제로 사용하지 않는다.

## 전체 실행

```bash
python baseline/run_reproduction.py --method llm --prompt standard --require-public-count --out baseline/experiment_results/reproduction_fresh/standard
python baseline/run_reproduction.py --method llm --prompt cot --require-public-count --out baseline/experiment_results/reproduction_fresh/cot
python baseline/run_reproduction.py --method llm --prompt repe --require-public-count --out baseline/experiment_results/reproduction_fresh/repe
```

저장된 문제는 성공/실패 모두 건너뛴다. 중단된 미저장 문제만 같은
명령으로 재개한다. 응답 직후 강제 종료되면 이미 과금된 요청이 재호출될
수 있다. 원문 API 응답은 먼저 별도 저장한다.
인증/요청 제한 오류 또는 연속 3개 예외가 발생하면 자동 중단한다.
그때 실패 파일을 삭제해 성공만 남기지 않는다. 원인 조사 후 재시도
정책을 별도 실험으로 명시하거나 오류 결과를 그대로 보고한다.

초기 정책은 원본 호출과 같은 최대 출력 1000토큰이다. CoT/RePE 응답이
잘린다면 무작정 반복하지 않는다. 출력 상한 변경이 필요한 경우
`--max-tokens 3000` 같은 값을 **세 조건 모두 동일하게** 적용하고,
새 output 디렉터리에서 실험하며 원본 대비 변경을 보고한다.
설정/코드가 바뀐 결과는 manifest 검사가 혼합을 막는다.
과제 설정 유지와의 해석이 불확실하면 변경 전에 조교 확인을 받는다.

로컬 안전장치로 API 60초, 방법별 문제 180초 제한을 사용한다. 이는
조교가 발표한 공식 제한이 아니다. timeout 결과도 실패로 기록한다.
실제 timeout이 나면 실험 정책을 검토하고 보고서에 명시한다.

## 통계

```bash
python baseline/summarize_reproduction.py --root baseline/experiment_results/reproduction_fresh
```

네 디렉터리 모두 1,000개 기록이 있어야 최종 집계한다.
실패도 1,000개 분모에 포함한다. 비율의 기하평균은 A*와 해당 조건
모두 경로가 유효한 쌍에 한정하며 n과 제외 수를 함께 표시한다.

- `summary/table1.csv`: 조건별 기하평균, 문제별 비율 표준편차, 95% CI, 유효 경로 비율.
- `summary/statistics.json`: 상세 수치, 실패 수, 파싱 지표, 토큰 사용량.
- `summary/paired_cases.csv`: 같은 문제끼리 대응한 비율.
- 기하평균 CI는 지도 100개를 단위로 5000회 bootstrap (seed=2026).
- 동일 지도 내 10쌍은 함께 뽑는다. 행 1000개를 독립적으로 뽑지 않는다.
- 이는 한 번 관측한 응답에 조건부인 지도 간 표본 불확실성이다.
  동일 문제의 LLM 반복 실행 변동성을 추정했다고 주장하지 않는다.
- 모든 성공률 관측이 100%이면 경험적 bootstrap CI도 100~100이 된다.
  새로운 지도에서 성공률 100%를 보장하는 뜻이 아니다.
- `storage`는 원본 g 사전 항목 수이며 RAM 사용량이 아니다.
- 원본 프롬프트는 baseline/llmastar/pather/llm_a_star/prompt.py에 있다.
- 처음 세 자연순서 문제만 그림을 생성한다. 그림/검증 포함 시간은
  순수 실행 시간의 공정 비교 지표로 사용하지 않는다.

## 미공개 입력 대응

원본 스키마 JSON을 받아 `searching(query, filepath)`를 호출한다.
1,000개 개수 검사나 공개 map ID에 의존하지 않는다.

```bash
python baseline/run_query.py --method astar --query /tmp/new_map.json --output /tmp/new_astar.json
python baseline/run_query.py --method llm --prompt standard --query /tmp/new_map.json --output /tmp/new_llm.json
```

출력 result의 원본 키는 유지하고 LLM 진단은 `.audit.json`에 저장한다.
이는 GPT/API baseline 인터페이스 검사이며 팀의 개선 알고리즘 실행기는
팀 통합 시 별도로 문서화하고 같은 입력으로 테스트해야 한다.

## 기록 및 제출

실험 후 환경 기록:

```bash
python -m pip freeze > baseline/requirements-reproduction311-lock.txt
```

새 결과는 `experiment_results/reproduction_v2/`에만 저장한다. 예전
gpt4omini_standard는 제외 이력으로 보존한다. 응답과 메시지는 공개
지도/프롬프트이며 API 키를 저장하지 않는다. 그래도 업로드 전 검토한다.

팀 최종 requirements.txt에는 개선 코드의 의존성도 합쳐야 한다.
통합 후 Python 3.11 빈 환경에서 설치 1줄과 README 순서대로 재검증한다.
이 baseline 업데이트만으로 개선 알고리즘/보고서/최종 제출이 완성된 것은 아니다.

## 전체 공개 데이터셋 평가 결과

공개 데이터셋의 100개 지도와 지도별 10개 출발점·도착점 쌍,
총 1,000개 사례를 평가했다.

GPT-4o mini를 사용했으며, standard, CoT, RePE 조건을 각각
1,000건 평가했다. temperature=0, max_tokens=1000, stop=None을
사용했다. A*도 동일한 1,000개 사례에서 실행했다.

| 조건 | 유효 경로 수 | 성공률 | 연산 비율 | 저장 항목 비율 | 경로 길이 비율 |
|---|---:|---:|---:|---:|---:|
| A* | 1000 | 100.0% | 100.00% | 100.00% | 100.00% |
| standard | 878 | 87.8% | 49.65% | 67.87% | 102.68% |
| CoT | 971 | 97.1% | 47.95% | 66.44% | 102.57% |
| RePE | 944 | 94.4% | 51.71% | 69.10% | 102.55% |

성능 비율은 각 조건에서 A*와 LLM-A* 모두 유효한 사례의
LLM-A*/A* 비율에 대한 기하평균이다.
조건마다 포함된 사례 집합이 다르다.
저장 항목 비율은 실제 RAM 사용량을 의미하지 않는다.

사례별 비율의 표준편차와 지도 단위 부트스트랩 95% 신뢰구간은
experiment_results/reproduction_v2/summary/statistics.json에 기록했다.
부트스트랩 반복 횟수는 5,000회이며 시드는 2026이다.
이는 지도 간 변동을 반영하며 LLM 반복 호출의 재현성을 측정하지 않는다.

전체 실행은 세 프롬프트 조건을 별도 프로세스에서 동시에 진행했다.
실행 시간은 독립적인 환경에서 측정한 조건별 속도 비교로 해석하지 않는다.

이전 gpt4omini_standard 결과는 줄바꿈 종료 및 파싱 실패 시
대체값 처리 문제로 최종 성능 비교에서 제외했다.

## 저장된 결과와 새 실험 구분

제출한 실험 기록은 experiment_results/reproduction_v2/에 있다.
위 실행 명령은 새 실험용 reproduction_fresh/에 결과를 저장한다.
처음 실행할 때 이 폴더는 존재하지 않거나 비어 있어야 한다.
중단된 동일 실험을 이어갈 때만 같은 출력 폴더를 사용한다.
이미 완료한 실험을 다시 수행하려면 네 조건 모두에 대해 새로운
공통 상위 폴더를 지정하고 통계 명령의 --root도 함께 변경한다.
새 실험의 통계는 reproduction_fresh/summary/에 생성된다.
기존 reproduction_v2/ 기록은 삭제하거나 덮어쓰지 않는다.
