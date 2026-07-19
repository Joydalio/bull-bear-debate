import datetime
import glob
import json
import os
import re

import streamlit as st

import claude_api
import claude_cli
import debate_engine
import gemini_client
import openai_client
import pdf_export
from prompts import SUMMARY_SYSTEM_TEMPLATE

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

CLAUDE_MODELS = ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5"]
GEMINI_MODELS = ["gemini-3-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"]
GPT_MODELS = ["gpt-5.1", "gpt-5", "gpt-5-mini"]

# API 키 백엔드: 모듈·키 입력 라벨·발급 링크 (로컬 CLI는 별도 분기)
API_BACKENDS = {
    "Claude (API 키)": (claude_api, "Claude API 키",
                       "[platform.claude.com](https://platform.claude.com/settings/keys)"),
    "GPT (API 키)": (openai_client, "OpenAI API 키",
                    "[platform.openai.com](https://platform.openai.com/api-keys)"),
    "Gemini (API 키)": (gemini_client, "Gemini API 키",
                       "[aistudio.google.com/apikey](https://aistudio.google.com/apikey)"),
}

st.set_page_config(page_title="Bull vs Bear Debate", page_icon="⚖️", layout="wide")

# Figma(Nickelfox Sales Dashboard) 팔레트: bg #171821 / card #21222D / mint #A9DFD8
BEAR_COLOR = "#FCB859"  # amber
BULL_COLOR = "#A9DFD8"  # mint
AXIS_COLORS = {"O": "#FCB859", "R": "#A0C5E8", "C": "#A9DFD8", "A": "#F2C8ED"}
VERDICT_COLORS = {"매수": "#A9DFD8", "관망": "#87888C", "매도": "#F97B7B"}

st.markdown("""<style>
h1 { font-size: 1.6rem !important; letter-spacing: -0.02em; }
[data-testid="stSidebar"] { background: #101118; border-right: 1px solid #2b2c38; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; border: 1px solid #2b2c38; }
[data-testid="stExpander"] { background: #21222D; border-radius: 10px; border: 1px solid #2b2c38; }
.stTextArea textarea, .stTextInput input { background: #21222D !important; border-radius: 10px; }
.bbd-role { display: inline-block; padding: 4px 12px; border-radius: 8px; font-size: 0.8rem;
            font-weight: 700; background: #21222D; margin: 14px 0 4px 0; }
.bbd-grid { display: flex; gap: 12px; flex-wrap: wrap; margin: 8px 0 16px 0; }
.bbd-stat { background: #21222D; border-radius: 12px; padding: 16px 20px; min-width: 130px; flex: 1; }
.bbd-stat .v { font-size: 1.7rem; font-weight: 800; }
.bbd-stat .l { color: #87888C; font-size: 0.78rem; margin-top: 2px; }
.bbd-rank .v { font-size: 1.2rem; }
.bbd-bar-row { display: flex; align-items: center; gap: 10px; margin: 7px 0; }
.bbd-bar-row .axis { width: 20px; font-weight: 700; color: #87888C; }
.bbd-bar-bg { flex: 1; height: 8px; background: #2b2c38; border-radius: 4px; }
.bbd-bar-fill { height: 8px; border-radius: 4px; }
.bbd-bar-row .score { width: 70px; text-align: right; font-size: 0.85rem; color: #87888C; }
</style>""", unsafe_allow_html=True)

st.title("⚖️ Bull vs Bear Debate")

with st.sidebar:
    backend = st.radio(
        "LLM 백엔드",
        ["Claude (로컬 CLI)", "Claude (API 키)", "GPT (API 키)", "Gemini (API 키)"],
    )
    model_choice = st.selectbox(
        "모델",
        GEMINI_MODELS if backend.startswith("Gemini")
        else GPT_MODELS if backend.startswith("GPT") else CLAUDE_MODELS,
    )

    backend_error = None
    api_key = ""
    if backend in API_BACKENDS:
        _, key_label, key_link = API_BACKENDS[backend]
        api_key = st.text_input(
            key_label,
            type="password",
            help="키는 브라우저 세션에만 보관되며 디스크에 저장되지 않습니다. API는 사용량만큼 과금됩니다.",
        )
        st.caption(f"🔑 키 발급: {key_link}")
        if not api_key:
            backend_error = f"{key_label}를 입력하세요."
    else:
        backend_error = claude_cli.preflight()

    if backend_error:
        st.warning(backend_error)

    tickers_raw = st.text_area(
        "종목명 또는 종목코드 (최대 5개, 줄바꿈/쉼표 구분)",
        height=100,
        placeholder="삼성전자\nSK하이닉스 또는 005930, 000660",
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
        st.caption(f"⏱️ 토너먼트 모드: LLM 호출 약 {est}회, 예상 {est}~{est * 2}분")

    run = st.button(
        "토론 시작",
        type="primary",
        disabled=bool(backend_error),
        use_container_width=True,
    )

    saved = sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json")), reverse=True)
    if saved:
        st.divider()
        pick = st.selectbox(
            "📂 지난 보고서",
            ["— 선택 —"] + [os.path.basename(p)[:-5] for p in saved],
        )
        if pick != "— 선택 —" and st.session_state.get("loaded_report") != pick:
            with open(os.path.join(REPORTS_DIR, pick + ".json"), encoding="utf-8") as f:
                data = json.load(f)
            st.session_state["result"] = data
            st.session_state["ticker"] = data.get("ticker", pick)
            st.session_state["loaded_report"] = pick

if backend in API_BACKENDS:
    _backend_mod = API_BACKENDS[backend][0]

    def ask_fn(system, user, timeout=90):
        return _backend_mod.ask(system, user, api_key, timeout=timeout, model=model_choice)

    def research_fn(t):
        return _backend_mod.research(t, api_key, model=model_choice)
else:
    def ask_fn(system, user, timeout=90):
        return claude_cli.ask(system, user, timeout=timeout, model=model_choice)

    def research_fn(t):
        return claude_cli.research(t, model=model_choice)

context = ""
if len(tickers) <= 1:
    auto_ctx = st.button(
        "🔍 AI로 컨텍스트 자동 생성 (웹검색, 1~3분)",
        disabled=bool(backend_error),
    )
    if auto_ctx:
        if not tickers:
            st.warning("먼저 사이드바에 종목명(또는 종목코드)을 입력하세요.")
        else:
            try:
                with st.spinner("웹에서 최신 정량 데이터를 조사하는 중…"):
                    st.session_state["context_text"] = research_fn(tickers[0])
            except Exception as e:
                st.error(f"컨텍스트 자동 생성 실패: {e}")

    context = st.text_area(
        "컨텍스트",
        height=220,
        key="context_text",
        placeholder="정량 스크리닝 요약 붙여넣기 — 주가/PER/PSR/수급/오버행 등 (또는 위 버튼으로 자동 생성)",
    )
else:
    st.info(f"토너먼트 모드: {len(tickers)}개 종목의 컨텍스트는 종목별로 자동 리서치됩니다.")


def render_message(role, rnd, text):
    color = BEAR_COLOR if role == "bear" else BULL_COLOR
    icon, label = ("🐻", "Bear (공매도)") if role == "bear" else ("🐮", "Bull (매수)")
    st.markdown(
        f'<span class="bbd-role" style="color:{color}; border:1px solid {color}55">'
        f'{icon} 라운드 {rnd} · {label}</span>',
        unsafe_allow_html=True,
    )
    if rnd == 1 and len(text) > 300:
        st.write(text[:300] + "…")
        with st.expander("전문 보기"):
            st.write(text)
    else:
        st.write(text)


def save_report(result, prefix):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", prefix)
    fname = os.path.join(REPORTS_DIR, f"{safe}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    st.toast(f"💾 보고서 자동 저장됨: reports/{os.path.basename(fname)}")


just_ran = False
if run:
    if not tickers:
        st.warning("종목을 1개 이상 입력하세요.")
    elif len(tickers) == 1 and not context.strip():
        st.warning("컨텍스트를 입력하거나 자동 생성 버튼을 사용하세요.")
    elif len(tickers) == 1:
        ticker = tickers[0]
        chat_area = st.container()
        progress_ph = st.empty()
        progress_ph.markdown("⏳ **라운드 1 · 🐻 Bear 발언 생성 중…**")

        def on_message(role, rnd, text):
            with chat_area:
                render_message(role, rnd, text)
            if role == "bear":
                nxt = f"라운드 {rnd} · 🐮 Bull 발언 생성 중…"
            elif rnd < rounds:
                nxt = f"라운드 {rnd + 1} · 🐻 Bear 발언 생성 중…"
            else:
                nxt = "🧑‍⚖️ 심판 판정 중…"
            progress_ph.markdown(f"⏳ **{nxt}**")

        try:
            result = debate_engine.debate(
                ticker, context.strip(), rounds=rounds,
                on_message=on_message, ask_fn=ask_fn,
                r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout,
            )
        except Exception as e:
            progress_ph.empty()
            st.error(f"토론 중단: {e}")
            st.stop()
        progress_ph.empty()
        result["type"] = "single"
        result["ticker"] = ticker
        st.session_state["result"] = result
        st.session_state["ticker"] = ticker
        just_ran = True
        save_report(result, ticker)
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
                on_event=on_event, r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout,
            )
        except Exception as e:
            progress_ph.empty()
            st.error(f"토너먼트 중단: {e}")
            st.stop()
        progress_ph.empty()
        st.session_state["result"] = result
        st.session_state["ticker"] = "TOP" + str(len(result["results"]))
        just_ran = True
        save_report(result, "TOP5")


def render_single_verdict(verdict):
    if verdict.get("parse_error"):
        st.error("심판 응답 JSON 파싱 실패 — 원문:")
        st.code(verdict.get("raw", ""))
        return
    v = verdict.get("verdict", "?")
    v_color = VERDICT_COLORS.get(v, "#87888C")
    winner = verdict.get("winner", "?")
    w_icon = {"bear": "🐻", "bull": "🐮"}.get(winner, "🤝")
    bars = "".join(
        f'<div class="bbd-bar-row"><span class="axis">{axis}</span>'
        f'<div class="bbd-bar-bg"><div class="bbd-bar-fill" style="width:{min(float(verdict.get(axis, 0)) / 2.5 * 100, 100):.0f}%;'
        f'background:{AXIS_COLORS[axis]}"></div></div>'
        f'<span class="score">{verdict.get(axis, "?")} / 2.5</span></div>'
        for axis in ["O", "R", "C", "A"]
    )
    st.markdown(
        f'<div class="bbd-grid">'
        f'<div class="bbd-stat" style="border:1px solid {v_color}66">'
        f'<div class="v" style="color:{v_color}">{v}</div><div class="l">Verdict</div></div>'
        f'<div class="bbd-stat"><div class="v">{w_icon} {winner}</div><div class="l">Winner</div></div>'
        f'<div class="bbd-stat"><div class="v">{verdict.get("total", "?")}<span style="font-size:0.9rem;color:#87888C"> / 10</span></div>'
        f'<div class="l">ORCA Total</div></div>'
        f'<div class="bbd-stat" style="flex:2;min-width:260px">{bars}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"**핵심 근거:** {verdict.get('key_reason', '')}")
    inv = verdict.get("invalidation") or []
    if inv:
        st.markdown("**무효화(반증) 조건:**")
        for item in inv:
            st.markdown(f"- {item}")


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
            cards += (
                f'<div class="bbd-stat bbd-rank"><div class="v">{medals[i] if i < 5 else ""} {t}</div>'
                f'<div class="l">ORCA {v.get("total", "?")}/10 · {v.get("verdict", "?")}<br>{row.get("reason", "")}</div></div>'
            )
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


if "result" in st.session_state:
    result = st.session_state["result"]
    saved_ticker = st.session_state["ticker"]
    is_tournament = result.get("type") == "tournament"

    if is_tournament:
        render_tournament(result)
    else:
        if not just_ran:  # 다운로드 버튼 클릭 등 rerun 시 기록에서 다시 그림
            for m in result["transcript"]:
                render_message(m["role"], m["round"], m["text"])
        st.divider()
        st.subheader("🧑‍⚖️ 심판 판정")
        render_single_verdict(result["verdict"])

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
        if is_tournament:
            pdf_bytes = pdf_export.build_tournament_pdf(result)
        else:
            pdf_bytes = pdf_export.build_pdf(
                saved_ticker, result["transcript"], result["verdict"], result["notional_cost_usd"]
            )
        dl_pdf.download_button(
            "📑 PDF 다운로드 (전체)",
            data=pdf_bytes,
            file_name=f"{saved_ticker}_{date_str}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except RuntimeError as e:
        dl_pdf.error(str(e))

    pdf_len = st.selectbox("PDF 분량", ["전체(원문)"] + [f"요약 약 {n}장" for n in range(1, 11)])
    if pdf_len != "전체(원문)":
        n_pages = int(pdf_len.replace("요약 약 ", "").replace("장", ""))
        if st.button("📝 요약 PDF 생성", disabled=bool(backend_error)):
            full_text = json.dumps(result, ensure_ascii=False)
            system = SUMMARY_SYSTEM_TEMPLATE.format(chars=n_pages * 1800, pages=n_pages)
            try:
                with st.spinner("요약 생성 중…"):
                    resp = ask_fn(system, f"다음 보고서를 재작성:\n{full_text}", timeout=r1_timeout)
                st.session_state["summary_pdf"] = pdf_export.build_text_pdf(
                    f"{saved_ticker} 요약 보고서 (약 {n_pages}장)", resp["result"]
                )
            except Exception as e:
                st.error(f"요약 생성 실패: {e}")
        if st.session_state.get("summary_pdf"):
            st.download_button(
                "📑 요약 PDF 다운로드",
                data=st.session_state["summary_pdf"],
                file_name=f"{saved_ticker}_{date_str}_summary.pdf",
                mime="application/pdf",
            )

    st.caption(
        f"명목 비용: ${result['notional_cost_usd']:.4f} — 구독 기반이므로 실제 청구 없음"
    )
