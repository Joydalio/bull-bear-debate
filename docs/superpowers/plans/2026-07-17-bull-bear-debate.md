# bull-bear-debate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bear/Bull 에이전트가 라운드제 토론 후 심판이 ORCA 점수로 판정하는 로컬 Streamlit 앱. LLM 호출은 전부 로컬 `claude -p` subprocess.

**Architecture:** `app.py`(UI) → `debate_engine.debate()`(오케스트레이션) → `claude_cli.ask()`(subprocess 래퍼) 단방향 의존. `prompts.py`는 상수만, `pdf_export.py`는 결과 dict → PDF bytes 순수 함수.

**Tech Stack:** Python 3.11+, Streamlit, fpdf2, pytest(개발용), Claude Code CLI(`claude -p`)

## Global Constraints

- **API 키 금지:** subprocess env에서 `ANTHROPIC_API_KEY` 제거한 사본 전달. anthropic SDK 사용 금지.
- **subprocess:** 항상 `encoding="utf-8"`, `errors="replace"`, `shell=False`, `capture_output=True`.
- **모델:** `MODEL_PRIMARY = "claude-fable-5"`, `MODEL_FALLBACK = "claude-opus-4-8"`. PRIMARY 실패 시 FALLBACK 1회 재시도 후 모듈 캐시.
- **프롬프트 5종 문구 수정·요약 금지** (Task 1에 원문 수록).
- **크로스 플랫폼:** macOS + Windows. `claude` 실행 파일은 `shutil.which`로 해석 (Windows `.cmd` 대응).
- 작업 디렉토리: `/Users/jun/bull-bear-debate`. 파이썬은 `.venv/bin/python`(macOS) 사용.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: 스캐폴딩 + prompts.py

**Files:**
- Create: `prompts.py`, `requirements.txt`, `.gitignore`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces: `prompts.BEAR_SYSTEM_R1`, `BULL_SYSTEM_R1`, `BEAR_SYSTEM_REBUTTAL`, `BULL_SYSTEM_REBUTTAL`, `JUDGE_SYSTEM` (모두 str)

- [ ] **Step 1: venv 생성 및 의존성 설치**

```bash
cd /Users/jun/bull-bear-debate
python3 -m venv .venv
.venv/bin/pip install streamlit fpdf2 pytest
```

- [ ] **Step 2: `.gitignore` 작성**

```
__pycache__/
.venv/
.DS_Store
*.pyc
```

- [ ] **Step 3: `requirements.txt` 작성** (pytest는 개발용이라 제외)

```
streamlit
fpdf2
```

- [ ] **Step 4: 실패하는 테스트 작성** — `tests/test_prompts.py`

```python
import prompts

def test_five_prompts_exist_and_intact():
    assert "숏셀러(공매도 투자자)입니다" in prompts.BEAR_SYSTEM_R1
    assert "Reverse DCF" in prompts.BEAR_SYSTEM_R1
    assert "매수(Long) 관점의 투자자입니다" in prompts.BULL_SYSTEM_R1
    assert "숨겨진 콜옵션" in prompts.BULL_SYSTEM_R1
    assert "가장 약한 고리 2개" in prompts.BEAR_SYSTEM_REBUTTAL
    assert "최대 800자" in prompts.BULL_SYSTEM_REBUTTAL
    assert '"verdict": "매수|관망|매도"' in prompts.JUDGE_SYSTEM
```

- [ ] **Step 5: 실패 확인**

Run: `cd /Users/jun/bull-bear-debate && .venv/bin/python -m pytest tests/ -v`
Expected: FAIL (`ModuleNotFoundError: prompts`)

- [ ] **Step 6: `prompts.py` 작성 — 아래 원문 그대로, 한 글자도 수정 금지**

```python
BEAR_SYSTEM_R1 = """당신은 철저하게 비판적인 시각을 가진 독립적 금융 애널리스트이자 숏셀러(공매도 투자자)입니다. 감정적 수사를 배제하고 오직 팩트와 데이터, 리스크 요인만을 기반으로, 제공된 컨텍스트를 활용해 아래 4개 항목을 순서대로 분석하십시오.

1. 하방 촉매(Downside Catalyst) 및 주가 하락 요인 분석

* 매크로 환경 변화(금리, 환율, 경기 둔화 등), 산업 내 경쟁 구도 악화, 기업 고유의 펀더멘탈 훼손 요인
* 주가 하락을 유발할 가장 유력한 시나리오 제시

2. 밸류에이션 프리미엄 및 고평가 리스크 검증

* 과거 역사적 평균 밴드(P/E, P/S, EV/EBITDA 등) 및 글로벌 피어 대비 과도한 프리미엄의 정량적 근거
* 안전마진(Margin of Safety) 결여를 판단할 수 있는 지표

3. 리스크 프로파일 세분화 및 꼬리 위험(Tail Risk)

* 재무적 리스크: 현금흐름 악화, 부채 부담, 수익성(마진) 압박 가능성
* 운영 및 규제 리스크: 공급망 차질, 주요 경영진 리스크, 정부 규제 및 소송 가능성
* 테일 리스크: 발생 확률은 낮으나 발생 시 기업 가치에 치명적인 블랙스완 요인

4. 시장 기대치 역산(Reverse DCF) 및 성장률 가정의 결함

* 현재 시가총액을 정당화하기 위해 시장이 반영 중인 내재 성장률(%) 추정
* 역산된 기대치(성장률, 마진율)가 산업 평균 전망이나 기업 실제 역량 대비 비현실적이라고 판단되는 논리적 결함과 근거
출력 규칙: 한국어, ~함/~임체. 각 항목에 번호를 붙여 구조화. 컨텍스트에 없는 수치는 "확인 불가"로 표기하고 추정치를 지어내지 말 것."""

BULL_SYSTEM_R1 = """당신은 이 기업의 내재 가치와 장기 성장성을 강하게 신뢰하는 밸류에이션 전문가이자 매수(Long) 관점의 투자자입니다. 앞서 제시된 Bear Case를 정면으로 반박하고, 리스크들이 통제 가능하거나 과장되었음을 오직 팩트와 논리적 근거로 입증하십시오. 아래 4개 항목을 순서대로 답하십시오.

1. 하방 촉매에 대한 반박 및 시클리컬 소음의 분리

* Bear가 지적한 하락 요인 중 단기적·일시적 소음에 불과한 것 식별
* 악재가 이미 주가에 선반영(Priced-in)되었다고 볼 수 있는 가격적 근거
* 악재 해소 시 회복을 이끌 상방 촉매(Upside Catalyst) 정의

2. 밸류에이션 프리미엄의 정당성 및 고착성 검증

* 높은 멀티플을 정당화하는 독점적 경쟁 우위(전환 비용, 브랜드 장벽, 네트워크 효과 등 경제적 해자)
* 피어 대비 프리미엄의 타당성을 입증하는 재무 지표(고성장률, ROE/ROIC, 영업이익률 등)

3. 리스크 완화 요인 및 하방 지지선

* 재무적 버퍼: 순현금, FCF 창출력, 가격 전가력
* 운영적 회복력: 다변화된 공급망, 대체 불가능한 핵심 기술력/시장 지배력
* 하방 지지선: 주주환원 정책(자사주/배당), 청산가치 등 주가의 최저 마지노선

4. 내재 성장률 달성 가능성 및 숨겨진 옵셔널리티

* 시장의 내재 성장률 가정이 달성 가능한 시나리오임을 증명 (신규 시장 개척, 침투율 확대 경로)
* 밸류에이션에 미반영된 숨겨진 콜옵션(신규 비즈니스 모델, AI/신기술, M&A 등)
출력 규칙: 한국어, ~함/~임체. 각 항목에 번호를 붙여 구조화. Bear의 주장 중 반박하는 대목을 명시적으로 인용할 것. 컨텍스트에 없는 수치는 "확인 불가"로 표기."""

BEAR_SYSTEM_REBUTTAL = """당신은 숏셀러 애널리스트임. 라운드 1에서 제시한 본인의 Bear Case를 방어하는 반박 라운드임.

* 직전 Bull 주장에서 가장 약한 고리 2개를 골라 정면 공격할 것 (예: 선반영 주장에 가격 근거 부재, 해자의 지속성 과대평가, 옵셔널리티의 실현 확률 미제시 등)
* 본인 논지 중 Bull이 반박하지 못한 항목을 1개 재강조할 것
* 새로운 주제를 벌이지 말고 기존 쟁점을 심화할 것 한국어, ~함/~임체, 최대 800자."""

BULL_SYSTEM_REBUTTAL = """당신은 매수 관점 밸류에이션 전문가임. 본인의 Bull Case를 방어하는 반박 라운드임.

* 직전 Bear 공격 중 가장 치명적인 것 2개에 대해 데이터로 방어할 것
* Bear가 여전히 해소하지 못한 반박 1개를 재제기할 것
* 새로운 주제를 벌이지 말고 기존 쟁점을 심화할 것 한국어, ~함/~임체, 최대 800자."""

JUDGE_SYSTEM = """너는 중립 심판임. 토론 전문을 읽고 ORCA(O/R/C/A 각 0~2.5점, 총 10점)로 판정. 마크다운 백틱 없이 아래 JSON만 출력: {"O": float, "R": float, "C": float, "A": float, "total": float, "verdict": "매수|관망|매도", "winner": "bear|bull|무승부", "key_reason": "1문장", "invalidation": ["반증가능 수치조건 1~3개"]} 채점 기준: R은 높을수록 리스크가 낮다는 뜻. 2.5=명백한 강점, 1.25=중립, 0.5 이하=명백한 결함."""
```

- [ ] **Step 7: 통과 확인**

Run: `cd /Users/jun/bull-bear-debate && .venv/bin/python -m pytest tests/ -v`
Expected: PASS 1개

- [ ] **Step 8: Commit**

```bash
git add prompts.py requirements.txt .gitignore tests/
git commit -m "feat: 프롬프트 5종 상수 + 프로젝트 스캐폴딩"
```

---

### Task 2: claude_cli.py

**Files:**
- Create: `claude_cli.py`
- Test: `tests/test_claude_cli.py`

**Interfaces:**
- Produces:
  - `ask(system_prompt: str, user_prompt: str, timeout: int = 90) -> dict` — 반환 `{"result": str, "total_cost_usd": float, "is_error": False, "model": str}`. 실패 시 `RuntimeError(stderr 포함)`.
  - `preflight() -> str | None` — 정상이면 None, 실패 시 안내 문자열.
  - `MODEL_PRIMARY`, `MODEL_FALLBACK`, `_active_model` (테스트에서 리셋용)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_claude_cli.py`

```python
import json
import subprocess
import pytest
import claude_cli


def _fake_proc(stdout="", returncode=0, stderr=""):
    class P:
        pass
    p = P()
    p.stdout = stdout
    p.returncode = returncode
    p.stderr = stderr
    return p


def _ok_json(result="ok", cost=0.01):
    return json.dumps({"result": result, "total_cost_usd": cost, "is_error": False})


@pytest.fixture(autouse=True)
def reset_model():
    claude_cli._active_model = claude_cli.MODEL_PRIMARY


def test_api_key_removed_from_env(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs["env"]
        return _fake_proc(_ok_json())

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-be-removed")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = claude_cli.ask("시스템", "유저 질문")
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert out["result"] == "ok"


def test_utf8_and_no_shell(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        captured["cmd"] = cmd
        return _fake_proc(_ok_json())

    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cli.ask("한글 시스템", "한글 질문")
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["shell"] is False
    assert "--output-format" in captured["cmd"] and "json" in captured["cmd"]
    assert "--max-turns" in captured["cmd"]


def test_error_raises_with_stderr(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _fake_proc("", returncode=1, stderr="login required")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="login required"):
        claude_cli.ask("s", "u")


def test_is_error_true_raises(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _fake_proc(json.dumps({"result": "bad", "is_error": True, "total_cost_usd": 0}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        claude_cli.ask("s", "u")


def test_model_fallback_and_cache(monkeypatch):
    used = []

    def fake_run(cmd, **kwargs):
        model = cmd[cmd.index("--model") + 1]
        used.append(model)
        if model == claude_cli.MODEL_PRIMARY:
            return _fake_proc("", returncode=1, stderr="model not available")
        return _fake_proc(_ok_json())

    monkeypatch.setattr(subprocess, "run", fake_run)
    out1 = claude_cli.ask("s", "u")
    out2 = claude_cli.ask("s", "u")
    assert used == [claude_cli.MODEL_PRIMARY, claude_cli.MODEL_FALLBACK, claude_cli.MODEL_FALLBACK]
    assert out1["model"] == claude_cli.MODEL_FALLBACK
    assert out2["model"] == claude_cli.MODEL_FALLBACK
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_claude_cli.py -v`
Expected: FAIL (`ModuleNotFoundError: claude_cli`)

- [ ] **Step 3: `claude_cli.py` 구현**

```python
"""claude -p subprocess 래퍼. API 키를 절대 쓰지 않고 로컬 로그인 세션만 사용."""
import json
import os
import shutil
import subprocess

MODEL_PRIMARY = "claude-fable-5"
MODEL_FALLBACK = "claude-opus-4-8"

# ponytail: 실패 원인을 모델 오류로 한정 판별하지 않음 — PRIMARY 실패 시 무조건 FALLBACK 1회 시도
_active_model = MODEL_PRIMARY


def _claude_bin():
    # Windows에서 claude.cmd를 shell=False로 실행하려면 which로 전체 경로 해석 필요
    return shutil.which("claude") or "claude"


def _run(cmd, timeout):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # 구독 세션만 사용, API 과금 원천 차단
    return subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
        env=env,
    )


def _try_model(model, system_prompt, user_prompt, timeout):
    cmd = [
        _claude_bin(), "-p", user_prompt,
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--max-turns", "1",
        "--model", model,
    ]
    proc = _run(cmd, timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI 실패 (model={model}, code={proc.returncode}): {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    if data.get("is_error"):
        raise RuntimeError(f"claude 응답 오류 (model={model}): {data.get('result')} {proc.stderr.strip()}")
    return {
        "result": data.get("result", ""),
        "total_cost_usd": data.get("total_cost_usd") or 0.0,
        "is_error": False,
        "model": model,
    }


def ask(system_prompt, user_prompt, timeout=90):
    global _active_model
    try:
        return _try_model(_active_model, system_prompt, user_prompt, timeout)
    except RuntimeError:
        if _active_model != MODEL_PRIMARY:
            raise
        out = _try_model(MODEL_FALLBACK, system_prompt, user_prompt, timeout)
        _active_model = MODEL_FALLBACK  # 성공한 폴백을 캐시해 이후 호출 재시도 방지
        return out


def preflight():
    try:
        proc = _run([_claude_bin(), "--version"], timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "claude 명령 실행 불가 — claude login 필요 또는 PATH 미등록"
    if proc.returncode != 0:
        return f"claude CLI 오류: {proc.stderr.strip()} — claude login 필요 또는 PATH 미등록"
    return None


if __name__ == "__main__":
    err = preflight()
    if err:
        raise SystemExit(err)
    out = ask("한 문장으로 간결히 답하라.", "테스트 질문: 오늘 기분이 어때?")
    print(f"[{out['model']}] {out['result']}  (명목 비용 ${out['total_cost_usd']:.4f})")
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add claude_cli.py tests/test_claude_cli.py
git commit -m "feat: claude -p 래퍼 — API키 차단, 모델 폴백, preflight"
```

---

### Task 3: debate_engine.py

**Files:**
- Create: `debate_engine.py`
- Test: `tests/test_debate_engine.py`

**Interfaces:**
- Consumes: `claude_cli.ask(system, user, timeout=90) -> dict`, `prompts.*` 5종
- Produces: `debate(ticker: str, context: str, rounds: int = 2, on_message=None) -> dict`
  - 반환 `{"transcript": [{"role": "bear"|"bull", "round": int, "text": str}], "verdict": dict, "notional_cost_usd": float}`
  - verdict 파싱 최종 실패 시 `{"parse_error": True, "raw": str}`
  - `on_message(role, round, text)`는 각 발언 직후 호출

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_debate_engine.py`

```python
import claude_cli
import debate_engine
import prompts


def make_fake_ask(judge_responses):
    """judge_responses: JUDGE_SYSTEM 호출에 차례로 돌려줄 result 문자열 리스트."""
    calls = []
    judge_iter = iter(judge_responses)

    def fake_ask(system, user, timeout=90):
        calls.append({"system": system, "user": user, "timeout": timeout})
        if system == prompts.JUDGE_SYSTEM:
            return {"result": next(judge_iter), "total_cost_usd": 0.01, "is_error": False, "model": "m"}
        return {"result": f"발언#{len(calls)}", "total_cost_usd": 0.02, "is_error": False, "model": "m"}

    return fake_ask, calls


GOOD_JUDGE = '{"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5, "verdict": "관망", "winner": "무승부", "key_reason": "팽팽함", "invalidation": ["PER 30 초과 시"]}'


def test_two_rounds_branching_and_callback(monkeypatch):
    fake_ask, calls = make_fake_ask([GOOD_JUDGE])
    monkeypatch.setattr(claude_cli, "ask", fake_ask)
    events = []
    out = debate_engine.debate("005930", "PER 10, PSR 1.2", rounds=2,
                               on_message=lambda role, r, t: events.append((role, r)))

    # 호출 순서: bear R1, bull R1, bear R2, bull R2, judge
    assert calls[0]["system"] == prompts.BEAR_SYSTEM_R1
    assert calls[0]["timeout"] == 180
    assert calls[0]["user"] == "[대상 기업: 005930]\n컨텍스트:\nPER 10, PSR 1.2"
    assert calls[1]["system"] == prompts.BULL_SYSTEM_R1
    assert "=== Bear Case 전문 ===\n발언#1" in calls[1]["user"]
    assert calls[2]["system"] == prompts.BEAR_SYSTEM_REBUTTAL
    assert calls[2]["timeout"] == 90
    assert "직전 상대(Bull) 주장:\n발언#2" in calls[2]["user"]
    assert "본인의 R1 논지 요약:\n발언#1" in calls[2]["user"]
    assert calls[3]["system"] == prompts.BULL_SYSTEM_REBUTTAL
    assert "직전 상대(Bear) 주장:\n발언#3" in calls[3]["user"]
    assert calls[4]["system"] == prompts.JUDGE_SYSTEM

    assert events == [("bear", 1), ("bull", 1), ("bear", 2), ("bull", 2)]
    assert [m["role"] for m in out["transcript"]] == ["bear", "bull", "bear", "bull"]
    assert out["verdict"]["total"] == 6.5
    assert abs(out["notional_cost_usd"] - (0.02 * 4 + 0.01)) < 1e-9


def test_r1_summary_truncated_to_500(monkeypatch):
    long_text = "가" * 600

    def fake_ask(system, user, timeout=90):
        if system == prompts.JUDGE_SYSTEM:
            return {"result": GOOD_JUDGE, "total_cost_usd": 0.0, "is_error": False, "model": "m"}
        return {"result": long_text, "total_cost_usd": 0.0, "is_error": False, "model": "m"}

    captured = []
    orig = fake_ask

    def spy(system, user, timeout=90):
        captured.append(user)
        return orig(system, user, timeout)

    monkeypatch.setattr(claude_cli, "ask", spy)
    debate_engine.debate("티커", "ctx", rounds=2)
    r2_bear_user = captured[2]
    summary = r2_bear_user.split("본인의 R1 논지 요약:\n")[1]
    assert len(summary) == 500


def test_judge_backtick_removal_and_retry(monkeypatch):
    bad_then_good = ["이건 JSON 아님", "```json\n" + GOOD_JUDGE + "\n```"]
    fake_ask, calls = make_fake_ask(bad_then_good)
    monkeypatch.setattr(claude_cli, "ask", fake_ask)
    out = debate_engine.debate("T", "ctx", rounds=1)
    judge_calls = [c for c in calls if c["system"] == prompts.JUDGE_SYSTEM]
    assert len(judge_calls) == 2
    assert out["verdict"]["verdict"] == "관망"


def test_judge_double_failure_returns_raw(monkeypatch):
    fake_ask, _ = make_fake_ask(["깨진 응답1", "깨진 응답2"])
    monkeypatch.setattr(claude_cli, "ask", fake_ask)
    out = debate_engine.debate("T", "ctx", rounds=1)
    assert out["verdict"]["parse_error"] is True
    assert out["verdict"]["raw"] == "깨진 응답2"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_debate_engine.py -v`
Expected: FAIL (`ModuleNotFoundError: debate_engine`)

- [ ] **Step 3: `debate_engine.py` 구현**

```python
"""토론 오케스트레이션: 라운드 진행 → 심판 판정."""
import json

import claude_cli
from prompts import (
    BEAR_SYSTEM_R1,
    BULL_SYSTEM_R1,
    BEAR_SYSTEM_REBUTTAL,
    BULL_SYSTEM_REBUTTAL,
    JUDGE_SYSTEM,
)

R1_TIMEOUT = 180  # R1은 장문 생성
REBUTTAL_TIMEOUT = 90


def debate(ticker, context, rounds=2, on_message=None):
    transcript = []
    cost = 0.0
    bear_r1 = bull_r1 = last_bear = last_bull = ""

    for r in range(1, rounds + 1):
        for role in ("bear", "bull"):
            if r == 1:
                system = BEAR_SYSTEM_R1 if role == "bear" else BULL_SYSTEM_R1
                timeout = R1_TIMEOUT
                if role == "bear":
                    user = f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                else:
                    user = (f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                            f"\n\n=== Bear Case 전문 ===\n{bear_r1}")
            else:
                system = BEAR_SYSTEM_REBUTTAL if role == "bear" else BULL_SYSTEM_REBUTTAL
                timeout = REBUTTAL_TIMEOUT
                if role == "bear":
                    user = (f"[{ticker}] 직전 상대(Bull) 주장:\n{last_bull}"
                            f"\n\n본인의 R1 논지 요약:\n{bear_r1[:500]}")
                else:
                    user = (f"[{ticker}] 직전 상대(Bear) 주장:\n{last_bear}"
                            f"\n\n본인의 R1 논지 요약:\n{bull_r1[:500]}")

            resp = claude_cli.ask(system, user, timeout=timeout)
            text = resp["result"]
            cost += resp.get("total_cost_usd") or 0.0
            transcript.append({"role": role, "round": r, "text": text})

            if role == "bear":
                last_bear = text
                if r == 1:
                    bear_r1 = text
            else:
                last_bull = text
                if r == 1:
                    bull_r1 = text

            if on_message:
                on_message(role, r, text)

    verdict, judge_cost = _judge(ticker, transcript)
    return {
        "transcript": transcript,
        "verdict": verdict,
        "notional_cost_usd": cost + judge_cost,
    }


def _judge(ticker, transcript):
    full = "\n\n".join(
        f"[라운드 {m['round']} — {m['role'].upper()}]\n{m['text']}" for m in transcript
    )
    user = f"[{ticker}] 토론 전문:\n{full}"
    cost = 0.0
    raw = ""
    for _ in range(2):  # 파싱 실패 시 1회 재시도
        resp = claude_cli.ask(JUDGE_SYSTEM, user, timeout=REBUTTAL_TIMEOUT)
        cost += resp.get("total_cost_usd") or 0.0
        raw = resp["result"].strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned), cost
        except json.JSONDecodeError:
            continue
    return {"parse_error": True, "raw": raw}, cost
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: 토론 오케스트레이션 — 라운드 분기, 콜백, 심판 파싱/재시도"
```

---

### Task 4: pdf_export.py

**Files:**
- Create: `pdf_export.py`
- Test: `tests/test_pdf_export.py`

**Interfaces:**
- Consumes: `debate()` 반환 형식 (transcript / verdict / notional_cost_usd)
- Produces: `build_pdf(ticker: str, transcript: list, verdict: dict, notional_cost_usd: float) -> bytes`
  - 한글 폰트 미발견 시 `RuntimeError`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_pdf_export.py`

```python
import pdf_export


def _sample():
    transcript = [
        {"role": "bear", "round": 1, "text": "하방 리스크: 마진 압박이 심각함. " * 30},
        {"role": "bull", "round": 1, "text": "경제적 해자가 견고함. " * 30},
        {"role": "bear", "round": 2, "text": "선반영 주장에 가격 근거가 없음."},
        {"role": "bull", "round": 2, "text": "FCF 창출력이 하방을 지지함."},
    ]
    verdict = {"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5,
               "verdict": "관망", "winner": "무승부",
               "key_reason": "양측 논거가 팽팽함",
               "invalidation": ["PER 30 초과 시", "FCF 적자 전환 시"]}
    return transcript, verdict


def test_build_pdf_returns_pdf_bytes():
    transcript, verdict = _sample()
    data = pdf_export.build_pdf("삼성전자(005930)", transcript, verdict, 0.53)
    assert data[:5] == b"%PDF-"
    assert len(data) > 2000


def test_build_pdf_parse_error_verdict():
    transcript, _ = _sample()
    data = pdf_export.build_pdf("T", transcript, {"parse_error": True, "raw": "심판 응답 원문"}, 0.1)
    assert data[:5] == b"%PDF-"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_pdf_export.py -v`
Expected: FAIL (`ModuleNotFoundError: pdf_export`)

- [ ] **Step 3: `pdf_export.py` 구현**

```python
"""토론 결과 → PDF bytes. 한글은 OS 시스템 폰트로 렌더링."""
import datetime
from pathlib import Path

from fpdf import FPDF

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",   # macOS
    "C:/Windows/Fonts/malgun.ttf",                          # Windows 맑은 고딕
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",      # Linux(참고)
]

ROLE_LABEL = {"bear": "Bear (공매도)", "bull": "Bull (매수)"}


def _find_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "한글 폰트를 찾을 수 없음 — macOS(AppleGothic) 또는 Windows(맑은 고딕) 환경에서 실행하세요."
    )


def build_pdf(ticker, transcript, verdict, notional_cost_usd):
    pdf = FPDF()
    pdf.add_font("kr", "", _find_font())
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    # 표지/헤더
    pdf.set_font("kr", size=18)
    pdf.multi_cell(0, 10, f"Bull vs Bear 토론 리포트 — {ticker}")
    pdf.set_font("kr", size=10)
    pdf.multi_cell(0, 6, f"생성일: {datetime.date.today().isoformat()}")
    pdf.ln(4)

    # 판정 요약
    pdf.set_font("kr", size=14)
    pdf.multi_cell(0, 8, "판정 결과")
    pdf.set_font("kr", size=11)
    if verdict.get("parse_error"):
        pdf.multi_cell(0, 6, "심판 JSON 파싱 실패 — 원문:")
        pdf.multi_cell(0, 6, str(verdict.get("raw", "")))
    else:
        pdf.multi_cell(0, 6, f"Verdict: {verdict.get('verdict')}   Winner: {verdict.get('winner')}")
        pdf.multi_cell(
            0, 6,
            f"ORCA — O: {verdict.get('O')}  R: {verdict.get('R')}  "
            f"C: {verdict.get('C')}  A: {verdict.get('A')}  /  Total: {verdict.get('total')}",
        )
        pdf.multi_cell(0, 6, f"핵심 근거: {verdict.get('key_reason', '')}")
        inv = verdict.get("invalidation") or []
        if inv:
            pdf.multi_cell(0, 6, "무효화(반증) 조건:")
            for item in inv:
                pdf.multi_cell(0, 6, f"  - {item}")
    pdf.ln(4)

    # 토론 전문
    pdf.set_font("kr", size=14)
    pdf.multi_cell(0, 8, "토론 전문")
    for m in transcript:
        pdf.set_font("kr", size=12)
        pdf.multi_cell(0, 7, f"[라운드 {m['round']}] {ROLE_LABEL.get(m['role'], m['role'])}")
        pdf.set_font("kr", size=10)
        pdf.multi_cell(0, 5.5, m["text"])
        pdf.ln(3)

    pdf.set_font("kr", size=9)
    pdf.multi_cell(0, 5, f"명목 비용: ${notional_cost_usd:.4f} (구독 기반이므로 실제 청구 없음)")
    return bytes(pdf.output())
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS

- [ ] **Step 5: 육안 확인용 샘플 PDF 생성 (임시 파일, 커밋 금지)**

```bash
.venv/bin/python -c "
import tests.test_pdf_export as t, pdf_export
tr, v = t._sample()
open('/tmp/sample_debate.pdf','wb').write(pdf_export.build_pdf('삼성전자(005930)', tr, v, 0.5))
print('written /tmp/sample_debate.pdf')
"
```

한글이 깨지지 않는지 파일을 열어 확인.

- [ ] **Step 6: Commit**

```bash
git add pdf_export.py tests/test_pdf_export.py
git commit -m "feat: PDF 리포트 생성 — OS별 한글 폰트 자동 탐색"
```

---

### Task 5: app.py (Streamlit UI)

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `claude_cli.preflight()`, `debate_engine.debate()`, `pdf_export.build_pdf()`

- [ ] **Step 1: `app.py` 작성**

```python
import datetime
import json

import streamlit as st

import claude_cli
import debate_engine
import pdf_export

st.set_page_config(page_title="Bull vs Bear Debate", page_icon="⚖️", layout="wide")
st.title("⚖️ Bull vs Bear Debate")

preflight_error = claude_cli.preflight()
if preflight_error:
    st.error(preflight_error)

with st.sidebar:
    ticker = st.text_input("종목명 또는 종목코드", placeholder="삼성전자 또는 005930")
    rounds = st.slider("라운드 수", 1, 4, 2)
    run = st.button(
        "토론 시작",
        type="primary",
        disabled=bool(preflight_error),
        use_container_width=True,
    )

context = st.text_area(
    "컨텍스트",
    height=220,
    placeholder="정량 스크리닝 요약 붙여넣기 — 주가/PER/PSR/수급/오버행 등",
)


def render_message(role, rnd, text):
    with st.chat_message(role, avatar="🐻" if role == "bear" else "🐮"):
        st.caption(f"라운드 {rnd} · {'Bear (공매도)' if role == 'bear' else 'Bull (매수)'}")
        if rnd == 1 and len(text) > 300:
            st.write(text[:300] + "…")
            with st.expander("전문 보기"):
                st.write(text)
        else:
            st.write(text)


just_ran = False
if run:
    if not ticker.strip() or not context.strip():
        st.warning("종목명(또는 종목코드)과 컨텍스트를 모두 입력하세요.")
    else:
        chat_area = st.container()

        def on_message(role, rnd, text):
            with chat_area:
                render_message(role, rnd, text)

        try:
            with st.spinner("토론 진행 중… (라운드당 1~3분 소요)"):
                result = debate_engine.debate(
                    ticker.strip(), context.strip(), rounds=rounds, on_message=on_message
                )
        except Exception as e:
            st.error(f"토론 중단: {e}")
            st.stop()
        st.session_state["result"] = result
        st.session_state["ticker"] = ticker.strip()
        just_ran = True

if "result" in st.session_state:
    result = st.session_state["result"]
    saved_ticker = st.session_state["ticker"]

    if not just_ran:  # 다운로드 버튼 클릭 등 rerun 시 기록에서 다시 그림
        for m in result["transcript"]:
            render_message(m["role"], m["round"], m["text"])

    st.divider()
    st.subheader("🧑‍⚖️ 심판 판정")
    verdict = result["verdict"]
    if verdict.get("parse_error"):
        st.error("심판 응답 JSON 파싱 실패 — 원문:")
        st.code(verdict.get("raw", ""))
    else:
        cols = st.columns(4)
        for col, axis in zip(cols, ["O", "R", "C", "A"]):
            col.metric(axis, f"{verdict.get(axis, '?')} / 2.5")
        v_col, w_col, t_col = st.columns(3)
        v_col.metric("Verdict", verdict.get("verdict", "?"))
        w_col.metric("Winner", verdict.get("winner", "?"))
        t_col.metric("Total", f"{verdict.get('total', '?')} / 10")
        st.markdown(f"**핵심 근거:** {verdict.get('key_reason', '')}")
        inv = verdict.get("invalidation") or []
        if inv:
            st.markdown("**무효화(반증) 조건:**")
            for item in inv:
                st.markdown(f"- {item}")

    date_str = datetime.date.today().strftime("%Y%m%d")
    dl_json, dl_pdf = st.columns(2)
    dl_json.download_button(
        "📄 JSON 다운로드",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name=f"{saved_ticker}_{date_str}.json",
        mime="application/json",
        use_container_width=True,
    )
    try:
        pdf_bytes = pdf_export.build_pdf(
            saved_ticker, result["transcript"], verdict, result["notional_cost_usd"]
        )
        dl_pdf.download_button(
            "📑 PDF 다운로드",
            data=pdf_bytes,
            file_name=f"{saved_ticker}_{date_str}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except RuntimeError as e:
        dl_pdf.error(str(e))

    st.caption(
        f"명목 비용: ${result['notional_cost_usd']:.4f} — 구독 기반이므로 실제 청구 없음"
    )
```

- [ ] **Step 2: 문법/임포트 검증**

```bash
.venv/bin/python -m py_compile app.py && .venv/bin/python -c "import ast; ast.parse(open('app.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 수동 스모크 — 앱 기동 확인**

```bash
.venv/bin/python -m streamlit run app.py --server.headless true &
sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
```

Expected: `200`. 확인 후 streamlit 프로세스 종료.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit UI — 실시간 토론 렌더링, ORCA 판정, JSON/PDF 다운로드"
```

---

### Task 6: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: `README.md` 작성**

````markdown
# ⚖️ bull-bear-debate

공매도(Bear) 에이전트와 가치투자(Bull) 에이전트가 종목을 두고 토론하고,
중립 심판이 **ORCA 점수**(O/R/C/A 각 0~2.5, 총 10점)로 판정하는 로컬 Streamlit 앱.

- **API 키 불필요·추가 과금 없음** — 모든 LLM 호출은 로컬에 로그인된 Claude Code CLI(`claude -p`)를 통해 구독 세션으로 처리
- macOS / Windows 지원, Python 3.11+

## 전제조건

1. [Claude Code CLI](https://claude.com/claude-code) 설치 및 로그인 (`claude login` 또는 앱 최초 실행 시 로그인)
2. 터미널에서 `claude --version`이 동작하는지 확인 (PATH 등록 필요)
3. Python 3.11 이상

## 설치

```bash
git clone https://github.com/Joydalio/bull-bear-debate.git
cd bull-bear-debate
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
pip install -r requirements.txt
```

## 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속 후:

1. 사이드바에 **종목명 또는 상장사 종목코드**(예: `삼성전자` 또는 `005930`) 입력
2. 메인 영역에 정량 스크리닝 요약(주가/PER/PSR/수급/오버행 등) 붙여넣기
3. 라운드 수 선택(1~4, 기본 2) 후 **토론 시작**
4. 판정 후 **JSON / PDF 다운로드** 버튼으로 결과 저장

## 사용 모델

항상 최상위 모델을 사용: `claude-fable-5` 우선, 사용 불가 시 `claude-opus-4-8`로 자동 폴백.

## 알려진 제약

- **로컬 전용** (localhost) — 서버 배포 불가. `claude` CLI 로그인 세션이 있는 머신에서만 동작
- 화면의 "명목 비용"은 CLI가 보고하는 참고 수치일 뿐, 구독 기반이므로 실제 청구 없음
- 인코딩은 utf-8(errors=replace)로 처리해 Windows cp949 환경에서도 한글 깨짐 방지
- PDF 한글 폰트: macOS(AppleGothic) / Windows(맑은 고딕) 시스템 폰트 자동 사용

## 테스트

```bash
pip install pytest
pytest tests/ -v
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — 전제조건, 설치/실행, 제약"
```

---

### Task 7: 실호출 검수 (스펙 검수 기준)

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 단위 테스트**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS

- [ ] **Step 2: 모델 가용성 확인 — fable-5 실호출**

```bash
cd /Users/jun/bull-bear-debate && .venv/bin/python claude_cli.py
```

Expected: `[claude-fable-5] <응답> (명목 비용 $...)` 출력. fable-5가 CLI에서 불가하면 `[claude-opus-4-8]`로 출력되는지 확인 — 어느 쪽이든 폴백 체계가 작동하면 통과.

- [ ] **Step 3: ANTHROPIC_API_KEY 차단 확인 (가짜 키 주입 후 실행)**

```bash
ANTHROPIC_API_KEY=sk-fake-key-must-be-ignored .venv/bin/python claude_cli.py
```

Expected: 가짜 키가 무시되고(제거된 env 전달) 정상 응답. 키가 사용됐다면 인증 오류가 났을 것.

- [ ] **Step 4: debate() 실전 실행 — mock 없이 rounds=2**

```bash
.venv/bin/python -c "
import json, debate_engine
out = debate_engine.debate(
    '삼성전자(005930)',
    '주가 7만원대, PER 12, PSR 1.1, 외국인 순매도 지속, HBM 경쟁 심화 우려, 배당수익률 2.1%',
    rounds=2,
    on_message=lambda role, r, t: print(f'--- R{r} {role} ({len(t)}자) ---'),
)
print('verdict:', json.dumps(out['verdict'], ensure_ascii=False))
print('cost:', out['notional_cost_usd'])
json.dump(out, open('/tmp/debate_smoke.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
"
```

Expected: R1 bear/bull(장문), R2 bear/bull(단문) 순서로 4개 발언 + verdict JSON 출력. 수 분 소요.
확인 사항: R1은 장문(구조화 4항목), R2는 800자 내외 반박인지 → R1/R2 프롬프트 분기 실증.

- [ ] **Step 5: 실전 결과로 PDF 생성 — 한글 깨짐 확인**

```bash
.venv/bin/python -c "
import json, pdf_export
out = json.load(open('/tmp/debate_smoke.json', encoding='utf-8'))
data = pdf_export.build_pdf('삼성전자(005930)', out['transcript'], out['verdict'], out['notional_cost_usd'])
open('/tmp/debate_smoke.pdf','wb').write(data)
print('PDF bytes:', len(data))
"
```

PDF 파일을 열어 한글 렌더링 확인.

- [ ] **Step 6: Streamlit 수동 E2E**

`streamlit run app.py`로 기동 → 종목코드/컨텍스트 입력 → 1라운드 토론 실행 → 실시간 렌더링, 판정 metric, JSON/PDF 다운로드 버튼 동작 확인.

- [ ] **Step 7: 검수 결과를 체크리스트로 보고** (스펙의 검수 기준 각 항목에 통과/실패 명시)

---

### Task 8: GitHub 배포

**Files:** 없음 (git 작업만)

- [ ] **Step 1: gh 인증 확인**

```bash
gh auth status
```

미인증이면 사용자에게 `gh auth login` 요청 후 대기.

- [ ] **Step 2: 저장소 생성 + push** (저장소가 이미 있으면 remote add만)

```bash
cd /Users/jun/bull-bear-debate
gh repo view Joydalio/bull-bear-debate >/dev/null 2>&1 \
  && git remote add origin https://github.com/Joydalio/bull-bear-debate.git \
  || gh repo create Joydalio/bull-bear-debate --public --source . --remote origin
git push -u origin main
```

- [ ] **Step 3: 공개 확인**

```bash
gh repo view Joydalio/bull-bear-debate --json url,visibility
```

Expected: `"visibility": "PUBLIC"` 및 URL 출력. 브라우저에서 README 렌더링 확인.
