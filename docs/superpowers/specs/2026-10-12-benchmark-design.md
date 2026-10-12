# 에이전트 창의성 지수(ACI) 벤치마크 설계

- 날짜: 2026-10-12
- 상태: 사용자 검토 대기
- 범위: 하위 프로젝트 1(벤치마크). 하위 프로젝트 2(창의성 스킬/하네스)는 이 벤치마크가 돌아간 뒤 별도 설계한다.

## 1. 목적과 성공 기준

**목적.** 같은 에이전트에 스킬·하네스를 켰을 때(B)와 껐을 때(A)를 비교해 "창의성이 올랐는가"를 하나의 지수로 보고한다. 1차 사용자는 Claude Code 스킬 제작자다.

**성공 기준.**
1. `uv run aci run → judge → score` 세 명령으로 A/B 비교 보고서(`report.md`, `report.json`)가 나온다.
2. 같은 설정을 A와 B 양쪽에 넣으면(A/A 비교) 지수가 50 근처이고 95% 신뢰구간이 50을 포함한다. 이 검사를 통과하지 못하면 지수를 믿지 않는다.
3. 기준 에이전트(A)가 사용자 전역 설정(플러그인, CLAUDE.md, 훅)을 불러오지 않음이 확인된다(§6).
4. 외부 사용자가 README만 보고 재현할 수 있다.

**사용자가 정한 것.** 세 축(문제 해결·발산·생성물)을 묶은 지수 / 용도는 스킬·하네스 효과 검증 / 실행은 명령어 템플릿 어댑터 / 주관 축 채점은 블라인드 쌍대 비교 + 타 계열 모델 심판 / 접근 A(한 저장소 = 플러그인 + Python 벤치 CLI).

**가정(검토 시 정정 바람).** 이름 `agent-creativity-index`, CLI `aci`, 라이선스 AGPL-3.0-or-later(value-for-fable과 동일), 태스크 프롬프트와 README는 영어 기본(공개 대상이 넓으므로), 설계 문서는 한국어.

## 2. 비범위

리더보드 웹사이트, 임베딩 기반 다양성 지표, 절대 점수 루브릭, 인간 평가 데이터, Claude Code·Codex 외 어댑터 프리셋. 요구가 확인되면 그때 넣는다.

## 3. 저장소 구조

```
agent-creativity-index/
  .claude-plugin/plugin.json      # 하위 프로젝트 2에서 스킬을 채움. 지금은 뼈대만
  skills/
  bench/
    pyproject.toml                # uv로 실행. 의존성: pyyaml, pytest(dev)
    aci/
      cli.py                      # run / judge / score 하위 명령
      tasks.py                    # task.yaml 로드·검증
      runner.py                   # 에이전트 실행
      judge.py                    # 쌍대 비교
      score.py                    # 승률·신뢰구간·지수
    tasks/
      solve/<id>/task.yaml (+ starter/, tests/)
      diverge/<id>/task.yaml
      make/<id>/task.yaml (+ starter/)
    configs/
      claude-base.yaml  claude-skill.yaml  judge-codex.yaml  fake-agent.yaml  fake-judge.yaml
    tests/
    runs/                         # 결과물, gitignore
  docs/
  README.md  LICENSE
```

## 4. 태스크

### 4.1 형식

```yaml
id: solve-rate-limiter
axis: solve            # solve | diverge | make
split: dev             # dev | holdout
prompt: |
  ...
output: answer.md      # 에이전트가 작업 폴더에 써야 하는 결과 경로(파일 또는 폴더)
check: pytest -q tests # solve 축만. 작업 폴더에서 실행, 종료코드 0 = 통과
judge_focus: |         # 심판에게 줄 축별 판정 기준 보충(선택)
  ...
```

로더는 필수 필드 누락, 알 수 없는 axis/split, solve 축의 check 누락, 중복 id를 오류로 거부한다.

### 4.2 축 정의와 첫 태스크 세트

| 축 | 측정하는 것 | 태스크 모양 | 판정 |
|---|---|---|---|
| solve | 뻔한 첫 해법이 아닌, 작동하는 다른 접근 | 테스트가 있는 코딩·설계 과제. 흔한 해법을 제약으로 막거나 불리하게 만든다 | 테스트 통과가 먼저, 둘 다 통과하면 심판이 독창성 판정 |
| diverge | 발산적 사고 | "N개의 서로 다른 대안/용도/가설을 내라" | 심판이 목록 전체의 다양성·독창성 판정 |
| make | 산출물의 새로움 | 짧은 소설, 미니 게임(단일 HTML), 디자인 문서 | 심판이 "요구사항을 지키면서 더 창의적인 쪽" 판정 |

첫 버전은 축마다 dev 4 + holdout 4, 총 24개. 태스크 작성 원칙: 결과물이 한 화면 분량으로 심판 비교가 가능할 것, 특정 모델·스킬에 유리한 표현을 넣지 않을 것.

## 5. 설정(어댑터)

에이전트와 심판 모두 명령어 템플릿이다.

```yaml
# configs/claude-skill.yaml
name: claude-skill
cmd: >-
  claude -p "$(cat {prompt_file})" --plugin-dir {repo_root}
  --dangerously-skip-permissions
env: {}           # 격리용 환경변수(§6)
timeout: 900      # 초
```

자리표시자: `{prompt_file}`, `{workdir}`(실행 위치이기도 함), `{repo_root}`, `{output}`. 심판 설정은 추가로 `{judge_prompt_file}`을 받고, 표준출력 또는 지정 파일에서 판정 JSON을 읽는다(codex는 `-o` 사용).

에이전트 명령은 매번 새 임시 작업 폴더 안에서만 실행한다. 권한 우회 플래그는 이 격리 폴더를 전제로 한다.

## 6. 격리(필수)

A/B 비교가 의미를 가지려면 A가 사용자의 전역 플러그인·CLAUDE.md·훅·자동 메모리 없이 돌아야 한다.

- **API 키가 있을 때(공개 결과 권장):** `claude --bare`. 훅·플러그인 동기화·CLAUDE.md 자동 탐색·자동 메모리를 끄고, B는 `--plugin-dir`로 스킬만 더한다.
- **구독(OAuth)만 있을 때:** `--bare`는 OAuth를 읽지 않으므로 쓸 수 없다. 깨끗한 설정 폴더(`CLAUDE_CONFIG_DIR`) 또는 `--setting-sources`로 전역 설정을 배제하는 방법을 구현 첫 단계에서 실측해 정한다.
- **검증 태스크:** `aci doctor <config>`가 에이전트에게 "불러온 스킬·플러그인·지시 파일을 나열하라"를 실행시켜, A에 사용자 전역 항목이 보이면 실패로 보고한다. 이 검사를 통과한 설정만 보고서에 쓴다.

## 7. 실행 흐름

### 7.1 `aci run --config A.yaml --config B.yaml --split dev -k 3 -j 4 --out runs/<name>`

태스크 × 설정 × 샘플(k)마다:
1. 새 임시 작업 폴더를 만들고 `starter/`를 복사한다(`tests/`는 복사하지 않는다. 에이전트가 테스트를 보고 맞추지 못하게).
2. 프롬프트 파일을 쓰고 명령을 timeout과 함께 실행한다.
3. `runs/<name>/<task>/<config>/<i>/`에 stdout, stderr, 종료코드, 소요 시간, `output` 결과물을 저장한다.
4. solve 축이면 에이전트가 끝난 뒤 작업 폴더에 `tests/`를 복사해 `check`를 실행하고 통과 여부를 기록한다.

이미 완료 기록(`meta.json`)이 있는 샘플은 건너뛴다(재개).

### 7.2 `aci judge runs/<name> --judge configs/judge-codex.yaml`

같은 태스크에서 A의 i번째와 B의 i번째를 짝짓는다.
- solve 축: 한쪽만 통과 → 통과한 쪽 승(심판 호출 없음). 둘 다 실패 → 무승부. 둘 다 통과 → 심판.
- 심판 호출은 두 번, 순서를 바꿔서. 결과물은 "응답 1/응답 2"로만 표시하고 설정 이름·소요 시간 등 출처 단서를 지운다.
- 두 판정이 같은 쪽을 고르면 그 쪽 승, 엇갈리거나 둘 다 tie면 무승부.
- 심판 출력 형식: `{"winner": 1 | 2 | "tie", "reason": "..."}`.
- 심판 프롬프트의 축별 기준:
  - solve: 둘 다 정답이다. 어느 접근이 더 독창적이고 덜 뻔한가.
  - diverge: 어느 목록이 서로 더 다르고 덜 뻔한 아이디어를 담았는가. 개수가 같다는 전제에서 질로 판단.
  - make: 요구사항을 지키는 것이 전제다. 요구사항을 어긴 쪽은 진다. 지킨 경우 어느 쪽이 더 새롭고 인상적인가.
- 판정은 `runs/<name>/<task>/judgments.jsonl`에 누적, 이미 판정된 짝은 건너뛴다.

### 7.3 `aci score runs/<name> [--split holdout]`

- 축별 B 승률 = (B 승 + ½ 무승부) / 짝 수 × 100.
- 95% 신뢰구간: 태스크 단위로 재표집하는 부트스트랩(2,000회, 시드 고정).
- **지수 = 세 축 승률의 평균.** 50 = 차이 없음, 50 초과 = B가 더 창의적.
- 보고서에 함께 적는 것: 축별 짝 수·승·패·무, solve 축 테스트 통과율(A, B), 실패·시간초과 수, 심판 파싱 실패 수, 심판과 피평가 에이전트가 같은 계열이면 경고.
- 기본 보고 split은 holdout. dev 결과는 `--split dev`로 명시할 때만.

## 8. 실패 처리

| 상황 | 처리 |
|---|---|
| 에이전트 시간초과·비정상 종료·결과물 없음 | 해당 샘플은 결과물 없음으로 기록. 짝 판정에서 패배(상대도 없으면 무승부). 보고서에 집계 |
| 심판 출력 JSON 파싱 실패 | 1회 재시도, 그래도 실패면 그 호출은 tie로 기록하고 플래그 |
| 심판 명령 자체 실패 | 같은 처리. 실패율이 10%를 넘으면 score가 경고 |
| task.yaml 오류 | 실행 전 전체 검증에서 중단 |

## 9. 누수·편향 방지

- 스킬 개발(하위 프로젝트 2)은 dev split만 본다. holdout 프롬프트는 스킬 작성 중 열람하지 않는다.
- 심판은 피평가 에이전트와 다른 계열 모델을 기본으로 한다(Claude 평가 → codex 심판).
- 순서 바꿈 이중 판정으로 위치 편향을 상쇄한다.
- A/A 비교(성공 기준 2)로 심판·표집 잡음의 크기를 확인한다.

## 10. 테스트

필요한 만큼만.
- `score.py`: 승률 계산, 부트스트랩 신뢰구간(결정적 시드), 지수 평균.
- `judge.py`: 순서 바꿈 결합 규칙, solve 축 자동 판정, JSON 파싱·재시도.
- `tasks.py`: 유효/무효 task.yaml.
- 종단 간 연기 테스트: `fake-agent`(echo로 결과물 작성)와 `fake-judge`(고정 JSON 출력)로 run → judge → score 전체를 비용 없이 실행.

## 11. 이후

이 벤치마크로 A/A 검사와 기준선 측정을 마친 뒤, 하위 프로젝트 2(창의성 스킬/하네스)를 별도로 브레인스토밍한다. 후보 기제: 발산→수렴 루프, 뻔한 해법 먼저 나열 후 금지, 제약·관점 주입, 다중 후보 생성 후 자기 선별. dev split 점수로 고르고 holdout으로 최종 보고한다.
