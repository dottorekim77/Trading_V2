import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ==========================================
# 1. 페이지 기본 설정 및 상태 초기화 (기존 원본 100% 동일)
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
    "035420.KS": "NAVER", "035720.KS": "카카오", "005380.KS": "현대차", "000270.KS": "기아",
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
    st.session_state["cur_conds"] = sd.get("active_conds", [True]*10)
    st.session_state["target_tp_pct"] = float(sd.get("target_tp_pct", 3.0))
    st.session_state["target_sl_pct"] = float(sd.get("target_sl_pct", 1.0))
else:
    if "cur_conds" not in st.session_state: st.session_state["cur_conds"] = [True]*10

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
# 2. 마스터 제어 콘솔 (사이드바) - 기존 UI 유지
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

if app_mode == "🔍 조건 스캐너":
    time_options = ["15m", "30m", "1h", "1d"]
    scanner_interval = st.sidebar.selectbox("스캐너 시간대 설정:", options=time_options, index=0, key=f"i_select_scanner_{st.session_state['input_key_trigger']}")
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

target_tp_pct = st.sidebar.number_input("목표 익절 비율 (%)", value=float(st.session_state["target_tp_pct"]), step=0.1, key=f"tp_input_trig_{st.session_state['input_key_trigger']}")
st.session_state["target_tp_pct"] = target_tp_pct

if current_entry > 0:
    if "LONG" in position_side: side_tp = current_entry * (1 + (target_tp_pct / 100))
    else: side_tp = current_entry * (1 - (target_tp_pct / 100))
else: side_tp = 0.0
st.sidebar.markdown(f"<div style='background-color:#e6f9ed; padding:6px; border-radius:6px; text-align:center; border:1px solid #b3e6c4; margin-bottom:8px;'><span style='font-size:10px; color:#00802b; font-weight:bold;'>익절 매도선</span>&nbsp;&nbsp;<span style='font-size:13px; color:#00802b; font-weight:800;'>{curr_sign}{side_tp:,.2f}</span></div>", unsafe_allow_html=True)

target_sl_pct = st.sidebar.number_input("제한 손절 비율 (%)", value=float(st.session_state["target_sl_pct"]), step=0.1, key=f"sl_input_trig_{st.session_state['input_key_trigger']}")
st.session_state["target_sl_pct"] = target_sl_pct

if current_entry > 0:
    if "LONG" in position_side: side_sl = current_entry * (1 - (target_sl_pct / 100))
    else: side_sl = current_entry * (1 + (target_sl_pct / 100))
else: side_sl = 0.0
st.sidebar.markdown(f"<div style='background-color:#ffe6e6; padding:6px; border-radius:6px; text-align:center; border:1px solid #ffb3b3; margin-bottom:8px;'><span style='font-size:10px; color:#cc0000; font-weight:bold;'>로스컷 제한</span>&nbsp;&nbsp;<span style='font-size:13px; color:#cc0000; font-weight:800;'>{curr_sign}{side_sl:,.2f}</span></div>", unsafe_allow_html=True)

# ── 새로운 10대 대가들의 조건식 라벨 고정 ──
COND_LABELS = [
    "1. 시장 및 지수 필터링 (Index > 20EMA)",
    "2. 장기 정배열 정렬 (Price > 50 > 150 > 200 EMA)",
    "3. 주가 위치 필터 (52주 최저 대비 +25%, 최고 대비 -25% 이내)",
    "4. 단기 매물 소화 및 변동성 축소 (최근 변동성 < 전월 변동성)",
    "5. 저항선/박스권 돌파 (오늘 종가 > 최근 20일 최고가)",
    "6. 메이저 수급 및 거래량 폭발 (당일 거래량 > 20일 평균의 250%)",
    "7. 추세 강도 검증 (ADX >= 20 및 +DI > -DI 골든크로스)",
    "8. 변동성 기반 위험 측정 (현재가 대비 2*ATR 하락 계산)",
    "9. 기대 수익비 계산 (상단 저항폭 >= 하단 손절폭의 2배)",
    "10. 추적 이탈 방지 (종가 > 20일 이동평균선 지지)"
]

# ==========================================
# 3. 조건검색 커스텀 컨트롤러 및 전략 보관함 (사이드바)
# ==========================================
dk = f"{st.session_state.active_strategy_name}_{st.session_state['input_key_trigger']}"

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
                if key in st.session_state["saved_strategies"]: del rsd
                save_strategies_permanently()
                st.session_state["input_key_trigger"] += 1
                st.rerun()
else:
    st.sidebar.caption("저장된 전략이 없습니다.")

st.sidebar.markdown("---")
with st.sidebar.expander(f"⚙️ 조건검색 컨트롤러 — 🎯 {st.session_state.active_strategy_name}", expanded=False):
    st.markdown("**타점 조건식 토글**")
    active_conditions = []
    c_defaults = st.session_state["cur_conds"]
    for i in range(10):
        v = st.checkbox(COND_LABELS[i], value=c_defaults[i] if i < len(c_defaults) else True, key=f"c_box_{i}_{dk}")
        active_conditions.append(v)
    max_possible_score = sum(active_conditions)

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
        "active_conds": active_conditions
    }
    save_strategies_permanently()
    st.session_state.active_strategy_name = save_key
    st.session_state["cur_conds"] = active_conditions
    st.session_state["input_key_trigger"] += 1
    st.rerun()

# ==========================================
# 4. 수학/기술적 분석 엔진 (요청하신 새로운 10대 조건 구현)
# ==========================================
def get_yahoo_custom_analysis(symbol, interval, forced_position=None):
    if not symbol: return None
    symbol = symbol.upper().strip()

    if interval in ["1m", "2m", "5m", "15m", "30m"]: period_str = "60d"
    elif interval in ["1h"]: period_str = "730d"
    else: period_str = "3y"

    include_prepost = interval in ["1m", "15m", "30m", "1h"]
    _position = forced_position if forced_position else position_side

    try:
        # [1번 조건] 시장 지수 필터링 연산
        if ".KS" in symbol: index_symbol = "^KS11"
        elif ".KQ" in symbol: index_symbol = "^KQ11"
        else: index_symbol = "^GSPC"
        
        idx_df = yf.Ticker(index_symbol).history(period="100d", interval=interval)
        if not idx_df.empty:
            idx_df['EMA20'] = idx_df['Close'].ewm(span=20, adjust=False).mean()
            market_filter = bool(idx_df['Close'].iloc[-1] > idx_df['EMA20'].iloc[-1])
        else:
            market_filter = True

        df = yf.Ticker(symbol).history(period=period_str, interval=interval, prepost=include_prepost)
        if df.empty or len(df) < 252: return None
        df = df.sort_index(ascending=True).ffill().bfill()

        # 대가들의 핵심 기술적 지표 계산
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA150'] = df['Close'].ewm(span=150, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['Min_52wk'] = df['Low'].rolling(window=252, min_periods=50).min()
        df['Max_52wk'] = df['High'].rolling(window=252, min_periods=50).max()
        df['Max_20v'] = df['High'].shift(1).rolling(window=20).max()
        df['Min_20v'] = df['Low'].shift(1).rolling(window=20).min()
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

        # ADX / DMI 연산
        delta_high = df['High'].diff()
        delta_low = df['Low'].diff()
        plus_dm = np.where((delta_high > delta_low) & (delta_high > 0), delta_high, 0.0)
        minus_dm = np.where((delta_low > delta_high) & (delta_low > 0), delta_low, 0.0)
        tr = pd.concat([df['High'] - df['Low'], abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        df['ATR'] = atr
        df['Plus_DI'] = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=14).mean() / (atr + 1e-9))
        df['Minus_DI'] = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=14).mean() / (atr + 1e-9))
        dx = 100 * abs(df['Plus_DI'] - df['Minus_DI']) / (df['Plus_DI'] + df['Minus_DI'] + 1e-9)
        df['ADX'] = dx.rolling(window=14).mean()

        last = df.iloc[-1]
        
        # [4번 조건] 변동성 축소 패턴 (VCP) 계산
        recent_range = df['High'].tail(15).max() - df['Low'].tail(15).min()
        prior_range = df['High'].iloc[-45:-15].max() - df['Low'].iloc[-45:-15].min()
        vcp_pattern = bool(recent_range < prior_range)

        # [8, 9번 조건] 기대수익비 산출용 변수
        resistance_price = last['Max_52wk']
        stop_loss_price = last['Close'] - (2 * last['ATR'])
        reward_side = resistance_price - last['Close']
        risk_side = last['Close'] - stop_loss_price
        profit_ratio_cond = bool(reward_side >= (risk_side * 2))

        # ── 10가지 신규 조건식 판정 로직 ──
        if "LONG" in _position:
            c_results = [
                market_filter,                                                                  # 1
                bool(last['Close'] > last['EMA50'] > last['EMA150'] > last['EMA200']),         # 2
                bool(last['Close'] >= last['Min_52wk'] * 1.25 and last['Close'] >= last['Max_52wk'] * 0.75), # 3
                vcp_pattern,                                                                    # 4
                bool(last['Close'] >= last['Max_20v']),                                         # 5
                bool(last['Volume'] >= last['Vol_MA20'] * 2.5),                                 # 6
                bool(last['ADX'] >= 20 and last['Plus_DI'] > last['Minus_DI']),                 # 7
                bool(risk_side > 0),                                                            # 8
                profit_ratio_cond,                                                              # 9
                bool(last['Close'] > last['EMA20'])                                             # 10
            ]
        else:
            c_results = [
                not market_filter,                                                              # 1
                bool(last['Close'] < last['EMA50'] < last['EMA150'] < last['EMA200']),         # 2
                bool(last['Close'] <= last['Max_52wk'] * 0.75),                                 # 3
                vcp_pattern,                                                                    # 4
                bool(last['Close'] <= last['Min_20v']),                                         # 5
                bool(last['Volume'] >= last['Vol_MA20'] * 2.5),                                 # 6
                bool(last['ADX'] >= 20 and last['Minus_DI'] > last['Plus_DI']),                 # 7
                bool(risk_side > 0),                                                            # 8
                bool((last['Close'] - last['Min_52wk']) >= ((last['Close'] + 2*last['ATR']) - last['Close']) * 2), # 9
                bool(last['Close'] < last['EMA20'])                                             # 10
            ]

        score = sum([1 for i, active in enumerate(active_conditions) if active and c_results[i]])
        recom_side = "LONG" if "LONG" in _position else "SHORT"
        if max_possible_score > 0:
            ratio = score / max_possible_score
            if ratio >= 0.8: status = f"🟢 사격 개시 ({recom_side} 추천)"
            elif ratio <= 0.4: status = "🔴 위험구역 (RISK CUT)"
            else: status = "🟡 관망 (NEUTRAL)"
        else:
            status = "🟡 선택 조건 없음"

        currency_symbol = "₩" if (".KS" in symbol or ".KQ" in symbol) else "$"
        return {
            "df": df, "score": score, "status_text": status,
            "current_price": last['Close'], "currency": currency_symbol,
            "c_results": c_results
        }
    except Exception:
        return None

# ==========================================
# 5. 모드 1: 단일 종목 집중 감시 - 기존 원본의 4개 시간대 분리 테이블 구조 완벽 유지
# ==========================================
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

        res_price = mtf_results.get(("1d", "LONG (매수)")) or mtf_results.get(("1d", "SHORT (공매도)"))

        if res_price is None:
            st.error("❌ 현재 데이터를 파싱할 수 없습니다. 티커 부호 또는 거래소 개장 유무를 확인하세요.")
        else:
            c_price = res_price["current_price"]
            curr    = res_price["currency"]

            # ── 1. 시간대별 LONG / SHORT 격자 테이블 (원본 구조 100% 동기화) ──
            st.markdown(f"#### 📊 {ticker} — 시간대별 LONG / SHORT 점수")

            def make_cell(score, max_score, side):
                if max_score == 0:
                    return "<div style='color:#aaa; font-size:12px; text-align:center; padding:6px;'>조건없음</div>"
                ratio = score / max_score
                if ratio >= 0.8: fg, bg, label = "#155724", "#d4edda", "🟢 사격개시"
                elif ratio <= 0.4: fg, bg, label = "#721c24", "#f8d7da", "🔴 위험구역"
                else: fg, bg, label = "#856404", "#fff3cd", "🟡 관망"
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

            # 원본 헤더 레이아웃
            h0, h1, h2 = st.columns([1, 5, 5])
            h0.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            h1.markdown("<div style='text-align:center; font-size:12px; font-weight:700; color:#1565c0; background:#e8f4fd; border-radius:6px; padding:5px;'>📈 LONG (매수)</div>", unsafe_allow_html=True)
            h2.markdown("<div style='text-align:center; font-size:12px; font-weight:700; color:#b71c1c; background:#fdecea; border-radius:6px; padding:5px;'>📉 SHORT (공매도)</div>", unsafe_allow_html=True)

            # 원본 4개 행 가로 전개 루프
            for iv in INTERVALS:
                c0, c1, c2 = st.columns([1, 5, 5])
                r_l = mtf_results.get((iv, "LONG (매수)"))
                r_s = mtf_results.get((iv, "SHORT (공매도)"))

                c0.markdown(f"<div style='display:flex; align-items:center; justify-content:center; min-height:40px; height:100%;'><span style='font-size:13px; font-weight:800; color:#2d3748; background:#f0f4f8; padding:5px 10px; border-radius:7px; border:1px solid #cbd5e0;'>{iv}</span></div>", unsafe_allow_html=True)
                c1.markdown(make_cell(r_l["score"], max_possible_score, "LONG") if r_l else "<div style='color:#aaa; font-size:12px; text-align:center;'>데이터 없음</div>", unsafe_allow_html=True)
                c2.markdown(make_cell(r_s["score"], max_possible_score, "SHORT") if r_s else "<div style='color:#aaa; font-size:12px; text-align:center;'>데이터 없음</div>", unsafe_allow_html=True)

            st.markdown("---")

            # ── 2. 실시간 상태 모니터링판 ──
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

            st.markdown(f"<p style='font-size:11px; font-weight:700; color:#718096; letter-spacing:0.5px; margin-bottom:4px;'>💳 {ticker} 실시간 모니터링</p>", unsafe_allow_html=True)
            mon = (
                f"<div style='display:flex; gap:8px; flex-wrap:wrap; margin-bottom:4px;'>"
                f"<div style='background:#f7fafc; border:1px solid #e2e8f0; border-radius:8px; padding:6px 14px; min-width:110px;'><div style='font-size:10px; color:#718096;'>🔥 현재가</div><div style='font-size:14px; font-weight:800; color:#1a202c;'>{curr}{c_price:,.2f}</div></div>"
                f"<div style='background:{profit_bg}; border:1px solid {profit_color}44; border-radius:8px; padding:6px 14px; min-width:110px;'><div style='font-size:10px; color:#718096;'>📉 수익률</div><div style='font-size:14px; font-weight:800; color:{profit_color};'>{'%+.2f%%' % realtime_profit if current_entry > 0 else '평단가 미입력'}</div></div>"
                f"<div style='background:#e6f9ed; border:1px solid #b3e6c444; border-radius:8px; padding:6px 14px; min-width:110px;'><div style='font-size:10px; color:#718096;'>🎯 익절 ({target_tp_pct}%)</div><div style='font-size:14px; font-weight:800; color:#00802b;'>{curr+('%.2f' % calculated_tp) if current_entry > 0 else '-'}</div></div>"
                f"<div style='background:#ffe6e6; border:1px solid #ffb3b344; border-radius:8px; padding:6px 14px; min-width:110px;'><div style='font-size:10px; color:#718096;'>🚨 손절 ({target_sl_pct}%)</div><div style='font-size:14px; font-weight:800; color:#cc0000;'>{curr+('%.2f' % calculated_sl) if current_entry > 0 else '-'}</div></div>"
                f"</div>"
            )
            st.markdown(mon, unsafe_allow_html=True)
            st.markdown("---")

            # ── 3. 세부 체크리스트 (1D 기준 결과 매칭) ──
            ref_res = mtf_results.get(("1d", position_side)) or res_price
            if ref_res:
                c_score  = ref_res["score"]
                c_status = ref_res["status_text"]
                sc1, sc2 = st.columns([1, 3])
                with sc1: st.metric(label=f"스코어 (1d/{position_side[:5]})", value=f"{c_score} / {max_possible_score}")
                with sc2:
                    st.markdown(f"<p style='font-size:15px; font-weight:700; margin:6px 0;'>📟 {c_status}</p>", unsafe_allow_html=True)
                    if max_possible_score > 0: st.progress(int(c_score / max_possible_score * 100))

                st.markdown("##### ⚡ 세부 지표 체크리스트 (1D 기준)")
                check_cols = st.columns(2)
                for idx, (label, active, passed) in enumerate(zip(COND_LABELS, active_conditions, ref_res["c_results"])):
                    col = check_cols[0] if idx < 5 else check_cols[1]
                    if active:
                        if passed: col.success(f"⭕ [충족] {label}")
                        else:       col.error(f"❌ [미달] {label}")
                    else:
                        col.warning(f"⚪ [제외] {label}")
    else:
        st.warning("⚠️ 왼쪽 제어 콘솔에서 종목 티커를 입력해 주세요.")

# ==========================================
# 6. 모드 2: 주요 종목 마스터 스캐너 (기존 원본과 동일)
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
                        "티커": scan_list[idx], "종목명": STOCK_MAP.get(scan_list[idx], scan_list[idx]),
                        "현재가": f"{m['currency']}{m['current_price']:,.2f}", "스코어_raw": m['score'],
                        "스코어": f"{m['score']}/{max_possible_score}", "통합 시그널": m["status_text"]
                    })
                prog_bar.progress((idx + 1) / len(scan_list))
        if scan_results: st.session_state["cached_scan"] = scan_results

    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        df_display = pd.DataFrame(st.session_state["cached_scan"])
        df_view = df_display.drop(columns=["스코어_raw"], errors="ignore")

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

        if top_10_items:
            for i in range(0, len(top_10_items), 5):
                row_items = top_10_items[i: i + 5]
                grid_cols = st.columns(5)
                for idx, item in enumerate(row_items):
                    with grid_cols[idx]:
                        if "사격 개시" in str(item.get("통합 시그널")): badge_color = "#e6f9ed"; text_color = "#00802b"
                        elif "위험구역" in str(item.get("통합 시그널")): badge_color = "#ffe6e6"; text_color = "#cc0000"
                        else: badge_color = "#fff2cc"; text_color = "#cc9900"

                        st.markdown(f"""
                        <div style="border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:12px; text-align:center; background-color:#ffffff; box-shadow:0px 2px 4px rgba(0,0,0,0.04);">
                            <span style="font-weight:700; color:#1a202c; font-size:14px; display:block; text-overflow:ellipsis; white-space:nowrap; overflow:hidden;">{item.get("종목명")}</span>
                            <code style="color:#4a5568; font-size:11px; background-color:#f7fafc; padding:2px 6px; border-radius:4px;">{item.get("티커")}</code>
                            <div style="font-size:18px; font-weight:800; color:#2d3748; margin:8px 0;">{item.get("현재가")}</div>
                            <div style="font-size:12px; color:#718096; margin-bottom:8px;">📊 스코어: <b style="color:#2b6cb0;">{item.get("스코어")} 점</b></div>
                            <div style="background-color:{badge_color}; color:{text_color}; font-size:11px; padding:4px; border-radius:5px; font-weight:bold; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{item.get("통합 시그널")}</div>
                        </div>""", unsafe_allow_html=True)

                        if st.button(f"📈 {item.get('티커')} 분석", key=f"grid_redirect_{item.get('티커')}_{i}_{idx}", use_container_width=True):
                            st.session_state["ticker_buffer"] = item.get("티커")
                            st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                            st.session_state["input_key_trigger"] += 1
                            st.rerun()
