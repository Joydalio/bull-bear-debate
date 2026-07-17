"""토론 결과 → PDF bytes. 한글은 OS 시스템 폰트로 렌더링."""
import datetime
from pathlib import Path

from fpdf import FPDF

FONT_CANDIDATES = [
    # macOS — AppleGothic.ttf는 OS/2 테이블이 없어 fpdf2가 로드 불가, Arial Unicode 사용
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/malgun.ttf",                          # Windows 맑은 고딕
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",      # Linux(참고)
]

ROLE_LABEL = {"bear": "Bear (공매도)", "bull": "Bull (매수)"}


def _mc(pdf, w, h, text):
    # multi_cell 기본값이 커서를 오른쪽 끝에 두어 다음 셀 폭이 0이 되는 것 방지
    pdf.multi_cell(w, h, text, new_x="LMARGIN", new_y="NEXT")


def _find_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "한글 폰트를 찾을 수 없음 — macOS(Arial Unicode) 또는 Windows(맑은 고딕) 환경에서 실행하세요."
    )


def build_pdf(ticker, transcript, verdict, notional_cost_usd):
    pdf = FPDF()
    pdf.add_font("kr", "", _find_font())
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    # 표지/헤더
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, f"Bull vs Bear 토론 리포트 — {ticker}")
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}")
    pdf.ln(4)

    # 판정 요약
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "판정 결과")
    pdf.set_font("kr", size=11)
    if verdict.get("parse_error"):
        _mc(pdf, 0, 6, "심판 JSON 파싱 실패 — 원문:")
        _mc(pdf, 0, 6, str(verdict.get("raw", "")))
    else:
        _mc(pdf, 0, 6, f"Verdict: {verdict.get('verdict')}   Winner: {verdict.get('winner')}")
        _mc(pdf, 
            0, 6,
            f"ORCA — O: {verdict.get('O')}  R: {verdict.get('R')}  "
            f"C: {verdict.get('C')}  A: {verdict.get('A')}  /  Total: {verdict.get('total')}",
        )
        _mc(pdf, 0, 6, f"핵심 근거: {verdict.get('key_reason', '')}")
        inv = verdict.get("invalidation") or []
        if inv:
            _mc(pdf, 0, 6, "무효화(반증) 조건:")
            for item in inv:
                _mc(pdf, 0, 6, f"  - {item}")
    pdf.ln(4)

    # 토론 전문
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "토론 전문")
    for m in transcript:
        pdf.set_font("kr", size=12)
        _mc(pdf, 0, 7, f"[라운드 {m['round']}] {ROLE_LABEL.get(m['role'], m['role'])}")
        pdf.set_font("kr", size=10)
        _mc(pdf, 0, 5.5, m["text"])
        pdf.ln(3)

    pdf.set_font("kr", size=9)
    _mc(pdf, 0, 5, f"명목 비용: ${notional_cost_usd:.4f} (구독 기반이므로 실제 청구 없음)")
    return bytes(pdf.output())
