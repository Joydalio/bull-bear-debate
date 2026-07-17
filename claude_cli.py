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


def _exec(model, args, timeout):
    """claude -p 실행 후 JSON 파싱. 실패 시 stderr 포함 예외."""
    proc = _run([_claude_bin(), "-p"] + args + ["--output-format", "json", "--model", model], timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI 실패 (model={model}, code={proc.returncode}): {proc.stderr.strip()}"
        )
    data = json.loads(proc.stdout)
    if data.get("is_error"):
        raise RuntimeError(
            f"claude 응답 오류 (model={model}): {data.get('result')} {proc.stderr.strip()}"
        )
    return data


def _with_fallback(fn):
    global _active_model
    try:
        return fn(_active_model)
    except RuntimeError:
        if _active_model != MODEL_PRIMARY:
            raise
        out = fn(MODEL_FALLBACK)
        _active_model = MODEL_FALLBACK  # 성공한 폴백을 캐시해 이후 호출 재시도 방지
        return out


def ask(system_prompt, user_prompt, timeout=90):
    def call(model):
        data = _exec(model, [user_prompt, "--system-prompt", system_prompt, "--max-turns", "1"], timeout)
        return {
            "result": data.get("result", ""),
            "total_cost_usd": data.get("total_cost_usd") or 0.0,
            "is_error": False,
            "model": model,
        }

    return _with_fallback(call)


def research(ticker, timeout=300):
    """웹검색으로 종목 정량 스크리닝 요약을 자동 생성. 반환: 요약 문자열."""
    from prompts import RESEARCH_PROMPT_TEMPLATE

    prompt = RESEARCH_PROMPT_TEMPLATE.format(ticker=ticker)
    return _with_fallback(
        lambda m: _exec(m, [prompt, "--allowedTools", "WebSearch"], timeout).get("result", "")
    )


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
