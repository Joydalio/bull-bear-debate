import datetime
import glob
import json
import os
import re

import streamlit as st

import claude_cli
import debate_engine
import gemini_client
import pdf_export

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

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
.bbd-msg { border-left: 3px solid #2b2c38; padding-left: 14px; margin-left: 4px; }
.bbd-grid { display: flex; gap: 12px; flex-wrap: wrap; margin: 8px 0 16px 0; }
.bbd-stat { background: #21222D; border-radius: 12px; padding: 16px 20px; min-width: 130px; flex: 1; }
.bbd-stat .v { font-size: 1.7rem; font-weight: 800; }
.bbd-stat .l { color: #87888C; font-size: 0.78rem; margin-top: 2px; }
.bbd-bar-row { display: flex; align-items: center; gap: 10px; margin: 7px 0; }
.bbd-bar-row .axis { width: 20px; font-weight: 700; color: #87888C; }
.bbd-bar-bg { flex: 1; height: 8px; background: #2b2c38; border-radius: 4px; }
.bbd-bar-fill { height: 8px; border-radius: 4px; }
.bbd-bar-row .score { width: 70px; text-align: right; font-size: 0.85rem; color: #87888C; }
</style>""", unsafe_allow_html=True)

st.title("⚖️ Bull vs Bear Debate")

with st.sidebar:
    backend = st.radio("LLM 백엔드", ["Claude (로컬 CLI)", "Gemini (API 키)"])
    use_gemini = backend.startswith("Gemini")

    backend_error = None
    gemini_key = ""
    if use_gemini:
        gemini_key = st.text_input(
            "Gemini API 키",
            type="password",
            help="키는 브라우저 세션에만 보관되며 디스크에 저장되지 않습니다.",
        )
        st.caption("🔑 키 발급: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)")
        if not gemini_key:
            backend_error = "Gemini API 키를 입력하세요."
    else:
        backend_error = claude_cli.preflight()

    if backend_error:
        st.warning(backend_error)

    ticker = st.text_input("종목명 또는 종목코드", placeholder="삼성전자 또는 005930")
    rounds = st.slider("라운드 수", 1, 4, 2)
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

if use_gemini:
    def ask_fn(system, user, timeout=90):
        return gemini_client.ask(system, user, gemini_key, timeout=timeout)

    def research_fn(t):
        return gemini_client.research(t, gemini_key)
else:
    ask_fn = claude_cli.ask
    research_fn = claude_cli.research

auto_ctx = st.button(
    "🔍 AI로 컨텍스트 자동 생성 (웹검색, 1~3분)",
    disabled=bool(backend_error),
)
if auto_ctx:
    if not ticker.strip():
        st.warning("먼저 사이드바에 종목명(또는 종목코드)을 입력하세요.")
    else:
        try:
            with st.spinner("웹에서 최신 정량 데이터를 조사하는 중…"):
                st.session_state["context_text"] = research_fn(ticker.strip())
        except Exception as e:
            st.error(f"컨텍스트 자동 생성 실패: {e}")

context = st.text_area(
    "컨텍스트",
    height=220,
    key="context_text",
    placeholder="정량 스크리닝 요약 붙여넣기 — 주가/PER/PSR/수급/오버행 등 (또는 위 버튼으로 자동 생성)",
)


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


just_ran = False
if run:
    if not ticker.strip() or not context.strip():
        st.warning("종목명(또는 종목코드)과 컨텍스트를 모두 입력하세요.")
    else:
        chat_area = st.container()
        progress_ph = st.empty()
        progress_ph.markdown(f"⏳ **라운드 1 · 🐻 Bear 발언 생성 중…**")

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
            with st.spinner("토론 진행 중… (라운드당 1~3분 소요)"):
                result = debate_engine.debate(
                    ticker.strip(), context.strip(), rounds=rounds,
                    on_message=on_message, ask_fn=ask_fn,
                )
        except Exception as e:
            progress_ph.empty()
            st.error(f"토론 중단: {e}")
            st.stop()
        progress_ph.empty()
        st.session_state["result"] = result
        st.session_state["ticker"] = ticker.strip()
        just_ran = True
        # 보고서 자동 저장
        os.makedirs(REPORTS_DIR, exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]', "_", ticker.strip())
        fname = os.path.join(REPORTS_DIR, f"{safe}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump({"ticker": ticker.strip(), **result}, f, ensure_ascii=False, indent=2)
        st.toast(f"💾 보고서 자동 저장됨: reports/{os.path.basename(fname)}")

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
