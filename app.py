import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ==========================================
# 1. 페이지 기본 설정 및 상태 초기화
# ==========================================
st.set_page_config(page_title="한/미 통합 주식 실시간 마스터 대시보드", layout="wide")

STOCK_MAP = {
    "TSLA": "Tesla", "NVDA": "Nvidia", "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon",
    "GOOGL": "Alphabet", "META": "Meta Platforms", "NFLX": "Netflix", "IONQ": "IonQ", "PLTR": "Palantir",
    "AMD": "AMD", "SOFI": "SoFi", "MARA": "Marathon Digital", "COIN": "Coinbase", "BABA": "Alibaba",
    "AVGO": "Broadcom", "QCOM": "Qualcomm", "INTC": "Intel", "SMCI": "Super Micro Computer", "CRM": "Salesforce",
    "ORCL": "Oracle", "UBER": "Uber", "HOOD": "Robinhood", "SQ": "Block", "PYPL": "PayPal",
    "MU": "Micron Technology", "SOL-USD": "Solana", "SMH": "VanEck Semiconductor ETF",
    "TQQQ": "ProShares TQQQ", "SOXL": "Direxion SOXL", "SPY": "SPDR S&P 500", "QQQ": "Invesco QQQ",
    "LLY": "Eli Lilly", "TSM": "TSMC", "ASML": "ASML", "CVNA": "Carvana", "WMT": "Walmart",
    "COST": "Costco", "NET": "Cloudflare", "RKLB": "Rocket Lab", "ASTS": "AST SpaceMobile",

    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005450.KQ": "형지I&C", "042660.KS": "한화오션",
    "035420.KS": "NAVER", "035720.KS": "카카오", "005380.KS": "현대차", "000270.KS": "기아",  # 버그수정: 0000270 → 000270
    "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "068270.KS": "셀트리온", "005490.KS": "POSCO홀딩스",
    "373220.KS": "LG에너지솔루션", "000100.KS": "유한양행", "012330.KS": "현대모비스", "207940.KS": "삼성바이오로직스",
    "051910.KS": "LG화학", "006400.KS": "삼성SDI", "015760.KS": "한국전력", "012450.KS": "한화에어로스페이스",
    "066570.KS": "LG전자", "034020.KS": "두산에너빌리티", "009540.KS": "HD한국조선해양", "267250.KS": "HD현대일렉트릭",
    "035900.KQ": "JYP Ent.", "041510.KQ": "에스엠", "259960.KS": "크래프톤", "105560.KS": "KB금융",
    "055550.KS": "신한지주", "000030.KS": "우리금융지주", "011200.KS": "HMM", "009830.KS": "한화솔루션",
    "272210.KS": "한화시스템", "402340.KS": "SK스퀘어", "022100.KQ": "포스코DX", "058470.KQ": "리노공업",
    "293490.KQ": "카카오게임즈", "263750.KQ": "펄어비스", "138040.KS": "메리츠금융지주", "003550.KS": "LG"
}
INV_STOCK_MAP = {k.lower(): k for k in STOCK_MAP.keys()}
for k, v in STOCK_MAP.items():
    INV_STOCK_MAP[v.lower()] = k
US_SCAN_LIST = [k for k in STOCK_MAP.keys() if not k.endswith((".KS", ".KQ"))]
KR_SCAN_LIST = [k for k in STOCK_MAP.keys() if k.endswith((".KS", ".KQ"))]

ALL_INTERVALS = ["15m", "30m", "1h", "1d"]

# 영구 저장 파일 로드
if "saved_strategies" not in st.session_state:
    try:
        if os.path.exists("saved_strategies.json"):
            with open("saved_strategies.json", "r", encoding="utf-8") as f_json:
                st.session_state["saved_strategies"] = json.load(f_json)
        else:
            st.session_state["saved_strategies"] = {}
    except Exception:
        st.session_state["saved_strategies"] = {}

def save_strategies_permanently():
    with open("saved_strategies.json", "w", encoding="utf-8") as f_json:
        json.dump(st.session_state["saved_strategies"], f_json, ensure_ascii=False, indent=4)

# 런타임 제어용 버퍼 상태 초기화
if "ticker_buffer" not in st.session_state: st.session_state["ticker_buffer"] = "IONQ"
if "mode_buffer" not in st.session_state: st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
if "position_buffer" not in st.session_state: st.session_state["position_buffer"] = "SHORT (공매도)"
if "selected_entry_price" not in st.session_state: st.session_state["selected_entry_price"] = 0.0
if "target_tp_pct" not in st.session_state: st.session_state["target_tp_pct"] = 3.0
if "target_sl_pct" not in st.session_state: st.session_state["target_sl_pct"] = 1.0
if "input_key_trigger" not in st.session_state: st.session_state["input_key_trigger"] = 0

strat_keys = list(st.session_state["saved_strategies"].keys())
if "active_strategy_name" not in st.session_state or st.session_state.active_strategy_name not in st.session_state["saved_strategies"]:
    st.session_state.active_strategy_name = strat_keys[0] if strat_keys else "임시 미지정 전략"

if strat_keys and st.session_state.active_strategy_name in st.session_state["saved_strategies"]:
    sd = st.session_state["saved_strategies"][st.session_state.active_strategy_name]
    st.session_state["cur_short_ma"] = int(sd.get("short_ma", 20))
    st.session_state["cur_mid_ma"] = int(sd.get("mid_ma", 50))
    st.session_state["cur_long_ma"] = int(sd.get("long_ma", 200))
    st.session_state["cur_vol_break"] = float(sd.get("vol_breakout", 1.50))
    st.session_state["cur_conds"] = sd.get("active_conds", [True]*10)
    st.session_state["target_tp_pct"] = float(sd.get("target_tp_pct", 3.0))
    st.session_state["target_sl_pct"] = float(sd.get("target_sl_pct", 1.0))
else:
    if "cur_short_ma" not in st.session_state: st.session_state["cur_short_ma"] = 20
    if "cur_mid_ma" not in st.session_state: st.session_state["cur_mid_ma"] = 50
    if "cur_long_ma" not in st.session_state: st.session_state["cur_long_ma"] = 200
    if "cur_vol_break" not in st.session_state: st.session_state["cur_vol_break"] = 1.50
    if "cur_conds" not in st.session_state: st.session_state["cur_conds"] = [True]*10

# 런타임 전역 변수 계산
current_entry = float(st.session_state["selected_entry_price"])
target_tp_pct = float(st.session_state["target_tp_pct"])
target_sl_pct = float(st.session_state["target_sl_pct"])
raw_in_init = st.session_state["ticker_buffer"]
ticker_init = INV_STOCK_MAP.get(raw_in_init.lower(), raw_in_init.upper()) if raw_in_init else ""
curr_sign = "₩" if (".KS" in ticker_init or ".KQ" in ticker_init) else "$"

if current_entry > 0:
    if "LONG" in st.session_state["position_buffer"]:
        side_tp = current_entry * (1 + (target_tp_pct / 100))
        side_sl = current_entry * (1 - (target_sl_pct / 100))
    else:
        side_tp = current_entry * (1 - (target_tp_pct / 100))
        side_sl = current_entry * (1 + (target_sl_pct / 100))
else:
    side_tp, side_sl = 0.0, 0.0

# ==========================================
# 3. 마스터 제어 콘솔 (사이드바) - 시간대 선택 제거
# ==========================================
mode_options = ["🎯 단일 종목 검색", "🔍 조건 스캐너"]
try: mode_idx = mode_options.index(st.session_state["mode_buffer"])
except ValueError: mode_idx = 0
app_mode = st.sidebar.radio("작동 모드 전환:", options=mode_options, index=mode_idx, key=f"m_radio_trig_{st.session_state['input_key_trigger']}")
st.session_state["mode_buffer"] = app_mode
st.sidebar.markdown("---")

raw_in = st.sidebar.text_input("종목 이름 또는 티커 입력:", value=st.session_state["ticker_buffer"], key=f"t_input_trig_{st.session_state['input_key_trigger']}").strip()
st.session_state["ticker_buffer"] = raw_in
ticker = INV_STOCK_MAP.get(raw_in.lower(), raw_in.upper()) if raw_in else ""

# 스캐너 모드에서만 시간대 선택 표시
if app_mode == "🔍 조건 스캐너":
    time_options = ["15m", "30m", "1h", "1d"]
    scanner_interval = st.sidebar.selectbox(
        "스캐너 시간대 설정:",
        options=time_options,
        index=0,
        key=f"i_select_scanner_{st.session_state['input_key_trigger']}"
    )
else:
    scanner_interval = "15m"

st.sidebar.markdown("---")
st.sidebar.markdown("**📈 내 포지션 전략**")
pos_options = ["LONG (매수)", "SHORT (공매도)"]
try: pos_idx = pos_options.index(st.session_state["position_buffer"])
except ValueError: pos_idx = 1
position_side = st.sidebar.radio("포지션 방향 선택", options=pos_options, index=pos_idx, key=f"p_radio_trig_{st.session_state['input_key_trigger']}")
st.session_state["position_buffer"] = position_side

current_entry = st.sidebar.number_input("내 실제 진입 평단가", value=float(st.session_state["selected_entry_price"]), step=0.01, key=f"e_input_trig_{st.session_state['input_key_trigger']}")
st.session_state["selected_entry_price"] = current_entry

# 버그수정: sidebar.columns → 직접 sidebar에 배치
target_tp_pct = st.sidebar.number_input("목표 익절 비율 (%)", value=float(st.session_state["target_tp_pct"]), step=0.1, key=f"tp_input_trig_{st.session_state['input_key_trigger']}")
st.session_state["target_tp_pct"] = target_tp_pct

if current_entry > 0:
    if "LONG" in position_side:
        side_tp = current_entry * (1 + (target_tp_pct / 100))
    else:
        side_tp = current_entry * (1 - (target_tp_pct / 100))
else:
    side_tp = 0.0
st.sidebar.markdown(f"<div style='background-color:#e6f9ed; padding:6px; border-radius:6px; text-align:center; border:1px solid #b3e6c4; margin-bottom:8px;'><span style='font-size:10px; color:#00802b; font-weight:bold;'>익절 매도선</span>&nbsp;&nbsp;<span style='font-size:13px; color:#00802b; font-weight:800;'>{curr_sign}{side_tp:,.2f}</span></div>", unsafe_allow_html=True)

target_sl_pct = st.sidebar.number_input("제한 손절 비율 (%)", value=float(st.session_state["target_sl_pct"]), step=0.1, key=f"sl_input_trig_{st.session_state['input_key_trigger']}")
st.session_state["target_sl_pct"] = target_sl_pct

if current_entry > 0:
    if "LONG" in position_side:
        side_sl = current_entry * (1 - (target_sl_pct / 100))
    else:
        side_sl = current_entry * (1 + (target_sl_pct / 100))
else:
    side_sl = 0.0
st.sidebar.markdown(f"<div style='background-color:#ffe6e6; padding:6px; border-radius:6px; text-align:center; border:1px solid #ffb3b3; margin-bottom:8px;'><span style='font-size:10px; color:#cc0000; font-weight:bold;'>로스컷 제한</span>&nbsp;&nbsp;<span style='font-size:13px; color:#cc0000; font-weight:800;'>{curr_sign}{side_sl:,.2f}</span></div>", unsafe_allow_html=True)

# ==========================================
# 4. 조건검색 커스텀 컨트롤러 및 전략 보관함 (사이드바)
# ==========================================
dk = f"{st.session_state.active_strategy_name}_{st.session_state['input_key_trigger']}"

# ── 보관함 ──────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("**📂 나만의 조건 마스터 보관함**")
strat_keys = list(st.session_state["saved_strategies"].keys())
if strat_keys:
    for idx, key in enumerate(strat_keys):
        is_active = (key == st.session_state.active_strategy_name)
        btn_label = f"🎯 {key} (적용중)" if is_active else f"📁 {key}"
        sb_col_load, sb_col_del = st.sidebar.columns([4, 1])
        with sb_col_load:
            if st.button(btn_label, key=f"v_load_btn_{idx}", use_container_width=True):
                st.session_state["active_strategy_name"] = key
                target_sd = st.session_state["saved_strategies"][key]
                st.session_state["cur_short_ma"] = int(target_sd.get("short_ma", 20))
                st.session_state["cur_mid_ma"] = int(target_sd.get("mid_ma", 50))
                st.session_state["cur_long_ma"] = int(target_sd.get("long_ma", 200))
                st.session_state["cur_vol_break"] = float(target_sd.get("vol_breakout", 1.50))
                st.session_state["cur_conds"] = target_sd.get("active_conds", [True]*10)
                st.session_state["ticker_buffer"] = target_sd.get("ticker", "IONQ")
                st.session_state["position_buffer"] = target_sd.get("position_side", "SHORT (공매도)")
                st.session_state["selected_entry_price"] = float(target_sd.get("entry_price", 0.0))
                st.session_state["target_tp_pct"] = float(target_sd.get("target_tp_pct", 3.0))
                st.session_state["target_sl_pct"] = float(target_sd.get("target_sl_pct", 1.0))
                st.session_state["input_key_trigger"] += 1
                st.rerun()
        with sb_col_del:
            if st.button("❌", key=f"v_del_btn_{idx}", use_container_width=True):
                if key in st.session_state["saved_strategies"]:
                    del st.session_state["saved_strategies"][key]
                save_strategies_permanently()
                remaining_keys = list(st.session_state["saved_strategies"].keys())
                st.session_state.active_strategy_name = remaining_keys[0] if remaining_keys else "임시 미지정 전략"
                if remaining_keys:
                    rsd = st.session_state["saved_strategies"][st.session_state.active_strategy_name]
                    st.session_state["cur_short_ma"] = int(rsd.get("short_ma", 20))
                    st.session_state["cur_mid_ma"] = int(rsd.get("mid_ma", 50))
                    st.session_state["cur_long_ma"] = int(rsd.get("long_ma", 200))
                    st.session_state["cur_vol_break"] = float(rsd.get("vol_breakout", 1.50))
                    st.session_state["cur_conds"] = rsd.get("active_conds", [True]*10)
                    st.session_state["ticker_buffer"] = rsd.get("ticker", "IONQ")
                    st.session_state["position_buffer"] = rsd.get("position_side", "SHORT (공매도)")
                    st.session_state["selected_entry_price"] = float(rsd.get("entry_price", 0.0))
                    st.session_state["target_tp_pct"] = float(rsd.get("target_tp_pct", 3.0))
                    st.session_state["target_sl_pct"] = float(rsd.get("target_sl_pct", 1.0))
                st.session_state["input_key_trigger"] += 1
                st.rerun()
else:
    st.sidebar.caption("저장된 전략이 없습니다.")

# ── 조건검색 컨트롤러 변수 (항상 정의) ─────────────────────────────────
short_ma  = st.session_state["cur_short_ma"]
mid_ma    = st.session_state["cur_mid_ma"]
long_ma   = st.session_state["cur_long_ma"]
vol_break = st.session_state["cur_vol_break"]
active_conditions = list(st.session_state["cur_conds"])
max_possible_score = sum(active_conditions)

# 전설적 트레이더 기반 조건 레이블 (LONG/SHORT 공통 번호, 방향만 반전)
if "LONG" in position_side:
    COND_LABELS = [
        "1. [오닐/존스] 지수 필터: 시장 지수가 20일 이평선 위 (상승장)",
        "2. [미너비니/세이코타] 장기 정배열: 주가 > MA50 > MA150 > MA200",
        "3. [미너비니/리버모어] 52주 위치: 최저가+25% 이상 & 최고가 -25% 이내",
        "4. [미너비니/오닐] 변동성 축소: 최근 변동폭 < 이전 한달 변동폭 (힘의 응축)",
        "5. [다바스/덴니스] 박스권 돌파: 종가가 20일 최고가 상향 돌파",
        "6. [다바스/오닐] 거래량 폭발: 당일 거래량 ≥ 20일 평균 거래량 × 2.5배",
        "7. [덴니스/리버모어] 추세 강도: ADX ≥ 20 & +DI > -DI (상승 모멘텀)",
        "8. [덴니스/코브너] ATR 손절선: 현재가 - 2×ATR(14) 계산 완료",
        "9. [미너비니/소로스] 수익비: (목표가 - 현재가) ≥ 2 × (현재가 - 손절가)",
        "10. [세이코타/드락켄밀러] 추세 유지: 현재 종가가 20일 이평선 위 (보유 유지)",
    ]
else:
    COND_LABELS = [
        "1. [오닐/존스] 지수 필터: 시장 지수가 20일 이평선 아래 (하락장)",
        "2. [미너비니/세이코타] 장기 역배열: 주가 < MA50 < MA150 < MA200",
        "3. [미너비니/리버모어] 52주 위치: 최고가 -25% 이하 & 최저가 +25% 이내",
        "4. [미너비니/오닐] 변동성 축소 후 하락: 최근 변동폭 < 이전 변동폭 (압축)",
        "5. [다바스/덴니스] 박스권 하향 이탈: 종가가 20일 최저가 하향 돌파",
        "6. [다바스/오닐] 거래량 폭발: 당일 거래량 ≥ 20일 평균 거래량 × 2.5배",
        "7. [덴니스/리버모어] 추세 강도: ADX ≥ 20 & -DI > +DI (하락 모멘텀)",
        "8. [덴니스/코브너] ATR 손절선: 현재가 + 2×ATR(14) 계산 완료",
        "9. [미너비니/소로스] 수익비: (현재가 - 목표가) ≥ 2 × (손절가 - 현재가)",
        "10. [세이코타/드락켄밀러] 추세 유지: 현재 종가가 20일 이평선 아래 (보유 유지)",
    ]

# ── 조건검색 컨트롤러 (사이드바 expander) ───────────────────────────────
st.sidebar.markdown("---")
with st.sidebar.expander(f"⚙️ 조건검색 컨트롤러 — 🎯 {st.session_state.active_strategy_name}", expanded=False):
    st.markdown("**지표 기준 변수**")
    short_ma  = st.number_input("단기 EMA",          value=st.session_state["cur_short_ma"],  key=f"s_ma_{dk}")
    mid_ma    = st.number_input("중기 EMA",          value=st.session_state["cur_mid_ma"],    key=f"m_ma_{dk}")
    long_ma   = st.number_input("장기 EMA",          value=st.session_state["cur_long_ma"],   key=f"l_ma_{dk}")
    vol_break = st.number_input("거래량 돌파 기준배수", value=st.session_state["cur_vol_break"], step=0.1, key=f"v_bk_{dk}")

    # COND_LABELS 갱신 (expander 내부 — 포지션 방향 반영)
    if "LONG" in position_side:
        COND_LABELS = [
            "1. [오닐/존스] 지수 필터: 시장 지수 > 20일 이평 (상승장)",
            "2. [미너비니/세이코타] 장기 정배열: 주가 > MA50 > MA150 > MA200",
            "3. [미너비니/리버모어] 52주 위치: 최저가+25% & 최고가-25% 이내",
            "4. [미너비니/오닐] 변동성 축소: 최근 변동폭 < 이전 변동폭",
            "5. [다바스/덴니스] 20일 최고가 상향 돌파",
            "6. [다바스/오닐] 거래량 ≥ 20일 평균 × 2.5배",
            "7. [덴니스/리버모어] ADX ≥ 20 & +DI > -DI",
            "8. [덴니스/코브너] 2×ATR(14) 손절선 산출",
            "9. [미너비니/소로스] 수익비 ≥ 2:1",
            "10. [세이코타/드락켄밀러] 종가 > 20일 이평 (추세 유지)",
        ]
    else:
        COND_LABELS = [
            "1. [오닐/존스] 지수 필터: 시장 지수 < 20일 이평 (하락장)",
            "2. [미너비니/세이코타] 장기 역배열: 주가 < MA50 < MA150 < MA200",
            "3. [미너비니/리버모어] 52주 위치: 최고가-25% & 최저가+25% 이내",
            "4. [미너비니/오닐] 변동성 축소 후 하락: 최근 변동폭 < 이전 변동폭",
            "5. [다바스/덴니스] 20일 최저가 하향 돌파",
            "6. [다바스/오닐] 거래량 ≥ 20일 평균 × 2.5배",
            "7. [덴니스/리버모어] ADX ≥ 20 & -DI > +DI",
            "8. [덴니스/코브너] 2×ATR(14) 손절선 산출",
            "9. [미너비니/소로스] 수익비 ≥ 2:1",
            "10. [세이코타/드락켄밀러] 종가 < 20일 이평 (추세 유지)",
        ]

    st.markdown("---")
    st.markdown("**타점 조건식 토글**")
    active_conditions = []
    c_defaults = st.session_state["cur_conds"]
    for i in range(10):
        v = st.checkbox(COND_LABELS[i], value=c_defaults[i] if i < len(c_defaults) else True, key=f"c_box_{i}_{dk}")
        active_conditions.append(v)
    max_possible_score = sum(active_conditions)

# ── 전략 저장 (사이드바) ─────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("**💾 전략 저장 / 수정**")
default_input_name = "" if st.session_state.active_strategy_name == "임시 미지정 전략" else st.session_state.active_strategy_name
new_strat_name = st.sidebar.text_input("새 전략 이름:", value=default_input_name, placeholder="전략 명칭 입력", key=f"str_name_in_{dk}")
if st.sidebar.button("💾 저장 / 수정 반영", use_container_width=True, key=f"save_strat_btn_{dk}"):
    save_key = new_strat_name.strip() if new_strat_name.strip() else "나의 통합 전략"
    st.session_state["saved_strategies"][save_key] = {
        "ticker": st.session_state["ticker_buffer"],
        "position_side": position_side,
        "entry_price": current_entry,
        "target_tp_pct": target_tp_pct,
        "target_sl_pct": target_sl_pct,
        "short_ma": short_ma,
        "mid_ma": mid_ma,
        "long_ma": long_ma,
        "vol_breakout": vol_break,
        "active_conds": active_conditions
    }
    save_strategies_permanently()
    st.session_state.active_strategy_name = save_key
    st.session_state["cur_short_ma"] = short_ma
    st.session_state["cur_mid_ma"] = mid_ma
    st.session_state["cur_long_ma"] = long_ma
    st.session_state["cur_vol_break"] = vol_break
    st.session_state["cur_conds"] = active_conditions
    st.session_state["target_tp_pct"] = target_tp_pct
    st.session_state["target_sl_pct"] = target_sl_pct
    st.session_state["input_key_trigger"] += 1
    st.rerun()



# ==========================================
# 5. 수학/기술적 분석 엔진 (전설적 트레이더 10대 조건)
# ==========================================
def get_yahoo_custom_analysis(symbol, interval, forced_position=None):
    if not symbol: return None
    symbol = symbol.upper().strip()

    if interval in ["1m", "2m", "5m", "15m", "30m"]:
        period_str = "60d"
    elif interval == "1h":
        period_str = "730d"
    else:
        period_str = "2y"

    include_prepost = interval in ["1m", "15m", "30m", "1h"]
    _position = forced_position if forced_position else position_side

    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period=period_str, interval=interval, prepost=include_prepost)
        if df.empty or len(df) < 60: return None
        df = df.sort_index(ascending=True).ffill().bfill()

        close = df['Close']
        high  = df['High']
        low   = df['Low']
        vol   = df['Volume']
        last  = df.iloc[-1]

        # ── 이동평균선 ──────────────────────────────────────────────────
        ma20  = close.rolling(20).mean()
        ma50  = close.rolling(50).mean()
        ma150 = close.rolling(min(150, len(df))).mean()
        ma200 = close.rolling(min(200, len(df))).mean()

        # ── 52주(또는 가용 데이터) 고가/저가 ────────────────────────────
        lookback_52 = min(252, len(df))
        high_52 = high.rolling(lookback_52).max().iloc[-1]
        low_52  = low.rolling(lookback_52).min().iloc[-1]

        # ── 변동폭 축소 ──────────────────────────────────────────────────
        recent_range = (high.iloc[-20:].max() - low.iloc[-20:].min()) if len(df) >= 20 else 0
        prior_range  = (high.iloc[-50:-20].max() - low.iloc[-50:-20].min()) if len(df) >= 50 else recent_range + 1

        # ── 돌파: 최근 20일 고가/저가 ───────────────────────────────────
        breakout_high = high.iloc[-21:-1].max() if len(df) > 21 else high.iloc[:-1].max()
        breakout_low  = low.iloc[-21:-1].min()  if len(df) > 21 else low.iloc[:-1].min()

        # ── 거래량 ───────────────────────────────────────────────────────
        vol_avg20 = vol.rolling(20).mean().iloc[-1]

        # ── ADX / DI ────────────────────────────────────────────────────
        high_diff = high.diff()
        low_diff  = low.diff()
        plus_dm   = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
        minus_dm  = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low  - close.shift(1))
        ], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        plus_di  = 100 * (pd.Series(plus_dm,  index=df.index).rolling(14).mean() / (atr14 + 1e-9))
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).mean() / (atr14 + 1e-9))
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)) * 100
        adx = dx.rolling(14).mean()

        adx_val      = adx.iloc[-1]
        plus_di_val  = plus_di.iloc[-1]
        minus_di_val = minus_di.iloc[-1]
        atr_val      = atr14.iloc[-1]

        # ── 시장 지수 필터 (미국: SPY, 한국: ^KS11) ─────────────────────
        try:
            index_sym = "^KS11" if (".KS" in symbol or ".KQ" in symbol) else "SPY"
            idx_df = yf.Ticker(index_sym).history(period="60d", interval="1d")
            idx_df = idx_df.sort_index().ffill().bfill()
            idx_ma20 = idx_df['Close'].rolling(20).mean().iloc[-1]
            idx_last = idx_df['Close'].iloc[-1]
        except Exception:
            idx_last, idx_ma20 = 1.0, 0.9  # 조회 실패 시 통과 처리

        c_price = last['Close']
        ma20_val  = ma20.iloc[-1]
        ma50_val  = ma50.iloc[-1]
        ma150_val = ma150.iloc[-1]
        ma200_val = ma200.iloc[-1]

        # ── ATR 기반 손절가 / 목표가 (수익비용) ─────────────────────────
        if "LONG" in _position:
            sl_price = c_price - 2 * atr_val        # 손절
            tp_price = breakout_high + 3 * atr_val  # 목표 (다음 저항 추정)
        else:
            sl_price = c_price + 2 * atr_val
            tp_price = breakout_low  - 3 * atr_val

        rr_ok = abs(tp_price - c_price) >= 2 * abs(c_price - sl_price)

        # ── 조건식 계산 ─────────────────────────────────────────────────
        if "LONG" in _position:
            c_results = [
                # 1. 시장 지수 필터 (오닐/존스)
                bool(idx_last > idx_ma20),
                # 2. 장기 정배열 (미너비니/세이코타)
                bool(c_price > ma50_val > ma150_val > ma200_val),
                # 3. 52주 위치 필터 (미너비니/리버모어)
                bool(c_price >= low_52 * 1.25 and c_price >= high_52 * 0.75),
                # 4. 변동성 축소 (미너비니/오닐)
                bool(recent_range < prior_range),
                # 5. 박스권 상향 돌파 (다바스/덴니스)
                bool(c_price > breakout_high),
                # 6. 거래량 폭발 ≥ 2.5× (다바스/오닐)
                bool(last['Volume'] >= vol_avg20 * 2.5),
                # 7. ADX ≥ 20 & +DI > -DI (덴니스/리버모어)
                bool(adx_val >= 20 and plus_di_val > minus_di_val),
                # 8. ATR 손절선 산출 완료 (덴니스/코브너)
                bool(atr_val > 0),
                # 9. 수익비 ≥ 2:1 (미너비니/소로스)
                bool(rr_ok),
                # 10. 종가 > 20일 이평 (세이코타/드락켄밀러)
                bool(c_price > ma20_val),
            ]
        else:  # SHORT
            c_results = [
                # 1. 시장 지수 필터 — 하락장
                bool(idx_last < idx_ma20),
                # 2. 장기 역배열
                bool(c_price < ma50_val < ma150_val < ma200_val),
                # 3. 52주 위치 (하락 공매도용)
                bool(c_price <= high_52 * 0.75 and c_price <= low_52 * 1.25),
                # 4. 변동성 축소 후 하락
                bool(recent_range < prior_range),
                # 5. 박스권 하향 돌파
                bool(c_price < breakout_low),
                # 6. 거래량 폭발 ≥ 2.5×
                bool(last['Volume'] >= vol_avg20 * 2.5),
                # 7. ADX ≥ 20 & -DI > +DI
                bool(adx_val >= 20 and minus_di_val > plus_di_val),
                # 8. ATR 손절선 산출 완료
                bool(atr_val > 0),
                # 9. 수익비 ≥ 2:1
                bool(rr_ok),
                # 10. 종가 < 20일 이평
                bool(c_price < ma20_val),
            ]

        score = sum([1 for i, act in enumerate(active_conditions) if act and c_results[i]])
        recom_side = "LONG" if "LONG" in _position else "SHORT"
        if max_possible_score > 0:
            ratio = score / max_possible_score
            if ratio >= 0.8:   status = f"🟢 사격 개시 ({recom_side} 추천)"
            elif ratio <= 0.4: status = "🔴 위험구역 (RISK CUT)"
            else:              status = "🟡 관망 (NEUTRAL)"
        else:
            status = "🟡 선택 조건 없음"

        currency_symbol = "₩" if (".KS" in symbol or ".KQ" in symbol) else "$"
        return {
            "df": df, "score": score, "status_text": status,
            "current_price": c_price, "currency": currency_symbol,
            "c_results": c_results,
            "atr_val": atr_val, "sl_price": sl_price, "tp_price": tp_price,
        }
    except Exception:
        return None


# ==========================================
# 6. 모드 1: 단일 종목 집중 감시 - 멀티타임프레임 점수 그리드
# ==========================================
def render_score_badge(score, max_score, interval_label, position_label):
    """시간대 × 포지션 점수 뱃지 렌더링"""
    if max_score == 0:
        bg = "#f0f0f0"; fg = "#888"; status_short = "조건없음"
    else:
        ratio = score / max_score
        if ratio >= 0.8:
            bg = "#d4edda"; fg = "#155724"; status_short = "🟢 사격개시"
        elif ratio <= 0.4:
            bg = "#f8d7da"; fg = "#721c24"; status_short = "🔴 위험구역"
        else:
            bg = "#fff3cd"; fg = "#856404"; status_short = "🟡 관망"

    bar_pct = int((score / max_score * 100)) if max_score > 0 else 0
    pos_color = "#1565c0" if "LONG" in position_label else "#b71c1c"
    pos_label_short = "📈 LONG" if "LONG" in position_label else "📉 SHORT"

    return f"""
    <div style="
        border:1px solid #e2e8f0; border-radius:10px; padding:14px 10px;
        background:{bg}; text-align:center; height:100%;
    ">
        <div style="font-size:11px; color:#555; font-weight:600; margin-bottom:4px;">{interval_label}</div>
        <div style="font-size:12px; color:{pos_color}; font-weight:700; margin-bottom:6px;">{pos_label_short}</div>
        <div style="font-size:22px; font-weight:900; color:{fg};">{score}<span style="font-size:13px; font-weight:500; color:#666;">/{max_score}</span></div>
        <div style="font-size:11px; color:{fg}; font-weight:700; margin:4px 0;">{status_short}</div>
        <div style="background:#ddd; border-radius:4px; height:6px; margin-top:6px;">
            <div style="background:{fg}; width:{bar_pct}%; height:6px; border-radius:4px;"></div>
        </div>
        <div style="font-size:10px; color:#888; margin-top:3px;">{bar_pct}%</div>
    </div>
    """


if app_mode == "🎯 단일 종목 검색":
    if ticker:
        INTERVALS = ["15m", "30m", "1h", "1d"]
        combos = [(iv, pos) for iv in INTERVALS for pos in ["LONG (매수)", "SHORT (공매도)"]]

        with st.spinner("⏳ 멀티타임프레임 분석 중..."):
            mtf_results = {}
            def fetch_combo(args):
                iv, pos = args
                return (iv, pos), get_yahoo_custom_analysis(ticker, iv, forced_position=pos)
            with ThreadPoolExecutor(max_workers=8) as executor:
                for key_combo, result in executor.map(fetch_combo, combos):
                    mtf_results[key_combo] = result

        # 1d LONG 결과를 현재가 소스로 사용
        res_price = mtf_results.get(("1d", "LONG (매수)")) or mtf_results.get(("1d", "SHORT (공매도)"))

        if res_price is None:
            st.error("❌ 현재 데이터를 파싱할 수 없습니다. 티커 부호 또는 거래소 개장 유무를 확인하세요.")
        else:
            c_price = res_price["current_price"]
            curr    = res_price["currency"]

            # ── 1. 시간대별 LONG / SHORT 점수 테이블 ──────────────────────
            st.markdown(f"#### 📊 {ticker} — 시간대별 LONG / SHORT 점수")

            def make_cell(score, max_score, side):
                """점수 셀 HTML — 가로 한 줄 텍스트"""
                if max_score == 0:
                    return "<div style='color:#aaa; font-size:12px; text-align:center; padding:6px;'>조건없음</div>"
                ratio = score / max_score
                if ratio >= 0.8:
                    fg, bg, label = "#155724", "#d4edda", "🟢 사격개시"
                elif ratio <= 0.4:
                    fg, bg, label = "#721c24", "#f8d7da", "🔴 위험구역"
                else:
                    fg, bg, label = "#856404", "#fff3cd", "🟡 관망"
                side_icon = "📈" if "LONG" in side else "📉"
                side_txt  = "LONG" if "LONG" in side else "SHORT"
                side_col  = "#1565c0" if "LONG" in side else "#b71c1c"
                return (
                    f"<div style='background:{bg}; border:1px solid {fg}44; border-radius:8px; "
                    f"padding:6px 12px; display:flex; align-items:center; gap:8px;'>"
                    f"<span style='font-size:11px; font-weight:700; color:{side_col};'>{side_icon} {side_txt}</span>"
                    f"<span style='font-size:13px; font-weight:800; color:{fg};'>{score}/{max_score}</span>"
                    f"<span style='font-size:12px; font-weight:600; color:{fg};'>{label}</span>"
                    f"</div>"
                )

            # 헤더
            h0, h1, h2 = st.columns([1, 5, 5])
            h0.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            h1.markdown(
                "<div style='text-align:center; font-size:12px; font-weight:700; color:#1565c0; "
                "background:#e8f4fd; border-radius:6px; padding:5px;'>📈 LONG (매수)</div>",
                unsafe_allow_html=True)
            h2.markdown(
                "<div style='text-align:center; font-size:12px; font-weight:700; color:#b71c1c; "
                "background:#fdecea; border-radius:6px; padding:5px;'>📉 SHORT (공매도)</div>",
                unsafe_allow_html=True)

            for iv in INTERVALS:
                c0, c1, c2 = st.columns([1, 5, 5])
                r_l = mtf_results.get((iv, "LONG (매수)"))
                r_s = mtf_results.get((iv, "SHORT (공매도)"))

                c0.markdown(
                    f"<div style='display:flex; align-items:center; justify-content:center; "
                    f"min-height:40px; height:100%;'>"
                    f"<span style='font-size:13px; font-weight:800; color:#2d3748; "
                    f"background:#f0f4f8; padding:5px 10px; border-radius:7px; "
                    f"border:1px solid #cbd5e0;'>{iv}</span></div>",
                    unsafe_allow_html=True
                )
                c1.markdown(
                    make_cell(r_l["score"], max_possible_score, "LONG") if r_l
                    else "<div style='color:#aaa; font-size:12px; text-align:center;'>데이터 없음</div>",
                    unsafe_allow_html=True
                )
                c2.markdown(
                    make_cell(r_s["score"], max_possible_score, "SHORT") if r_s
                    else "<div style='color:#aaa; font-size:12px; text-align:center;'>데이터 없음</div>",
                    unsafe_allow_html=True
                )

            st.markdown("---")

            # ── 2. 실시간 상태 모니터링판 (점수 테이블 아래, 작은 크기) ───────
            if current_entry > 0:
                if "LONG" in position_side:
                    realtime_profit = ((c_price - current_entry) / current_entry) * 100
                    calculated_tp   = current_entry * (1 + target_tp_pct / 100)
                    calculated_sl   = current_entry * (1 - target_sl_pct / 100)
                else:
                    realtime_profit = ((current_entry - c_price) / current_entry) * 100
                    calculated_tp   = current_entry * (1 - target_tp_pct / 100)
                    calculated_sl   = current_entry * (1 + target_sl_pct / 100)
            else:
                realtime_profit = calculated_tp = calculated_sl = 0.0

            profit_color = "#155724" if realtime_profit >= 0 else "#721c24"
            profit_bg    = "#d4edda" if realtime_profit >= 0 else "#f8d7da"

            st.markdown(
                f"<p style='font-size:11px; font-weight:700; color:#718096; "
                f"letter-spacing:0.5px; margin-bottom:4px;'>💳 {ticker} 실시간 모니터링</p>",
                unsafe_allow_html=True
            )
            mon = (
                f"<div style='display:flex; gap:8px; flex-wrap:wrap; margin-bottom:4px;'>"

                f"<div style='background:#f7fafc; border:1px solid #e2e8f0; border-radius:8px; "
                f"padding:6px 14px; min-width:110px;'>"
                f"<div style='font-size:10px; color:#718096;'>🔥 현재가</div>"
                f"<div style='font-size:14px; font-weight:800; color:#1a202c;'>{curr}{c_price:,.2f}</div>"
                f"</div>"

                f"<div style='background:{profit_bg}; border:1px solid {profit_color}44; border-radius:8px; "
                f"padding:6px 14px; min-width:110px;'>"
                f"<div style='font-size:10px; color:#718096;'>📉 수익률</div>"
                f"<div style='font-size:14px; font-weight:800; color:{profit_color};'>"
                f"{'%+.2f%%' % realtime_profit if current_entry > 0 else '평단가 미입력'}</div>"
                f"</div>"

                f"<div style='background:#e6f9ed; border:1px solid #b3e6c444; border-radius:8px; "
                f"padding:6px 14px; min-width:110px;'>"
                f"<div style='font-size:10px; color:#718096;'>🎯 익절 ({target_tp_pct}%)</div>"
                f"<div style='font-size:14px; font-weight:800; color:#00802b;'>"
                f"{curr+('%.2f' % calculated_tp) if current_entry > 0 else '-'}</div>"
                f"</div>"

                f"<div style='background:#ffe6e6; border:1px solid #ffb3b344; border-radius:8px; "
                f"padding:6px 14px; min-width:110px;'>"
                f"<div style='font-size:10px; color:#718096;'>🚨 손절 ({target_sl_pct}%)</div>"
                f"<div style='font-size:14px; font-weight:800; color:#cc0000;'>"
                f"{curr+('%.2f' % calculated_sl) if current_entry > 0 else '-'}</div>"
                f"</div>"

                f"</div>"
            )
            st.markdown(mon, unsafe_allow_html=True)

            st.markdown("---")

            # ── 3. 세부 체크리스트 (선택 포지션 1d 기준) ───────────────────
            ref_res = mtf_results.get(("1d", position_side)) or res_price
            if ref_res:
                c_score  = ref_res["score"]
                c_status = ref_res["status_text"]
                sc1, sc2 = st.columns([1, 3])
                with sc1:
                    st.metric(label=f"스코어 (1d/{position_side[:5]})", value=f"{c_score} / {max_possible_score}")
                with sc2:
                    st.markdown(f"<p style='font-size:15px; font-weight:700; margin:6px 0;'>📟 {c_status}</p>", unsafe_allow_html=True)
                    if max_possible_score > 0:
                        st.progress(int(c_score / max_possible_score * 100))

                st.markdown("##### ⚡ 세부 지표 체크리스트 (1D 기준)")
                check_cols = st.columns(2)
                for idx, (label, active, passed) in enumerate(zip(COND_LABELS, active_conditions, ref_res["c_results"])):
                    col = check_cols[0] if idx < 5 else check_cols[1]
                    if active:
                        if passed: col.success(f"⭕ [충족] {label}")
                        else:       col.error(f"❌ [미달] {label}")
                    else:
                        col.warning(f"⚪ [제외] {label}")

                # ── ATR 손절/목표가 요약 박스 ────────────────────────────
                atr_v  = ref_res.get("atr_val", 0)
                sl_v   = ref_res.get("sl_price", 0)
                tp_v   = ref_res.get("tp_price", 0)
                if atr_v and atr_v > 0:
                    st.markdown(
                        f"<div style='margin-top:10px; background:#f8f9fa; border:1px solid #dee2e6; "
                        f"border-radius:8px; padding:10px 16px; display:flex; gap:20px; flex-wrap:wrap;'>"
                        f"<span style='font-size:11px; color:#495057;'>📐 <b>ATR(14)</b>: {curr}{atr_v:,.2f}</span>"
                        f"<span style='font-size:11px; color:#cc0000;'>🚨 <b>2×ATR 손절선</b>: {curr}{sl_v:,.2f}</span>"
                        f"<span style='font-size:11px; color:#00802b;'>🎯 <b>목표가 추정</b>: {curr}{tp_v:,.2f}</span>"
                        f"<span style='font-size:11px; color:#856404;'>📊 <b>수익비</b>: "
                        f"{'%.1f' % (abs(tp_v - c_price) / (abs(c_price - sl_v) + 1e-9))}:1</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
    else:
        st.warning("⚠️ 왼쪽 제어 콘솔에서 종목 티커(예: IONQ, TSLA)를 입력하거나 보관함에서 불러올 전략을 클릭해 주세요.")

# ==========================================
# 7. 모드 2: 주요 종목 마스터 스캐너
# ==========================================
else:
    st.markdown(f"### 🔍 한/미 주요 종목 마스터 스캐너 ({scanner_interval} 기준)")
    m_col1, m_col2 = st.columns(2)
    with m_col1: scan_us = st.checkbox("🇺🇸 미국 우량주 포함", value=True)
    with m_col2: scan_kr = st.checkbox("🇰🇷 한국 우량주 포함", value=False)

    scan_list = []
    if scan_us: scan_list.extend(US_SCAN_LIST)
    if scan_kr: scan_list.extend(KR_SCAN_LIST)

    if st.button("🚀 실시간 프리마켓 전수 조사 스캔 개시"):
        # 버그수정: 스캔 시작 시 이전 캐시 초기화
        st.session_state.pop("cached_scan", None)

        scan_results = []
        prog_bar = st.progress(0)

        def thread_scanner(sym): return get_yahoo_custom_analysis(sym, scanner_interval)
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(thread_scanner, s) for s in scan_list]
            for idx, fut in enumerate(futures):
                m = fut.result()
                if m:
                    scan_results.append({
                        "티커": scan_list[idx],
                        "종목명": STOCK_MAP.get(scan_list[idx], scan_list[idx]),
                        "현재가_raw": m['current_price'],
                        "현재가": f"{m['currency']}{m['current_price']:,.2f}",
                        "스코어_raw": m['score'],
                        "스코어": f"{m['score']}/{max_possible_score}",
                        "통합 시그널": m["status_text"]
                    })
                prog_bar.progress((idx + 1) / len(scan_list))

        if scan_results:
            st.session_state["cached_scan"] = scan_results

    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        df_display = pd.DataFrame(st.session_state["cached_scan"])
        df_view = df_display.drop(columns=["현재가_raw", "스코어_raw"], errors="ignore")

        def color_signal_cell(val):
            if "사격 개시" in str(val): return "background-color: #d4edda; color: #155724; font-weight: bold;"
            if "관망" in str(val): return "background-color: #fff3cd; color: #856404; font-weight: bold;"
            if "위험구역" in str(val): return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
            return "color: #333333;"

        styled_df = df_view.style.map(color_signal_cell, subset=['통합 시그널'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### ⚡ 실시간 스캔 매칭률 Top 10 고득점 정렬 리스트")
        top_10_items = sorted(st.session_state["cached_scan"], key=lambda x: x.get("스코어_raw", 0), reverse=True)[:10]
        ITEMS_PER_ROW = 5

        if top_10_items:
            for i in range(0, len(top_10_items), ITEMS_PER_ROW):
                row_items = top_10_items[i: i + ITEMS_PER_ROW]
                grid_cols = st.columns(ITEMS_PER_ROW)
                for idx, item in enumerate(row_items):
                    with grid_cols[idx]:
                        item_ticker = item.get("티커")
                        item_name = item.get("종목명")
                        item_score = item.get("스코어")
                        view_price = item.get("현재가")
                        signal = item.get("통합 시그널", "N/A")

                        if "사격 개시" in str(signal):
                            badge_color = "#e6f9ed"; text_color = "#00802b"
                        elif "위험구역" in str(signal):
                            badge_color = "#ffe6e6"; text_color = "#cc0000"
                        else:
                            badge_color = "#fff2cc"; text_color = "#cc9900"

                        st.markdown(f"""
                        <div style="border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:12px;
                            text-align:center; background-color:#ffffff; box-shadow:0px 2px 4px rgba(0,0,0,0.04);">
                            <span style="font-weight:700; color:#1a202c; font-size:14px; display:block;
                                text-overflow:ellipsis; white-space:nowrap; overflow:hidden;">{item_name}</span>
                            <code style="color:#4a5568; font-size:11px; background-color:#f7fafc;
                                padding:2px 6px; border-radius:4px;">{item_ticker}</code>
                            <div style="font-size:18px; font-weight:800; color:#2d3748; margin:8px 0;">{view_price}</div>
                            <div style="font-size:12px; color:#718096; margin-bottom:8px;">
                                📊 스코어: <b style="color:#2b6cb0;">{item_score} 점</b></div>
                            <div style="background-color:{badge_color}; color:{text_color}; font-size:11px;
                                padding:4px; border-radius:5px; font-weight:bold;
                                overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{signal}</div>
                        </div>""", unsafe_allow_html=True)

                        if st.button(f"📈 {item_ticker} 분석", key=f"grid_redirect_{item_ticker}_{i}_{idx}", use_container_width=True):
                            st.session_state["ticker_buffer"] = item_ticker
                            st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                            st.session_state["input_key_trigger"] += 1
                            st.rerun()
