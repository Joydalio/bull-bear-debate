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
