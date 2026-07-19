# 인수인계서 — bull-bear-debate (2026-07-19)

## 프로젝트 개요
주식 종목을 놓고 Bull(강세론) vs Bear(약세론) LLM 에이전트가 토론하는 Streamlit 앱.
토너먼트 모드(다중 라운드), PDF 리포트 출력 지원.

## 실행 방법 (Windows)
```
cd D:\claude\bear-bull-debate
run.bat
```
최초 1회 venv 생성 + 패키지 설치 후 브라우저 자동 실행. 이후는 `run.bat`만 실행하면 됨.

## 아키텍처 (파일별 역할)
| 파일 | 역할 | 라인수 |
|---|---|---|
| `app.py` | Streamlit UI, 백엔드 선택 라우팅 | 410 |
| `debate_engine.py` | 토론 라운드 진행 로직 | 141 |
| `prompts.py` | Bull/Bear 시스템 프롬프트 | 95 |
| `pdf_export.py` | 토론 결과 PDF 생성 | 152 |
| `claude_cli.py` | Claude 로컬 CLI 백엔드 (CLI 로그인 필요) | 100 |
| `claude_api.py` | Claude API 키 백엔드 | 72 |
| `openai_client.py` | GPT(OpenAI) API 키 백엔드 | 62 |
| `gemini_client.py` | Gemini API 키 백엔드 | 69 |
| `tests/` | pytest, 31개 전부 통과 (mock 기반, 실 API 호출 없음) |

## 백엔드 4종 (사이드바에서 선택)
1. **Claude (로컬 CLI)** — `claude` CLI 설치+로그인 필요. 클라우드 배포 불가(로컬 세션 의존).
2. **Claude (API 키)** — `claude_api.py`, `anthropic` SDK. 폰/클라우드에서도 동작.
3. **GPT (API 키)** — `openai_client.py`, `openai` SDK (Responses API).
4. **Gemini (API 키)** — `gemini_client.py`.

세 API 키 백엔드는 모두 동일 인터페이스로 설계됨:
```python
ask(system, user, api_key, timeout, model) -> {result, total_cost_usd, model}
research(ticker, api_key, timeout, model) -> str  # 서버측 web_search 사용
```
모델 실패 시 1회 폴백(더 안정적인 모델로 재시도) 패턴 공통 적용.

## 현재 상태
- `main` 브랜치 = 최신, PR #4/#5/#6 전부 머지 완료.
- 로컬 브랜치 `claude/ponytail-superpowers-plugins-p8ena2`도 origin과 존재하나 이미 main에 머지됨 — 신규 작업은 main에서 새 브랜치 따는 걸 권장.
- 미완 항목: `docs/superpowers/specs/2026-07-18-claude-api-backend.md` 체크리스트 중 "실호출 1회"만 미검증 (사용자 API 키 필요, 배포 후 확인 예정).

## 스펙 문서 위치
`docs/superpowers/specs/` 에 설계 스펙 3건:
- `2026-07-17-bull-bear-debate-design.md` — 토론 앱 기본 설계
- `2026-07-17-tournament-mode-design.md` — 토너먼트 모드 설계
- `2026-07-18-claude-api-backend.md` — API 백엔드 설계(폰 단독 사용 목적)

새 기능 추가 시 이 폴더에 같은 형식으로 스펙 문서 작성하는 관례 있음(ponytail/superpowers 플러그인 워크플로우 사용 중).

## Claude Code로 이어서 작업할 때 참고
- 이 레포는 `ponytail` 스킬(과잉설계 방지) + `superpowers` 스킬셋이 세션 시작 시 자동 로드됨(`.claude/hooks` 또는 프로젝트 설정 참고).
- 코드 리뷰는 `ponytail-review` 스킬로 진행해온 이력 있음 (불필요 복잡도 제거 목적).
- 테스트는 전부 mock 기반 — 실 API 키 없이 `pytest` 실행 가능.
- 커밋 전 `pytest tests/ -q` 로 회귀 확인 습관화됨.

## 다음 액션 후보
- [ ] 실 API 키로 각 백엔드 1회 실호출 검증 (Claude/GPT/Gemini)
- [ ] Streamlit Community Cloud 배포 (README에 절차 있음)
- [ ] 신규 기능/버그는 `docs/superpowers/specs/`에 스펙 먼저 작성 후 구현 권장
