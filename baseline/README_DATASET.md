# 공개 데이터셋 전체 평가

## 기존 GPT 결과의 경유점 문제 (2026-11-20 확인)

`experiment_results/gpt4omini_standard/`에 저장된 최초 1,000개 실행은
경로 자체는 모두 유효하지만, GPT 응답 1,000개 중 경유점 목록을 포함한 것이
0개였다. 원본 `ChatGPT.ask`의 기본 `stop=["\n"]` 때문에 출력이 첫
줄바꿈에서 끝났고, 원본 파서는 목록이 없을 때 좌표 `[0,0]` 두 개로
대체했다. 이 좌표들은 필터에서 제거되어 모든 사례의 `llm_output`이
출발점과 도착점만 포함한다. 따라서 이 폴더의 성능 수치는 **LLM 경유점
효과를 평가한 결과로 사용할 수 없다**. 원본 응답과 결과는 감사 기록으로
보존한다. `scripts/audit_gpt_waypoint_archive.py`가 이 상태를 재검증한다.

`improvement` 브랜치에는 경유점 요청에서만 `stop=None`을 전달하고,
파싱 가능한 목록이 없으면 명시적으로 실패하도록 수정했다. 이 수정은
오프라인 모의 응답으로 검증했으며, **실제 GPT 재실행은 아직 하지 않았다**.
현재 `improvement` 브랜치의 실행기는 Windows PowerShell과 Ubuntu에서
작동한다. `--prompt`는 `standard`, `cot`, `repe` 중 하나를 고른다.
`--pairs-per-map 2`는 지도 100개마다 출발·도착 쌍 앞의 2개씩을 골라
200건을 구성한다. `--limit 10`은 그 200건 중 처음 10건을 실행한다.
이후 **같은 코드와 가상환경**에서 `--limit` 없이 다시 실행하면 저장된
10건을 건너뛰고 나머지 190건을 진행한다. 조건별 기본 출력 폴더가
다르므로 CoT와 RePE 결과가 섞이지 않는다.

### Windows PowerShell: CoT·RePE 각 200건

저장소 최상위에서 실행한다. 다음은 이 컴퓨터에서 확인한 Python 경로이다.
새 가상환경에는 GPT 실행에 필요한 CPU 패키지만 설치한다.

```powershell
& 'C:\Users\dkdis\anaconda3\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r baseline/requirements-gpt.txt
.\.venv\Scripts\python.exe baseline/run_dataset.py --validate-only --pairs-per-map 2
```

API 키는 같은 PowerShell 창에서 입력한다. 입력값은 화면에 표시하지 않고
이 창의 환경 변수에만 둔다. 키를 채팅이나 Git에 올리지 않는다.

```powershell
$secret = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
Remove-Variable secret
$env:OPENAI_MODEL = 'gpt-4o-mini'
```

먼저 각 조건에서 10건만 실행한다. `summary.json`의 `methods.llm`에서
오류가 없는지, `llm_waypoints.valid_cases_with_intermediate_waypoint`가
0보다 큰지 확인한다. 모두 0이거나 오류가 있으면 전체 실행을 멈추고
원인을 확인한다.

```powershell
.\.venv\Scripts\python.exe baseline/run_dataset.py --prompt cot --pairs-per-map 2 --limit 10
.\.venv\Scripts\python.exe baseline/run_dataset.py --prompt repe --pairs-per-map 2 --limit 10
Get-Content baseline/experiment_results/gpt4omini_cot_2pairs_fixed/summary.json
Get-Content baseline/experiment_results/gpt4omini_repe_2pairs_fixed/summary.json
```

10건이 정상이라면 같은 명령에서 `--limit 10`만 빼고 이어 실행한다.

```powershell
.\.venv\Scripts\python.exe baseline/run_dataset.py --prompt cot --pairs-per-map 2
.\.venv\Scripts\python.exe baseline/run_dataset.py --prompt repe --pairs-per-map 2
```

재실행 시 기존 사례의 `SKIP` 표시가 정상이다. 실패 사례도 기록된 후
자동으로 재시도하지 않으므로, 오류가 나면 결과 폴더를 임의로 고치거나
삭제하지 말고 원인을 확인한다. 실행기 코드나 주요 패키지를 바꾸면
기존 폴더로 이어 실행할 수 없도록 manifest가 막는다.

팀원이 `standard` 1,000건을 다시 실행할 경우에는 같은 실행기에서
`--prompt standard --pairs-per-map 10`을 쓰면 된다. 기본 출력 폴더는
`gpt4omini_standard_10pairs_fixed`이고 기존 기록은 덮어쓰지 않는다.

Windows에서는 Linux 전용 `SIGALRM` 제한을 사용할 수 없다. GPT API
요청에는 60초 타임아웃이 있고, 사례별 기록은 유지된다. 최종 제출
평가 환경인 Python 3.11/Ubuntu 22.04에서는 별도 설치 검증이 필요하다.

기존 폴더를 덮어쓰지 않는다. 원본 실행은 Python 3.10.12에서 수행되었고,
과제 평가 환경은 Python 3.11이므로 최종 제출 전 별도 검증이 필요하다.

## 이전 원본 실행 기록 (참고)

아래 내용은 처음 수행한 `gpt4omini_standard` 기록에 대한 설명이다.
새 실험은 위 Windows 명령과 새 결과 폴더를 사용한다.

## 목적
공식 LLM-A* 탐색 구현과 원본 standard 프롬프트를 사용해
A*와 LLM-A*를 공개 데이터셋에서 비교한다.
LLM은 GPT-4o mini이며, 논문과 동일한 LLM 조건의 완전 재현은 아니다.
개선 알고리즘은 포함하지 않는다.

## 데이터
dataset/environment_50_30.json
지도 100개, 지도마다 출발·도착점 10쌍, 총 1,000개 문제.
데이터 파일은 수정하지 않는다.

## 이전 실행 명령 (현재 실험에는 사용하지 않음)
팀 저장소 최상위에서 가상환경을 활성화하고
OPENAI_API_KEY와 OPENAI_MODEL=gpt-4o-mini를 설정한다.

python baseline/run_dataset.py --validate-only
python baseline/run_dataset.py --limit 10
python baseline/run_dataset.py
python baseline/run_dataset.py --summary-only

## 이전 실행의 저장 및 재개
baseline/experiment_results/gpt4omini_standard/에 저장한다.
방법별·문제별 결과를 저장하며 재실행 시 저장된 결과는 건너뛴다.
실패 결과도 유지하며 자동 재시도하지 않는다.
코드나 주요 환경이 변경되면 동일 결과 폴더에서 재개하지 않는다.

## 평가
출발·도착점, 이동 규칙, 경계, 장애물과의 선분 교차,
반환된 경로 길이를 검사한다.
A*의 역방향 경로는 검증 시 출발점→도착점 순서로 정규화한다.

operation과 storage는 원본 구현의 지표를 사용한다.
storage는 g 사전 항목 수이며 실제 RAM 사용량이 아니다.
성능 비율은 두 방법 모두 유효한 문제에서 기하평균으로 집계한다.
실패 수와 미실행 수는 별도로 보고한다.

첫 10개 문제만 그림을 생성한다.
elapsed_seconds_including_plot은 그림 생성과 검증 등도 포함하므로
순수 탐색 시간이나 전체 문제 간 공정한 시간 비교에 사용하지 않는다.

## 모델 및 비용
실제 반환 모델과 응답별 토큰 사용량은 api_calls/에 기록한다.
비용 추정은 캐시 할인을 제외한 참고값이다.
응답을 받지 못한 요청의 비용은 로컬 기록에서 누락될 수 있으므로
최종 청구 금액은 API 사용 내역을 기준으로 한다.

## 결과와 환경
summary.json: 전체 집계
cases.csv: 문제별 표
cases/: 경로 및 원시 결과
api_calls/: 모델 응답 및 사용량
plots/: 대표 이미지
manifest.json: 설정, 데이터 및 코드 해시
provenance.json: 코드 출처
requirements-experiment-lock.txt: 실행 환경 패키지 목록

실제 완료 여부와 성공률은 summary.json을 확인한다.
