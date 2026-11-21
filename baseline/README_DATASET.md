> **주의: 아래는 이전 실행 기록입니다.** 기존 `gpt4omini_standard` 결과는 1,000건 모두 경유점 배열 파싱에 실패한 실행이며, 정상 LLM-A* 재현 결과로 사용하지 않습니다. 수정 실행과 현재 상태는 [README_REPRODUCTION_V2.md](README_REPRODUCTION_V2.md)를 따르세요.

# 공개 데이터셋 전체 평가

## 목적
공식 LLM-A* 탐색 구현과 원본 standard 프롬프트를 사용해
A*와 LLM-A*를 공개 데이터셋에서 비교한다.
LLM은 GPT-4o mini이며, 논문과 동일한 LLM 조건의 완전 재현은 아니다.
개선 알고리즘은 포함하지 않는다.

## 데이터
dataset/environment_50_30.json
지도 100개, 지도마다 출발·도착점 10쌍, 총 1,000개 문제.
데이터 파일은 수정하지 않는다.

## 실행
팀 저장소 최상위에서 가상환경을 활성화하고
OPENAI_API_KEY와 OPENAI_MODEL=gpt-4o-mini를 설정한다.

python baseline/run_dataset.py --validate-only
python baseline/run_dataset.py --limit 10
python baseline/run_dataset.py
python baseline/run_dataset.py --summary-only

## 저장 및 재개
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
