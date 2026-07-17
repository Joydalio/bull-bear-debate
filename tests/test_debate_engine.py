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


GOOD_JUDGE = (
    '{"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5, "verdict": "관망", '
    '"winner": "무승부", "key_reason": "팽팽함", "invalidation": ["PER 30 초과 시"]}'
)


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
    captured = []

    def fake_ask(system, user, timeout=90):
        captured.append(user)
        if system == prompts.JUDGE_SYSTEM:
            return {"result": GOOD_JUDGE, "total_cost_usd": 0.0, "is_error": False, "model": "m"}
        return {"result": long_text, "total_cost_usd": 0.0, "is_error": False, "model": "m"}

    monkeypatch.setattr(claude_cli, "ask", fake_ask)
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


def test_judge_double_failure_returns_raw(monkeypatch):
    fake_ask, _ = make_fake_ask(["깨진 응답1", "깨진 응답2"])
    monkeypatch.setattr(claude_cli, "ask", fake_ask)
    out = debate_engine.debate("T", "ctx", rounds=1)
    assert out["verdict"]["parse_error"] is True
    assert out["verdict"]["raw"] == "깨진 응답2"
