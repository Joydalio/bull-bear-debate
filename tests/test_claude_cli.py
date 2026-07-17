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
