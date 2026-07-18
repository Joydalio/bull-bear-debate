# 토너먼트 모드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 최대 5종목 입력 → 종목별 토론 → 비교 변론 → 랭킹 심판 TOP5 + 최종 보고서(분량 선택 PDF).

**Architecture:** 기존 `debate()`는 그대로 두고 `tournament()`가 이를 종목별로 호출한 뒤 변론·랭킹 단계를 추가. UI는 type 필드("single"/"tournament")로 렌더 분기. 모델 선택과 타임아웃은 기존 함수에 선택적 매개변수로 주입.

**Tech Stack:** 기존 그대로 (Streamlit, fpdf2, google-genai, pytest). 신규 의존성 없음.

## Global Constraints

- Python 3.9 호환 문법만 사용 (개발 머신 3.9.6)
- 단일 종목 모드 기존 동작 회귀 금지 — 기존 테스트 15개 전부 통과 유지
- subprocess 규칙 유지: utf-8/errors=replace/shell=False, ANTHROPIC_API_KEY 제거
- 모델 폴백: 명시 선택 모델 실패 시 MODEL_FALLBACK 1회 시도 (Claude: claude-opus-4-8 / Gemini: gemini-2.5-pro)
- 타임아웃 기본값: R1 180초, 반박·심판 90초
- 작업 디렉토리 `/Users/jun/bull-bear-debate`, 파이썬 `.venv/bin/python`
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: 모델 선택 매개변수 (claude_cli + gemini_client)

**Files:**
- Modify: `claude_cli.py` (`_with_fallback`, `ask`, `research`)
- Modify: `gemini_client.py` (`_with_fallback`, `ask`, `research`)
- Test: `tests/test_model_select.py`

**Interfaces:**
- Produces: `claude_cli.ask(system, user, timeout=90, model=None)`, `claude_cli.research(ticker, timeout=300, model=None)`
- Produces: `gemini_client.ask(system, user, api_key, timeout=90, model=None)`, `gemini_client.research(ticker, api_key, timeout=180, model=None)`
- 의미: `model` 지정 시 그 모델을 1순위로 사용, 실패하면 `MODEL_FALLBACK` 1회 시도(전역 캐시는 건드리지 않음). `model=None`이면 기존 동작 그대로.

- [x] **Step 1: 실패하는 테스트 작성** — `tests/test_model_select.py`

```python
import json
import subprocess

import pytest

import claude_cli
import gemini_client


def _fake_proc(stdout="", returncode=0, stderr=""):
    class P:
        pass
    p = P()
    p.stdout = stdout
    p.returncode = returncode
    p.stderr = stderr
    return p


@pytest.fixture(autouse=True)
def reset_models():
    claude_cli._active_model = claude_cli.MODEL_PRIMARY
    gemini_client._active_model = gemini_client.MODEL_PRIMARY


def test_claude_explicit_model_used(monkeypatch):
    used = []

    def fake_run(cmd, **kwargs):
        used.append(cmd[cmd.index("--model") + 1])
        return _fake_proc(json.dumps({"result": "ok", "total_cost_usd": 0, "is_error": False}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cli.ask("s", "u", model="claude-sonnet-5")
    assert used == ["claude-sonnet-5"]


def test_claude_explicit_model_falls_back_without_caching(monkeypatch):
    used = []

    def fake_run(cmd, **kwargs):
        model = cmd[cmd.index("--model") + 1]
        used.append(model)
        if model == "claude-sonnet-5":
            return _fake_proc("", returncode=1, stderr="model error")
        return _fake_proc(json.dumps({"result": "ok", "total_cost_usd": 0, "is_error": False}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = claude_cli.ask("s", "u", model="claude-sonnet-5")
    assert used == ["claude-sonnet-5", claude_cli.MODEL_FALLBACK]
    assert out["model"] == claude_cli.MODEL_FALLBACK
    assert claude_cli._active_model == claude_cli.MODEL_PRIMARY  # 캐시 오염 없음


def test_gemini_explicit_model_used(monkeypatch):
    used = []

    def fake_generate(api_key, model, system, user, timeout, tools=None):
        used.append(model)
        return "응답"

    monkeypatch.setattr(gemini_client, "_generate", fake_generate)
    out = gemini_client.ask("s", "u", "k", model="gemini-2.5-flash")
    assert used == ["gemini-2.5-flash"]
    assert out["model"] == "gemini-2.5-flash"
```

- [x] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_model_select.py -v`
Expected: FAIL (`TypeError: ask() got an unexpected keyword argument 'model'`)

- [x] **Step 3: claude_cli.py 수정**

`_with_fallback`을 다음으로 교체:

```python
def _with_fallback(fn, model=None):
    global _active_model
    primary = model or _active_model
    try:
        return fn(primary)
    except RuntimeError:
        if primary == MODEL_FALLBACK:
            raise
        out = fn(MODEL_FALLBACK)
        if model is None:
            _active_model = MODEL_FALLBACK  # 암묵 경로만 캐시
        return out
```

`ask` 시그니처를 `def ask(system_prompt, user_prompt, timeout=90, model=None):`로, 마지막 줄을 `return _with_fallback(call, model)`로.
`research` 시그니처를 `def research(ticker, timeout=300, model=None):`로, `return _with_fallback(lambda m: ..., model)`로.

- [x] **Step 4: gemini_client.py 수정**

```python
def _with_fallback(fn, model=None):
    global _active_model
    primary = model or _active_model
    try:
        return fn(primary), primary
    except Exception:
        if primary == MODEL_FALLBACK:
            raise
        out = fn(MODEL_FALLBACK)
        if model is None:
            _active_model = MODEL_FALLBACK
        return out, MODEL_FALLBACK
```

`ask(system_prompt, user_prompt, api_key, timeout=90, model=None)` / `research(ticker, api_key, timeout=180, model=None)`에서 `_with_fallback(..., model)` 전달.

- [x] **Step 5: 전체 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 기존 15 + 신규 3 = 18 passed

- [x] **Step 6: Commit**

```bash
git add claude_cli.py gemini_client.py tests/test_model_select.py
git commit -m "feat: ask/research에 모델 명시 선택 매개변수"
```

---

### Task 2: debate() 타임아웃 매개변수

**Files:**
- Modify: `debate_engine.py`
- Test: `tests/test_debate_engine.py` (테스트 추가)

**Interfaces:**
- Produces: `debate(ticker, context, rounds=2, on_message=None, ask_fn=None, r1_timeout=R1_TIMEOUT, rebuttal_timeout=REBUTTAL_TIMEOUT)`
- `_judge(ticker, transcript, ask_fn, timeout)` — rebuttal_timeout 전달

- [x] **Step 1: 실패하는 테스트 추가** — `tests/test_debate_engine.py` 끝에

```python
def test_custom_timeouts_passed(monkeypatch):
    seen = []

    def fake_ask(system, user, timeout=90):
        seen.append(timeout)
        if system == prompts.JUDGE_SYSTEM:
            return {"result": GOOD_JUDGE, "total_cost_usd": 0.0, "is_error": False, "model": "m"}
        return {"result": "발언", "total_cost_usd": 0.0, "is_error": False, "model": "m"}

    monkeypatch.setattr(claude_cli, "ask", fake_ask)
    debate_engine.debate("T", "ctx", rounds=2, r1_timeout=300, rebuttal_timeout=45)
    assert seen == [300, 300, 45, 45, 45]  # R1 bear/bull, R2 bear/bull, judge
```

- [x] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_debate_engine.py::test_custom_timeouts_passed -v`
Expected: FAIL (`TypeError ... unexpected keyword argument 'r1_timeout'`)

- [x] **Step 3: debate_engine.py 수정**

시그니처: `def debate(ticker, context, rounds=2, on_message=None, ask_fn=None, r1_timeout=R1_TIMEOUT, rebuttal_timeout=REBUTTAL_TIMEOUT):`
본문에서 `timeout = R1_TIMEOUT` → `timeout = r1_timeout`, `timeout = REBUTTAL_TIMEOUT` → `timeout = rebuttal_timeout`,
`_judge(ticker, transcript, ask_fn)` → `_judge(ticker, transcript, ask_fn, rebuttal_timeout)`,
`def _judge(ticker, transcript, ask_fn, timeout=REBUTTAL_TIMEOUT):` 안의 `timeout=REBUTTAL_TIMEOUT` 호출부를 `timeout=timeout`으로.

- [x] **Step 4: 통과 확인 후 Commit**

Run: `.venv/bin/python -m pytest tests/ -q` → 19 passed

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: debate() 라운드별 타임아웃 매개변수"
```

---

### Task 3: 프롬프트 3종 + tournament()

**Files:**
- Modify: `prompts.py`, `debate_engine.py`
- Test: `tests/test_tournament.py`

**Interfaces:**
- Produces: `prompts.ADVOCATE_SYSTEM`, `prompts.RANKING_JUDGE_SYSTEM`, `prompts.SUMMARY_SYSTEM_TEMPLATE` (str)
- Produces: `debate_engine.tournament(tickers, rounds, ask_fn, research_fn, on_event=None, r1_timeout=180, rebuttal_timeout=90) -> dict`
  - 반환: `{"type": "tournament", "tickers": [...], "contexts": {t: str}, "results": {t: debate반환dict}, "advocacy": {t: str}, "ranking": dict, "failed": [t...], "notional_cost_usd": float}`
  - `on_event(stage, ticker, detail)` — stage ∈ research/debate/advocate/ranking, debate 단계 detail은 (role, round, text)
  - ranking 파싱 실패 시 `{"parse_error": True, "raw": str}`

- [x] **Step 1: prompts.py 끝에 3종 추가**

```python
ADVOCATE_SYSTEM = """너는 특정 종목의 매수 대표 변호인임. 본인 종목의 개별 토론 판정 결과와 경쟁 종목들의 판정 요약이 주어짐.
- 왜 본인 종목이 경쟁 종목들보다 우선 매수 대상인지 상대 종목의 약점과 본인 종목의 강점을 대비해 변론할 것
- 개별 판정에서 확인된 수치·근거만 사용하고 새로운 수치를 지어내지 말 것
- 한국어, ~함/~임체, 최대 800자."""

RANKING_JUDGE_SYSTEM = """너는 포트폴리오 배분 심판임. 각 종목의 개별 ORCA 판정 결과와 종목 대표들의 비교 변론을 읽고 매수 우선순위를 판정함. 마크다운 백틱 없이 아래 JSON만 출력:
{"ranking": [{"rank": 1, "ticker": "종목명", "reason": "1문장"}], "portfolio_comment": "전체 포트폴리오 관점 1~2문장"}
- ranking 배열은 우선순위 순서대로 전 종목 포함
- 개별 ORCA 총점을 참고하되 종속되지 말 것 — 변론에서 드러난 논리 강도와 리스크 비대칭을 반영해 순위를 정할 것"""

SUMMARY_SYSTEM_TEMPLATE = """너는 금융 리서치 에디터임. 주어진 토론 보고서 전문을 약 {chars}자(A4 약 {pages}장 분량)의 한국어 최종 보고서로 재작성할 것.
- 구조: 결론(랭킹/판정) → 핵심 근거 → 주요 리스크 → 무효화(반증) 조건
- 원문에 있는 수치는 보존하고 새로운 수치를 만들지 말 것
- ~함/~임체. 다른 머리말 없이 보고서 본문만 출력할 것."""
```

- [x] **Step 2: 실패하는 테스트 작성** — `tests/test_tournament.py`

```python
import debate_engine
import prompts

GOOD_JUDGE = (
    '{"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5, "verdict": "관망", '
    '"winner": "무승부", "key_reason": "팽팽함", "invalidation": ["x"]}'
)
GOOD_RANKING = (
    '{"ranking": [{"rank": 1, "ticker": "B사", "reason": "우세"}, '
    '{"rank": 2, "ticker": "A사", "reason": "열세"}], "portfolio_comment": "코멘트"}'
)


def make_env(fail_research=None):
    calls = []

    def ask_fn(system, user, timeout=90):
        calls.append({"system": system, "user": user, "timeout": timeout})
        if system == prompts.JUDGE_SYSTEM:
            return {"result": GOOD_JUDGE, "total_cost_usd": 0.01, "is_error": False, "model": "m"}
        if system == prompts.RANKING_JUDGE_SYSTEM:
            return {"result": GOOD_RANKING, "total_cost_usd": 0.01, "is_error": False, "model": "m"}
        return {"result": f"발언#{len(calls)}", "total_cost_usd": 0.02, "is_error": False, "model": "m"}

    def research_fn(ticker):
        if ticker == fail_research:
            raise RuntimeError("리서치 실패")
        return f"{ticker} 컨텍스트"

    return ask_fn, research_fn, calls


def test_tournament_two_tickers_full_flow():
    ask_fn, research_fn, calls = make_env()
    events = []
    out = debate_engine.tournament(
        ["A사", "B사"], rounds=1, ask_fn=ask_fn, research_fn=research_fn,
        on_event=lambda stage, t, d: events.append((stage, t)),
    )
    assert out["type"] == "tournament"
    assert set(out["results"].keys()) == {"A사", "B사"}
    assert set(out["advocacy"].keys()) == {"A사", "B사"}
    assert out["ranking"]["ranking"][0]["ticker"] == "B사"
    assert out["failed"] == []
    # 변론 시스템 프롬프트 사용 확인
    adv_calls = [c for c in calls if c["system"] == prompts.ADVOCATE_SYSTEM]
    assert len(adv_calls) == 2
    assert "경쟁 종목" in adv_calls[0]["user"] or "B사" in adv_calls[0]["user"]
    # 이벤트 순서: research/debate가 종목별로, 마지막에 ranking
    assert events[0] == ("research", "A사")
    assert events[-1][0] == "ranking"
    assert out["notional_cost_usd"] > 0


def test_tournament_skips_failed_ticker():
    ask_fn, research_fn, calls = make_env(fail_research="B사")
    out = debate_engine.tournament(
        ["A사", "B사", "C사"], rounds=1, ask_fn=ask_fn, research_fn=research_fn)
    assert out["failed"] == ["B사"]
    assert set(out["results"].keys()) == {"A사", "C사"}


def test_tournament_single_survivor_skips_ranking():
    ask_fn, research_fn, calls = make_env(fail_research="B사")
    out = debate_engine.tournament(["A사", "B사"], rounds=1, ask_fn=ask_fn, research_fn=research_fn)
    assert out["failed"] == ["B사"]
    assert out["advocacy"] == {}
    assert out["ranking"] == {}
```

- [x] **Step 3: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_tournament.py -v`
Expected: FAIL (`AttributeError: ... no attribute 'tournament'`)

- [x] **Step 4: debate_engine.py에 구현**

임포트에 `ADVOCATE_SYSTEM, RANKING_JUDGE_SYSTEM` 추가. `_judge`의 파싱 루프를 재사용 가능하게 헬퍼로 추출:

```python
def _ask_json(ask_fn, system, user, timeout):
    """JSON 응답 요청 — 백틱 제거 후 파싱, 실패 시 1회 재시도. (dict, cost) 반환."""
    cost = 0.0
    raw = ""
    for _ in range(2):
        resp = ask_fn(system, user, timeout=timeout)
        cost += resp.get("total_cost_usd") or 0.0
        raw = resp["result"].strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned), cost
        except json.JSONDecodeError:
            continue
    return {"parse_error": True, "raw": raw}, cost
```

`_judge`는 `_ask_json(ask_fn, JUDGE_SYSTEM, user, timeout)` 호출로 축소.

```python
def tournament(tickers, rounds, ask_fn, research_fn, on_event=None,
               r1_timeout=R1_TIMEOUT, rebuttal_timeout=REBUTTAL_TIMEOUT):
    def emit(stage, ticker, detail=None):
        if on_event:
            on_event(stage, ticker, detail)

    contexts, results, failed = {}, {}, []
    cost = 0.0
    for t in tickers:
        try:
            emit("research", t)
            contexts[t] = research_fn(t)
            emit("debate", t)
            out = debate(t, contexts[t], rounds=rounds, ask_fn=ask_fn,
                         on_message=lambda role, r, text, _t=t: emit("debate", _t, (role, r, text)),
                         r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout)
            results[t] = out
            cost += out["notional_cost_usd"]
        except Exception:
            failed.append(t)  # 한 종목 실패가 전체를 죽이지 않음

    advocacy, ranking = {}, {}
    if len(results) >= 2:
        def _summary(t):
            v = results[t]["verdict"]
            return f"- {t}: 총점 {v.get('total')} / verdict {v.get('verdict')} / {v.get('key_reason', '')}"

        for t in results:
            rivals = "\n".join(_summary(x) for x in results if x != t)
            v = results[t]["verdict"]
            user = (f"[본인 종목: {t}]\n개별 판정: 총점 {v.get('total')}, verdict {v.get('verdict')}, "
                    f"핵심 근거: {v.get('key_reason', '')}\n\n경쟁 종목 판정 요약:\n{rivals}")
            emit("advocate", t)
            resp = ask_fn(ADVOCATE_SYSTEM, user, timeout=rebuttal_timeout)
            advocacy[t] = resp["result"]
            cost += resp.get("total_cost_usd") or 0.0

        emit("ranking", None)
        user = ("개별 판정 요약:\n" + "\n".join(_summary(t) for t in results)
                + "\n\n=== 종목별 비교 변론 ===\n"
                + "\n\n".join(f"[{t}]\n{advocacy[t]}" for t in advocacy))
        ranking, jcost = _ask_json(ask_fn, RANKING_JUDGE_SYSTEM, user, rebuttal_timeout)
        cost += jcost

    return {"type": "tournament", "tickers": list(tickers), "contexts": contexts,
            "results": results, "advocacy": advocacy, "ranking": ranking,
            "failed": failed, "notional_cost_usd": cost}
```

- [x] **Step 5: 통과 확인 후 Commit**

Run: `.venv/bin/python -m pytest tests/ -q` → 22 passed

```bash
git add prompts.py debate_engine.py tests/test_tournament.py
git commit -m "feat: tournament() — 종목별 토론, 비교 변론, 랭킹 심판"
```

---

### Task 4: PDF — 토너먼트 보고서 + 요약 PDF

**Files:**
- Modify: `pdf_export.py`
- Test: `tests/test_pdf_export.py` (테스트 추가)

**Interfaces:**
- Produces: `build_tournament_pdf(data: dict) -> bytes` (data = tournament() 반환 형식)
- Produces: `build_text_pdf(title: str, text: str) -> bytes` (요약 PDF용 — 제목 + 본문)

- [x] **Step 1: 실패하는 테스트 추가** — `tests/test_pdf_export.py` 끝에

```python
def test_build_tournament_pdf():
    transcript, verdict = _sample()
    data = {
        "type": "tournament", "tickers": ["A사", "B사"],
        "contexts": {"A사": "ctx", "B사": "ctx"},
        "results": {t: {"transcript": transcript, "verdict": verdict, "notional_cost_usd": 0.1}
                    for t in ["A사", "B사"]},
        "advocacy": {"A사": "A사가 우선임", "B사": "B사가 우선임"},
        "ranking": {"ranking": [{"rank": 1, "ticker": "B사", "reason": "우세"},
                                 {"rank": 2, "ticker": "A사", "reason": "열세"}],
                    "portfolio_comment": "균형 잡힌 구성"},
        "failed": ["C사"], "notional_cost_usd": 0.5,
    }
    out = pdf_export.build_tournament_pdf(data)
    assert out[:5] == b"%PDF-"


def test_build_text_pdf():
    out = pdf_export.build_text_pdf("요약 보고서", "결론: 매수 우선순위는 B사임.\n\n근거: 생략함.")
    assert out[:5] == b"%PDF-"
```

- [x] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_pdf_export.py -v`
Expected: 신규 2개 FAIL (`AttributeError`)

- [x] **Step 3: pdf_export.py에 구현** (기존 `_mc`, `_find_font`, 폰트 로딩 재사용)

```python
def _new_pdf():
    pdf = FPDF()
    pdf.add_font("kr", "", _find_font())
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    return pdf


def build_text_pdf(title, text):
    pdf = _new_pdf()
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, title)
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}")
    pdf.ln(4)
    pdf.set_font("kr", size=10.5)
    _mc(pdf, 0, 5.5, text)
    return bytes(pdf.output())


def build_tournament_pdf(data):
    pdf = _new_pdf()
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, "종목 토너먼트 최종 보고서 — TOP" + str(len(data.get("results", {}))))
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}   대상: {', '.join(data.get('tickers', []))}")
    if data.get("failed"):
        _mc(pdf, 0, 6, f"실패(제외): {', '.join(data['failed'])}")
    pdf.ln(4)

    ranking = data.get("ranking") or {}
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "최종 순위")
    pdf.set_font("kr", size=11)
    if ranking.get("parse_error"):
        _mc(pdf, 0, 6, "랭킹 파싱 실패 — 원문:")
        _mc(pdf, 0, 6, str(ranking.get("raw", "")))
    else:
        for row in ranking.get("ranking", []):
            t = row.get("ticker", "?")
            total = (data["results"].get(t, {}).get("verdict") or {}).get("total", "?")
            _mc(pdf, 0, 6, f"{row.get('rank')}. {t}  (ORCA {total}/10) — {row.get('reason', '')}")
        if ranking.get("portfolio_comment"):
            pdf.ln(2)
            _mc(pdf, 0, 6, f"포트폴리오 코멘트: {ranking['portfolio_comment']}")
    pdf.ln(4)

    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "종목별 판정 요약")
    for t, res in data.get("results", {}).items():
        v = res.get("verdict") or {}
        pdf.set_font("kr", size=12)
        _mc(pdf, 0, 7, f"■ {t}")
        pdf.set_font("kr", size=10)
        _mc(pdf, 0, 5.5, f"Verdict: {v.get('verdict')} / Winner: {v.get('winner')} / Total: {v.get('total')}")
        _mc(pdf, 0, 5.5, f"핵심 근거: {v.get('key_reason', '')}")
        for item in v.get("invalidation") or []:
            _mc(pdf, 0, 5.5, f"  - 무효화: {item}")
        pdf.ln(2)

    if data.get("advocacy"):
        pdf.set_font("kr", size=14)
        _mc(pdf, 0, 8, "비교 변론 전문")
        for t, speech in data["advocacy"].items():
            pdf.set_font("kr", size=12)
            _mc(pdf, 0, 7, f"[{t}]")
            pdf.set_font("kr", size=10)
            _mc(pdf, 0, 5.5, speech)
            pdf.ln(2)

    pdf.set_font("kr", size=9)
    _mc(pdf, 0, 5, f"명목 비용: ${data.get('notional_cost_usd', 0):.4f} (구독 기반이므로 실제 청구 없음)")
    return bytes(pdf.output())
```

기존 `build_pdf`의 헤더 4줄(FPDF 생성~add_page)도 `_new_pdf()` 호출로 교체해 중복 제거.

- [x] **Step 4: 통과 확인 후 Commit**

Run: `.venv/bin/python -m pytest tests/ -q` → 24 passed

```bash
git add pdf_export.py tests/test_pdf_export.py
git commit -m "feat: 토너먼트 보고서 PDF + 요약 텍스트 PDF"
```

---

### Task 5: app.py — UI 통합

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: Task 1~4의 모든 신규 시그니처

변경 사항 (기존 구조 유지, 아래 블록별 교체/추가):

- [x] **Step 1: 사이드바 — 모델 선택 + 종목 다중 입력 + 고급 설정**

백엔드 radio 아래에 모델 selectbox 추가, 종목 입력을 text_area로 교체, 고급 설정 expander 추가:

```python
CLAUDE_MODELS = ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5"]
GEMINI_MODELS = ["gemini-3-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"]
```

sidebar 내부 (radio 바로 아래):

```python
    model_choice = st.selectbox("모델", GEMINI_MODELS if use_gemini else CLAUDE_MODELS)
```

종목 입력 교체:

```python
    tickers_raw = st.text_area(
        "종목명 또는 종목코드 (최대 5개, 줄바꿈/쉼표 구분)",
        height=100, placeholder="삼성전자\nSK하이닉스 또는 005930, 000660",
    )
    tickers = [t.strip() for chunk in tickers_raw.splitlines() for t in chunk.split(",") if t.strip()]
    if len(tickers) > 5:
        st.warning("최대 5개까지만 사용합니다 — 앞의 5개만 진행")
        tickers = tickers[:5]
    rounds = st.slider("라운드 수", 1, 4, 2)
    with st.expander("⚙️ 고급 설정"):
        r1_timeout = st.slider("R1(장문) 타임아웃(초)", 60, 600, 180)
        rebuttal_timeout = st.slider("반박·심판 타임아웃(초)", 30, 300, 90)
    if len(tickers) >= 2:
        est = len(tickers) * (rounds * 2 + 2) + len(tickers) + 1
        st.caption(f"⏱️ 토너먼트 모드: 호출 약 {est}회, 예상 {est}~{est * 2}분")
```

ask_fn/research_fn 클로저에 `model=model_choice` 전달:

```python
if use_gemini:
    def ask_fn(system, user, timeout=90):
        return gemini_client.ask(system, user, gemini_key, timeout=timeout, model=model_choice)

    def research_fn(t):
        return gemini_client.research(t, gemini_key, model=model_choice)
else:
    def ask_fn(system, user, timeout=90):
        return claude_cli.ask(system, user, timeout=timeout, model=model_choice)

    def research_fn(t):
        return claude_cli.research(t, model=model_choice)
```

`ticker` 단일 변수를 쓰던 기존 코드는 `tickers[0]`(단일 모드) 기준으로 정리. 자동 컨텍스트 버튼과 컨텍스트 textarea는 `len(tickers) <= 1`일 때만 표시.

- [x] **Step 2: 실행 분기 — 단일 vs 토너먼트**

기존 `if run:` 블록에서 검증 후 분기:

```python
if run:
    if not tickers:
        st.warning("종목을 1개 이상 입력하세요.")
    elif len(tickers) == 1 and not context.strip():
        st.warning("컨텍스트를 입력하거나 자동 생성 버튼을 사용하세요.")
    elif len(tickers) == 1:
        # 기존 단일 흐름 그대로 + ask_fn에 모델, debate에 타임아웃 전달
        ...기존 코드에 r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout 추가...
    else:
        chat_area = st.container()
        progress_ph = st.empty()

        def on_event(stage, t, detail=None):
            idx = tickers.index(t) + 1 if t in tickers else 0
            if stage == "research":
                progress_ph.markdown(f"⏳ **[{idx}/{len(tickers)}] {t} · 웹 리서치 중…**")
            elif stage == "debate" and detail:
                role, rnd, text = detail
                with chat_area:
                    st.markdown(f"##### {t}")
                    render_message(role, rnd, text)
            elif stage == "debate":
                progress_ph.markdown(f"⏳ **[{idx}/{len(tickers)}] {t} · 토론 중…**")
            elif stage == "advocate":
                progress_ph.markdown(f"⏳ **{t} · 비교 변론 생성 중…**")
            else:
                progress_ph.markdown("⏳ **🏆 최종 랭킹 판정 중…**")

        try:
            result = debate_engine.tournament(
                tickers, rounds=rounds, ask_fn=ask_fn, research_fn=research_fn,
                on_event=on_event, r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout)
        except Exception as e:
            progress_ph.empty()
            st.error(f"토너먼트 중단: {e}")
            st.stop()
        progress_ph.empty()
        st.session_state["result"] = result
        st.session_state["ticker"] = "TOP" + str(len(result["results"]))
        just_ran = True
        os.makedirs(REPORTS_DIR, exist_ok=True)
        fname = os.path.join(REPORTS_DIR, f"TOP5_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        st.toast(f"💾 보고서 자동 저장됨: reports/{os.path.basename(fname)}")
```

단일 모드 저장 dict에 `"type": "single"` 추가.

- [x] **Step 3: 결과 렌더 분기 — 토너먼트 화면**

기존 `if "result" in st.session_state:` 블록에서 `result.get("type") == "tournament"`이면:

```python
def render_tournament(result):
    st.divider()
    st.subheader("🏆 최종 순위")
    ranking = result.get("ranking") or {}
    if ranking.get("parse_error"):
        st.error("랭킹 파싱 실패 — 원문:")
        st.code(ranking.get("raw", ""))
    elif ranking:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        cards = ""
        for i, row in enumerate(ranking.get("ranking", [])):
            t = row.get("ticker", "?")
            v = (result["results"].get(t) or {}).get("verdict") or {}
            cards += (f'<div class="bbd-stat"><div class="v">{medals[i] if i < 5 else ""} {t}</div>'
                      f'<div class="l">ORCA {v.get("total", "?")}/10 · {v.get("verdict", "?")}<br>{row.get("reason", "")}</div></div>')
        st.markdown(f'<div class="bbd-grid">{cards}</div>', unsafe_allow_html=True)
        if ranking.get("portfolio_comment"):
            st.markdown(f"**포트폴리오 코멘트:** {ranking['portfolio_comment']}")
    if result.get("failed"):
        st.warning("실패로 제외된 종목: " + ", ".join(result["failed"]))
    for t, res in result["results"].items():
        with st.expander(f"📊 {t} — 개별 토론 및 판정"):
            for m in res["transcript"]:
                render_message(m["role"], m["round"], m["text"])
            v = res.get("verdict") or {}
            if not v.get("parse_error"):
                st.markdown(f"**개별 판정:** {v.get('verdict')} · 총점 {v.get('total')}/10 — {v.get('key_reason', '')}")
    if result.get("advocacy"):
        with st.expander("🎤 비교 변론 전문"):
            for t, speech in result["advocacy"].items():
                st.markdown(f"**[{t}]**")
                st.write(speech)
```

기존 단일 렌더는 else 분기로 유지. 다운로드 버튼: 토너먼트면 `pdf_export.build_tournament_pdf(result)`와 파일명 `TOP5_{date}.pdf/json`.

- [x] **Step 4: PDF 분량 옵션 (단일/토너먼트 공통)**

다운로드 영역에 추가:

```python
    from prompts import SUMMARY_SYSTEM_TEMPLATE
    pdf_len = st.selectbox("PDF 분량", ["전체(원문)"] + [f"요약 약 {n}장" for n in range(1, 11)])
    if pdf_len != "전체(원문)":
        n_pages = int(pdf_len.replace("요약 약 ", "").replace("장", ""))
        if st.button("📝 요약 PDF 생성"):
            full_text = json.dumps(result, ensure_ascii=False)
            system = SUMMARY_SYSTEM_TEMPLATE.format(chars=n_pages * 1800, pages=n_pages)
            with st.spinner("요약 생성 중…"):
                resp = ask_fn(system, f"다음 보고서를 재작성:\n{full_text}", timeout=r1_timeout)
            st.session_state["summary_pdf"] = pdf_export.build_text_pdf(
                f"{saved_ticker} 요약 보고서 (약 {n_pages}장)", resp["result"])
        if st.session_state.get("summary_pdf"):
            st.download_button("📑 요약 PDF 다운로드", data=st.session_state["summary_pdf"],
                               file_name=f"{saved_ticker}_{date_str}_summary.pdf", mime="application/pdf")
```

- [x] **Step 5: 검증**

```bash
.venv/bin/python -m py_compile app.py && .venv/bin/python -m pytest tests/ -q
```
Expected: compile OK, 24 passed. 이어서 `streamlit run app.py`로 화면 수동 확인 (사이드바에 모델·고급설정, 종목 여러 줄 입력).

- [x] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: 토너먼트 UI — 다중 종목, 모델 선택, 타임아웃, 랭킹 화면, PDF 분량"
```

---

### Task 6: README + 실전 검수 + push

**Files:**
- Modify: `README.md`

- [x] **Step 1: README 갱신** — 사용법 섹션에 추가:

```markdown
### 토너먼트 모드 (다중 종목 비교)

종목을 2~5개 입력하면(줄바꿈/쉼표 구분) 종목별 토론 후 비교 변론과 랭킹 심판을 거쳐
매수 우선순위 TOP5를 정하고 최종 보고서를 만든다. 컨텍스트는 종목별로 자동 리서치된다.
5종목×2라운드 기준 약 30분 소요.

### 기타 옵션

- **모델 선택**: 사이드바에서 백엔드별 모델 선택 (기본값 = 최상위 모델)
- **고급 설정**: 라운드별 타임아웃 조정 (기본값이 최적값)
- **PDF 분량**: 전체 원문 또는 AI 요약 약 1~10장 선택
```

- [x] **Step 2: 실전 검수 — 2종목×1라운드 실호출** (mock 없이, 수 분 소요)

```bash
.venv/bin/python -c "
import json, claude_cli, debate_engine
out = debate_engine.tournament(
    ['삼성전자(005930)', 'SK하이닉스(000660)'], rounds=1,
    ask_fn=claude_cli.ask, research_fn=claude_cli.research,
    on_event=lambda s, t, d=None: print(s, t, '' if not (s=='debate' and d) else f'{d[0]} {len(d[2])}자', flush=True))
print(json.dumps(out['ranking'], ensure_ascii=False))
print('failed:', out['failed'], 'cost:', out['notional_cost_usd'])
"
```

Expected: research→debate(bear/bull)×2종목→advocate×2→ranking 순 이벤트, ranking JSON에 두 종목 rank 1·2.

- [x] **Step 3: 스펙 검수 기준 체크리스트 보고 후 push**

```bash
git push
```
