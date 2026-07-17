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
        on_event=lambda stage, t, d=None: events.append((stage, t)),
    )
    assert out["type"] == "tournament"
    assert set(out["results"].keys()) == {"A사", "B사"}
    assert set(out["advocacy"].keys()) == {"A사", "B사"}
    assert out["ranking"]["ranking"][0]["ticker"] == "B사"
    assert out["failed"] == []
    adv_calls = [c for c in calls if c["system"] == prompts.ADVOCATE_SYSTEM]
    assert len(adv_calls) == 2
    assert "경쟁 종목" in adv_calls[0]["user"]
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
