> **주의: 아래는 이전 실행 기록입니다.** 기존 `gpt4omini_standard` 결과는 1,000건 모두 경유점 배열 파싱에 실패한 실행이며, 정상 LLM-A* 재현 결과로 사용하지 않습니다. 수정 실행과 현재 상태는 [README_REPRODUCTION_V2.md](README_REPRODUCTION_V2.md)를 따르세요.

# 원본 LLM-A* 실행 안내

## 범위
공식 LLM-A* 구현을 사용하며, GPT-4o mini 연결과 예제 실행 파일을 추가했다.
개선 알고리즘은 포함하지 않는다.
예제 지도 1개에서 A*와 LLM-A*의 실행을 확인했다.
전체 데이터셋 및 논문 Table 1 재현은 아직 완료하지 않았다.

## 출처
공식 저장소: https://github.com/SilinMeng0510/llm-astar
기준 커밋: UPSTREAM_COMMIT.txt
공식 라이선스: LICENSE

## 변경사항
- llmastar/model/chatgpt.py: GPT-4o mini를 위한 API 연결 수정
- run_baseline.py: 실행 모드 선택 및 JSON/PNG 저장 추가
- 탐색 알고리즘과 원본 프롬프트는 유지

## 설치
팀 저장소 최상위에서 실행한다.

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install wheel
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r baseline/requirements.txt
python -m pip install -e ./baseline --no-deps --no-build-isolation

검증 환경의 패키지 버전은 requirements-lock.txt에 기록했다.
원본은 openai==0.27.2를 사용한다.

## API 설정
터미널에서 다음 첫 줄을 실행한 뒤 키를 입력한다.

read -s -p "OpenAI API key: " OPENAI_API_KEY
export OPENAI_API_KEY
echo
export OPENAI_MODEL="gpt-4o-mini"

키를 코드나 Git에 저장하지 않는다.

## 실행
cd baseline
python run_baseline.py --method astar
python run_baseline.py --method llm

## 출력
results/astar.png, results/astar.json
results/llm.png, results/llm.json

operation: 원본 CLOSED 목록 항목 수
storage: 원본 g 사전 항목 수이며 RAM 사용량이 아님
length: 경로 길이
llm_output: 원본 코드가 처리한 안내 지점 목록
elapsed_seconds_including_plot: 그림 생성까지 포함한 실행 시간

JSON 결과와 이미지 생성만으로 모든 경로의 유효성이 검증되는 것은 아니다.
실행을 반복하면 같은 이름의 결과 파일을 덮어쓴다.

## 팀 저장소의 기존 스크립트와 관계
이 폴더는 독립적으로 실행하는 원본 baseline이다.
루트의 requirements.txt와 scripts/reproduce.py는 수정하지 않았다.
기존 실험 스크립트와의 통합 및 모델 기록 수정은 별도 작업이다.
