import pytest

import debate_engine
import gemini_client
import prompts


GOOD_JUDGE = (
    '{"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5, "verdict": "관망", '
    '"winner": "무승부", "key_reason": "팽팽함", "invalidation": ["PER 30 초과 시"]}'
)


def test_debate_uses_injected_ask_fn():
    calls = []

    def fake_ask(system, user, timeout=90):
        calls.append(system)
        if system == prompts.JUDGE_SYSTEM:
            return {"result": GOOD_JUDGE, "total_cost_usd": 0.0, "is_error": False, "model": "g"}
        return {"result": "발언", "total_cost_usd": 0.0, "is_error": False, "model": "g"}

    out = debate_engine.debate("T", "ctx", rounds=1, ask_fn=fake_ask)
    assert len(calls) == 3  # bear, bull, judge — 주입한 함수만 사용됨
    assert out["verdict"]["verdict"] == "관망"


@pytest.fixture(autouse=True)
def reset_gemini_model():
    gemini_client._active_model = gemini_client.MODEL_PRIMARY


def test_gemini_ask_fallback_and_cache(monkeypatch):
    used = []

    def fake_generate(api_key, model, system, user, timeout, tools=None):
        used.append(model)
        if model == gemini_client.MODEL_PRIMARY:
            raise RuntimeError("model unavailable")
        return "응답"

    monkeypatch.setattr(gemini_client, "_generate", fake_generate)
    out1 = gemini_client.ask("s", "u", "fake-key")
    out2 = gemini_client.ask("s", "u", "fake-key")
    assert used == [
        gemini_client.MODEL_PRIMARY,
        gemini_client.MODEL_FALLBACK,
        gemini_client.MODEL_FALLBACK,
    ]
    assert out1["model"] == gemini_client.MODEL_FALLBACK
    assert out2["result"] == "응답"
    assert out1["total_cost_usd"] == 0.0


def test_gemini_research_uses_template(monkeypatch):
    captured = {}

    def fake_generate(api_key, model, system, user, timeout, tools=None):
        captured["user"] = user
        captured["tools"] = tools
        return "요약문"

    monkeypatch.setattr(gemini_client, "_generate", fake_generate)
    out = gemini_client.research("삼성전자", "fake-key")
    assert out == "요약문"
    assert "삼성전자" in captured["user"]
    assert captured["tools"] is not None  # google_search 그라운딩 사용
