import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. 페이지 설정 및 글로벌 CSS (Apple / macOS 스타일)
# ==========================================
st.set_page_config(page_title="한/미 통합 주식 실시간 마스터 대시보드", layout="wide", page_icon="📈")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* 전체 앱 기본 폰트 및 배경 설정 (SF Pro 스타일) */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif !important;
}

/* 메인 프레임 라이트 그레이 배경 */
.stApp { background-color: #f5f5f7; }

/* 사이드바 다크 모드 (macOS Pro 앱 스타일) */
section[data-testid="stSidebar"] {
    background: #1c1c1e !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * { color: #f5f5f7 !important; }
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stSelectbox select {
    background: #2c2c2e !important;
    border: 1px solid #3a3a3c !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
}
section[data-testid="stSidebar"] .stRadio label { color: #ebebf5 !important; }
section[data-testid="stSidebar"] .stExpander {
    background: #2c2c2e !important;
    border: 1px solid #3a3a3c !important;
    border-radius: 12px !important;
}
section[data-testid="stSidebar"] button {
    background: #2c2c2e !important;
    border: 1px solid #3a3a3c !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
    font-size: 12px !important;
}
section[data-testid="stSidebar"] button:hover {
    background: #3a3a3c !important;
    border-color: #0a84ff !important;
}

/* 메인 레이아웃 여백 정리 */
.block-container { padding: 1.5rem 2rem 2rem 2rem !important; max-width: 1400px; }

/* 불필요한 Streamlit 기본 요소 숨김 처리 */
#MainMenu, footer, header { visibility: hidden; }

/* 메인 대시보드 Metric 컴포넌트 */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 14px;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
div[data-testid="metric-container"] label { color: #8e8e93 !important; font-size: 11px !important; font-weight: 500 !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 18px !important; font-weight: 700 !important; color: #1c1c1e !important; }

/* 프로그레스 바 정밀 바인딩 */
div[data-testid="stProgress"] > div { border-radius: 99px !important; height: 6px !important; }
div[data-testid="stProgress"] > div > div { border-radius: 99px !important; background: #0a84ff !important; }

/* 메인 UI 인터랙티브 버튼 디자인 */
.stButton > button {
    border-radius: 10px !important;
    border: 1px solid #e5e5ea !important;
    background: #ffffff !important;
    color: #1c1c1e !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 6px 14px !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #f0f0f5 !important;
    border-color: #0a84ff !important;
    color: #0a84ff !important;
}

/* 데이터프레임 라운딩 처리 및 보더라인 제거 */
div[data-testid="stDataFrame"] { border-radius: 14px !important; overflow: hidden; border: 1px solid #e5e5ea !important; }

/* 메인 영역 확장 컴포넌트 */
details { border-radius: 12px !important; border: 1px solid #e5e5ea !important; background: #fff !important; }
summary { font-weight: 600 !important; font-size: 13px !important; }

/* 디바이더 슬림화 */
hr { border: none !important; border-top: 1px solid #e5e5ea !important; margin: 12px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── 애플 스타일 카드 컨텐츠 컴포넌트 헬퍼 (충돌 예방용 작명) ────────────────
def create_apple_html_card(content_html, bg="#ffffff", border="#e5e5ea", radius=14, padding="14px 18px"):
    return (f"<div style='background:{bg}; border:1px solid {border}; border-radius:{radius}px; "
            f"padding:{padding}; box-shadow:0 1px 3px rgba(0,0,0,0.04); margin-bottom:8px;'>"
            f"{content_html}</div>")

def create_apple_pill(text, fg, bg):
    return (f"<span style='background:{bg}; color:{fg}; font-size:11px; font-weight:600; "
            f"padding:3px 9px; border-radius:99px; white-space:nowrap;'>{text}</span>")

def get_signal_theme(score, max_score):
    if max_score == 0: return "#8e8e93", "#f2f2f7", "—"
    ratio = score / max_score
    if ratio >= 0.8: return "#1c6b3a", "#d1f5e0", "🟢 사격 개시"
    if ratio <= 0.4: return "#9b1c1c", "#fde8e8", "🔴 위험구역"
    return "#7d5a00", "#fef9c3", "🟡 관망"

# ==========================================
# 2. 전역 종목 데이터 셋 구성
# ==========================================
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
for k, v in STOCK_MAP.items(): INV_STOCK_MAP[v.lower()] = k
US_SCAN_LIST = [k for k in STOCK_MAP.keys() if not k.endswith((".KS", ".KQ"))]
KR_SCAN_LIST = [k for k in STOCK_MAP.keys() if k.endswith((".KS", ".KQ"))]

# ==========================================
# 3. Session State 동기화 및 초기화
# ==========================================
if "saved_strategies" not in st.session_state:
    try:
        if os.path.exists("saved_strategies.json"):
            with open("saved_strategies.json", "r", encoding="utf-8") as f_json:
                st.session_state["saved_strategies"] = json.load(f_json)
        else: st.session_state["saved_strategies"] = {}
    except Exception: st.session_state["saved_strategies"] = {}

def save_strategies_permanently():
    with open("saved_strategies.json", "w", encoding="utf-8") as f_json:
        json.dump(st.session_state["saved_strategies"], f_json, ensure_ascii=False, indent=4)

_defaults = {"ticker_buffer": "IONQ", "mode_buffer": "🎯 단일 종목 검색", "position_buffer": "SHORT (공매도)",
             "selected_entry_price": 0.0, "target_tp_pct": 3.0, "target_sl_pct": 1.0, "input_key_trigger": 0,
             "cur_short_ma": 20, "cur_mid_ma": 50, "cur_long_ma": 200, "cur_vol_break": 1.50, "cur_conds": [True]*10}
for _sk, _sv in _defaults.items():
    if _sk not in st.session_state: st.session_state[_sk] = _sv

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

kt = st.session_state["input_key_trigger"]

# ==========================================
# 4. 마스터 제어 콘솔 (사이드바 - 애플 다크뷰)
# ==========================================
st.sidebar.markdown("<div style='padding:16px 4px 8px 4px;'>"
                    "<span style='font-size:16px; font-weight:700; color:#f5f5f7; letter-spacing:-0.3px;'>📉 AlgoDashboard</span>"
                    "<br><span style='font-size:11px; color:#8e8e93;'>Premium Signal Screen</span></div>",
                    unsafe_allow_html=True)
st.sidebar.markdown("<hr style='border-color:#3a3a3c;margin:0 0 12px 0;'>", unsafe_allow_html=True)

mode_options = ["🎯 단일 종목 검색", "🔍 조건 스캐너"]
try: mode_idx = mode_options.index(st.session_state["mode_buffer"])
except ValueError: mode_idx = 0
app_mode = st.sidebar.radio("작동 모드 전환:", options=mode_options, index=mode_idx, key=f"m_radio_{kt}")
st.session_state["mode_buffer"] = app_mode

st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
raw_in = st.sidebar.text_input("종목 이름 또는 티커 입력:", value=st.session_state["ticker_buffer"], key=f"t_input_{kt}").strip()
st.session_state["ticker_buffer"] = raw_in
ticker = INV_STOCK_MAP.get(raw_in.lower(), raw_in.upper()) if raw_in else ""

if app_mode == "🔍 조건 스캐너":
    scanner_interval = st.sidebar.selectbox("스캐너 시간대 설정:", options=["15m", "30m", "1h", "1d"], index=0, key=f"i_select_{kt}")
else:
    scanner_interval = "15m"

st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
st.sidebar.markdown("<span style='font-size:11px; font-weight:600; color:#8e8e93; text-transform:uppercase;'>내 포지션 전략</span>", unsafe_allow_html=True)

pos_options = ["LONG (매수)", "SHORT (공매도)"]
try: pos_idx = pos_options.index(st.session_state["position_buffer"])
except ValueError: pos_idx = 1
position_side = st.sidebar.radio("포지션 방향 선택", options=pos_options, index=pos_idx, key=f"p_radio_{kt}")
st.session_state["position_buffer"] = position_side

current_entry = st.sidebar.number_input("내 실제 진입 평단가", value=float(st.session_state["selected_entry_price"]), step=0.01, key=f"e_input_{kt}")
st.session_state["selected_entry_price"] = current_entry

target_tp_pct = st.sidebar.number_input("목표 익절 비율 (%)", value=float(st.session_state["target_tp_pct"]), step=0.1, key=f"tp_input_{kt}")
st.session_state["target_tp_pct"] = target_tp_pct

target_sl_pct = st.sidebar.number_input("제한 손절 비율 (%)", value=float(st.session_state["target_sl_pct"]), step=0.1, key=f"sl_input_{kt}")
st.session_state["target_sl_pct"] = target_sl_pct

curr_sign = "₩" if (".KS" in ticker or ".KQ" in ticker) else "$"
if current_entry > 0:
    side_tp = current_entry * (1 + (target_tp_pct / 100)) if "LONG" in position_side else current_entry * (1 - (target_tp_pct / 100))
    side_sl = current_entry * (1 - (target_sl_pct / 100)) if "LONG" in position_side else current_entry * (1 + (target_sl_pct / 100))
    st.sidebar.markdown(
        f"<div style='display:flex;gap:6px;margin-top:6px;'>"
        f"<div style='flex:1;background:#1a3a2a;border:1px solid #1c6b3a;border-radius:10px;padding:8px;text-align:center;'>"
        f"<div style='font-size:9px;color:#30d158;font-weight:600;'>익절선</div>"
        f"<div style='font-size:12px;color:#30d158;font-weight:700;'>{curr_sign}{side_tp:,.2f}</div></div>"
        f"<div style='flex:1;background:#3a1a1a;border:1px solid #9b1c1c;border-radius:10px;padding:8px;text-align:center;'>"
        f"<div style='font-size:9px;color:#ff453a;font-weight:600;'>손절선</div>"
        f"<div style='font-size:12px;color:#ff453a;font-weight:700;'>{curr_sign}{side_sl:,.2f}</div></div>"
        f"</div>", unsafe_allow_html=True)

# ── 전략 보관함 ──────────────────────────────────────────────────────────
st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
st.sidebar.markdown("<span style='font-size:11px; font-weight:600; color:#8e8e93; text-transform:uppercase;'>나만의 조건 마스터 보관함</span>", unsafe_allow_html=True)
strat_keys = list(st.session_state["saved_strategies"].keys())
if strat_keys:
    for idx, key in enumerate(strat_keys):
        is_active = (key == st.session_state.active_strategy_name)
        btn_label = f"✦ {key}" if is_active else f"  {key}"
        sb_col_load, sb_col_del = st.sidebar.columns([5, 1])
        with sb_col_load:
            if st.button(btn_label, key=f"v_load_{idx}", use_container_width=True):
                st.session_state["active_strategy_name"] = key
                tsd = st.session_state["saved_strategies"][key]
                st.session_state["cur_short_ma"] = int(tsd.get("short_ma", 20))
                st.session_state["cur_mid_ma"] = int(tsd.get("mid_ma", 50))
                st.session_state["cur_long_ma"] = int(tsd.get("long_ma", 200))
                st.session_state["cur_vol_break"] = float(tsd.get("vol_breakout", 1.50))
                st.session_state["cur_conds"] = tsd.get("active_conds", [True]*10)
                st.session_state["ticker_buffer"] = tsd.get("ticker", "IONQ")
                st.session_state["position_buffer"] = tsd.get("position_side", "SHORT (공매도)")
                st.session_state["selected_entry_price"] = float(tsd.get("entry_price", 0.0))
                st.session_state["target_tp_pct"] = float(tsd.get("target_tp_pct", 3.0))
                st.session_state["target_sl_pct"] = float(tsd.get("target_sl_pct", 1.0))
                st.session_state["input_key_trigger"] += 1
                st.rerun()
        with sb_col_del:
            if st.button("✕", key=f"v_del_{idx}", use_container_width=True):
                if key in st.session_state["saved_strategies"]: del st.session_state["saved_strategies"][key]
                save_strategies_permanently()
                remaining_keys = list(st.session_state["saved_strategies"].keys())
                st.session_state.active_strategy_name = remaining_keys[0] if remaining_keys else "임시 미지정 전략"
                st.session_state["input_key_trigger"] += 1
                st.rerun()
else:
    st.sidebar.caption("저장된 전략이 없습니다.")

# ── 확장 지표 로직 변수 설정 ───────────────────────────────────────────────
dk = f"{st.session_state.active_strategy_name}_{kt}"
short_ma = st.session_state["cur_short_ma"]
mid_ma = st.session_state["cur_mid_ma"]
long_ma = st.session_state["cur_long_ma"]
vol_break = st.session_state["cur_vol_break"]
active_conditions = list(st.session_state["cur_conds"])

if "LONG" in position_side:
    COND_LABELS = [f"① 현재가 > EMA{short_ma} 지지", f"② EMA{short_ma} > EMA{mid_ma} 정배열", f"③ EMA{mid_ma} > EMA{long_ma} 장기 정배열",
                   "④ RSI 과매도 이탈 (30~70 범위)", "⑤ MACD > Signal 우상향", "⑥ MACD 골든크로스 상태",
                   "⑦ BB 상단 미돌파 (상방 여유)", f"⑧ 거래량 {vol_break}배 돌파", "⑨ 종가 > 직전 고가 돌파", f"⑩ 시가 > EMA{short_ma} 갭상승"]
else:
    COND_LABELS = [f"① 현재가 < EMA{short_ma} 저항", f"② EMA{short_ma} < EMA{mid_ma} 역배열", f"③ EMA{mid_ma} < EMA{long_ma} 장기 역배열",
                   "④ -DI > +DI (매도 우세)", "⑤ MACD < Signal 우하향", "⑥ MACD 데드크로스 상태",
                   "⑦ BB 하단 미이탈 (하방 여유)", f"⑧ 거래량 {vol_break}배 돌파", "⑨ 종가 < 직전 저가 이탈", f"⑩ 시가 < EMA{short_ma} 갭하락"]

with st.sidebar.expander(f"⚙️ 조건 설정 — {st.session_state.active_strategy_name}", expanded=False):
    short_ma = st.number_input("단기 EMA", value=st.session_state["cur_short_ma"], key=f"s_ma_{dk}")
    mid_ma = st.number_input("중기 EMA", value=st.session_state["cur_mid_ma"], key=f"m_ma_{dk}")
    long_ma = st.number_input("장기 EMA", value=st.session_state["cur_long_ma"], key=f"l_ma_{dk}")
    vol_break = st.number_input("거래량 돌파 배수", value=st.session_state["cur_vol_break"], step=0.1, key=f"v_bk_{dk}")
    st.markdown("---")
    active_conditions = []
    c_defaults = st.session_state["cur_conds"]
    for i in range(10):
        v = st.checkbox(COND_LABELS[i], value=c_defaults[i] if i < len(c_defaults) else True, key=f"c_box_{i}_{dk}")
        active_conditions.append(v)

max_possible_score = sum(active_conditions)

st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
default_input_name = "" if st.session_state.active_strategy_name == "임시 미지정 전략" else st.session_state.active_strategy_name
new_strat_name = st.sidebar.text_input("전략 이름", value=default_input_name, placeholder="이름 입력 후 저장", key=f"s_name_{dk}")
if st.sidebar.button("💾  저장 / 수정 반영", use_container_width=True, key=f"save_btn_{dk}"):
    save_key = new_strat_name.strip() if new_strat_name.strip() else "나의 통합 전략"
    st.session_state["saved_strategies"][save_key] = {
        "ticker": st.session_state["ticker_buffer"], "position_side": position_side,
        "entry_price": current_entry, "target_tp_pct": target_tp_pct, "target_sl_pct": target_sl_pct,
        "short_ma": short_ma, "mid_ma": mid_ma, "long_ma": long_ma, "vol_breakout": vol_break, "active_conds": active_conditions
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
# 5. 수학/기술적 분석 엔진
# ==========================================
def get_yahoo_custom_analysis(symbol, interval, forced_position=None):
    if not symbol: return None
    symbol = symbol.upper().strip()
    period_str = "60d" if interval in ["1m", "2m", "5m", "15m", "30m"] else ("730d" if interval == "1h" else "2y")
    include_prepost = interval in ["1m", "15m", "30m", "1h"]
    _position = forced_position if forced_position else position_side

    try:
        df = yf.Ticker(symbol).history(period=period_str, interval=interval, prepost=include_prepost)
        if df.empty or len(df) < max(50, long_ma): return None
        df = df.sort_index(ascending=True).ffill().bfill()

        df['EMA_Short'] = df['Close'].ewm(span=short_ma, adjust=False).mean()
        df['EMA_Mid'] = df['Close'].ewm(span=mid_ma, adjust=False).mean()
        df['EMA_Long'] = df['Close'].ewm(span=long_ma, adjust=False).mean()
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['MA20'] + (2 * df['STD20'])
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        high_diff, low_diff = df['High'].diff(), df['Low'].diff()
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
        tr = pd.concat([df['High'] - df['Low'], abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14).mean()
        df['Plus_DI'] = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=14).mean() / (atr_14 + 1e-9))
        df['Minus_DI'] = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=14).mean() / (atr_14 + 1e-9))

        last, prev = df.iloc[-1], df.iloc[-2]

        if "LONG" in _position:
            c_results = [
                bool(last['Close'] > last['EMA_Short']), bool(last['EMA_Short'] > last['EMA_Mid']), bool(last['EMA_Mid'] > last['EMA_Long']),
                bool(30 <= last['RSI'] <= 70), bool(last['MACD'] > last['Signal'] and last['MACD'] > prev['MACD']),
                bool(last['MACD'] > last['Signal']), bool(last['Close'] < last['BB_Upper']),
                bool(last['Volume'] > df['Volume'].tail(20).mean() * vol_break), bool(last['Close'] > prev['High']), bool(last['Open'] > last['EMA_Short'])
            ]
        else:
            c_results = [
                bool(last['Close'] < last['EMA_Short']), bool(last['EMA_Short'] < last['EMA_Mid']), bool(last['EMA_Mid'] < last['EMA_Long']),
                bool(last['Minus_DI'] > last['Plus_DI']), bool(last['MACD'] < last['Signal'] and last['MACD'] < prev['MACD']),
                bool(last['MACD'] < last['Signal']), bool(last['Close'] > last['BB_Lower']),
                bool(last['Volume'] > df['Volume'].tail(20).mean() * vol_break), bool(last['Close'] < prev['Low']), bool(last['Open'] < last['EMA_Short'])
            ]

        score = sum([1 for i, active in enumerate(active_conditions) if active and c_results[i]])
        fg, bg, lbl = get_signal_theme(score, max_possible_score)
        return {"df": df, "score": score, "status_text": f"{lbl} ({score}/{max_possible_score})",
                "current_price": last['Close'], "currency": "₩" if (".KS" in symbol or ".KQ" in symbol) else "$",
                "c_results": c_results, "fg": fg, "bg": bg, "lbl": lbl}
    except Exception: return None

# ==========================================
# 6. 메인 뷰 — 단일 종목 검색 모드
# ==========================================
if app_mode == "🎯 단일 종목 검색":
    name_disp = STOCK_MAP.get(ticker, ticker)
    st.markdown(f"<div style='margin-bottom:20px;'><h2 style='font-size:22px;font-weight:700;color:#1c1c1e;margin:0;'>{name_disp}</h2>"
                f"<span style='font-size:13px;color:#8e8e93;font-weight:500;'>{ticker}</span></div>" if ticker else 
                "<div style='margin-bottom:20px;'><h2 style='font-size:22px;font-weight:700;color:#1c1c1e;'>종목을 입력하세요</h2></div>", unsafe_allow_html=True)

    if not ticker:
        st.info("← 왼쪽 제어 패널에서 분석할 종목 이름 또는 티커를 입력해 주세요.")
        st.stop()

    INTERVALS = ["15m", "30m", "1h", "1d"]
    combos = [(iv, pos) for iv in INTERVALS for pos in ["LONG (매수)", "SHORT (공매도)"]]

    with st.spinner("⏳ 멀티타임프레임 연산 분석 실행 중..."):
        mtf_results = {}
        def fetch_combo(args):
            iv, pos = args
            return (iv, pos), get_yahoo_custom_analysis(ticker, iv, forced_position=pos)
        with ThreadPoolExecutor(max_workers=8) as executor:
            for key_combo, result in executor.map(fetch_combo, combos): mtf_results[key_combo] = result

    res_price = mtf_results.get(("1d", "LONG (매수)")) or mtf_results.get(("1d", "SHORT (공매도)"))
    if res_price is None:
        st.error("❌ 현재 시세 데이터를 불러오지 못했습니다. 티커 부호 상태나 거래소 개장 상황을 점검하세요.")
        st.stop()

    c_price, curr = res_price["current_price"], res_price["currency"]

    # 시간대별 점수 격자 테이블 (수평 콤팩트 라벨 배치)
    st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>시간대별 LONG / SHORT 점수 지표</p>", unsafe_allow_html=True)
    
    h0, h1, h2 = st.columns([1, 5, 5])
    h1.markdown("<div style='text-align:center; font-size:12px; font-weight:600; color:#1a56db; background:#e8f0fe; border-radius:8px; padding:5px;'>📈 LONG (매수)</div>", unsafe_allow_html=True)
    h2.markdown("<div style='text-align:center; font-size:12px; font-weight:600; color:#9b1c1c; background:#fde8e8; border-radius:8px; padding:5px;'>📉 SHORT (공매도)</div>", unsafe_allow_html=True)

    for iv in INTERVALS:
        c0, c1, c2 = st.columns([1, 5, 5])
        c0.markdown(f"<div style='display:flex; align-items:center; justify-content:center; min-height:38px;'><span style='font-size:12px; font-weight:700; color:#1c1c1e; background:#f2f2f7; padding:4px 10px; border-radius:8px; border:1px solid #e5e5ea;'>{iv}</span></div>", unsafe_allow_html=True)
        
        for col, target_side, side_col, side_tag in [(c1, "LONG (매수)", "#1a56db", "LONG"), (c2, "SHORT (공매도)", "#9b1c1c", "SHORT")]:
            res = mtf_results.get((iv, target_side))
            if res:
                col.markdown(f"<div style='background:{res['bg']}; border:1px solid {res['fg']}30; border-radius:10px; padding:7px 14px; display:flex; align-items:center; gap:10px;'>"
                             f"<span style='font-size:11px; font-weight:600; color:{side_col};'>{side_tag}</span>"
                             f"<span style='font-size:14px; font-weight:800; color:{res['fg']};'>{res['score']}/{max_possible_score}</span>"
                             f"<span style='font-size:11px; font-weight:600; color:{res['fg']};'>{res['lbl']}</span></div>", unsafe_allow_html=True)
            else:
                col.markdown("<div style='color:#c7c7cc; font-size:12px; padding:7px 14px;'>데이터 없음</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # 모니터링 컴포넌트 리파인
    if current_entry > 0:
        realtime_profit = ((c_price - current_entry) / current_entry) * 100 if "LONG" in position_side else ((current_entry - c_price) / current_entry) * 100
        calculated_tp = current_entry * (1 + target_tp_pct / 100) if "LONG" in position_side else current_entry * (1 - target_tp_pct / 100)
        calculated_sl = current_entry * (1 - target_sl_pct / 100) if "LONG" in position_side else current_entry * (1 + target_sl_pct / 100)
    else: realtime_profit = calculated_tp = calculated_sl = 0.0

    st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>실시간 자산 관리 상태 모니터링</p>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔥 현재가", f"{curr}{c_price:,.2f}")
    m2.metric("📊 실시간 수익률", f"{realtime_profit:+.2f}%" if current_entry > 0 else "평단가 미입력")
    m3.metric(f"🎯 익절 목표 ({target_tp_pct}%)", f"{curr}{calculated_tp:,.2f}" if current_entry > 0 else "—")
    m4.metric(f"🚨 로스컷 손절 ({target_sl_pct}%)", f"{curr}{calculated_sl:,.2f}" if current_entry > 0 else "—")

    st.markdown("<hr>", unsafe_allow_html=True)

    # 종합 스코어바 및 타점 체크리스트 구현
    ref_res = mtf_results.get(("1d", position_side)) or res_price
    if ref_res:
        st.markdown(f"<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>세부 조건 체크리스트 (1D · {position_side[:5]} 전략)</p>", unsafe_allow_html=True)
        sc1, sc2 = st.columns([1, 3])
        with sc1:
            st.markdown(create_apple_html_card(
                f"<div style='font-size:11px;color:#8e8e93;font-weight:500;'>종합 타점 스코어</div>"
                f"<div style='font-size:28px;font-weight:800;color:{ref_res['fg']};margin:4px 0;'>{ref_res['score']}<span style='font-size:14px;color:#8e8e93;'>/{max_possible_score}</span></div>"
                f"<div>{create_apple_pill(ref_res['lbl'], ref_res['fg'], ref_res['bg'])}</div>"
            ), unsafe_allow_html=True)
        with sc2:
            if max_possible_score > 0:
                pct = int(ref_res["score"] / max_possible_score * 100)
                st.markdown(f"<div style='background:#fff; border:1px solid #e5e5ea; border-radius:14px; padding:14px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
                            f"<div style='font-size:11px;color:#8e8e93;font-weight:500;margin-bottom:8px;'>조건식 만족도 매칭률</div>"
                            f"<div style='background:#f2f2f7; border-radius:99px; height:8px; overflow:hidden;'>"
                            f"<div style='background:{ref_res['fg']}; width:{pct}%; height:8px; border-radius:99px; transition:width 0.5s ease;'></div></div>"
                            f"<div style='font-size:20px; font-weight:700; color:{ref_res['fg']}; margin-top:8px;'>{pct}%</div></div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        check_cols = st.columns(2)
        for idx, (label, active, passed) in enumerate(zip(COND_LABELS, active_conditions, ref_res["c_results"])):
            col = check_cols[0] if idx < 5 else check_cols[1]
            if active:
                if passed: col.markdown(create_apple_html_card(f"✅ <span style='font-size:12px;font-weight:500;color:#1c6b3a;'>{label}</span>", bg="#f0fdf4", border="#bbf7d0"), unsafe_allow_html=True)
                else: col.markdown(create_apple_html_card(f"❌ <span style='font-size:12px;font-weight:500;color:#9b1c1c;'>{label}</span>", bg="#fff5f5", border="#fecaca"), unsafe_allow_html=True)
            else: col.markdown(create_apple_html_card(f"⬜ <span style='font-size:12px;color:#c7c7cc;'>{label}</span>", bg="#fafafa", border="#e5e5ea"), unsafe_allow_html=True)

# ==========================================
# 7. 메인 뷰 — 주요 종목 마스터 스캐너 모드
# ==========================================
else:
    st.markdown(f"<h2 style='font-size:22px;font-weight:700;color:#1c1c1e;margin-bottom:4px;'>조건 스캐너</h2>"
                f"<p style='font-size:13px;color:#8e8e93;margin-bottom:20px;'>{scanner_interval} 기준전략 분할 매칭 조사 스크리닝</p>", unsafe_allow_html=True)
    
    m_col1, m_col2 = st.columns(2)
    with m_col1: scan_us = st.checkbox("🇺🇸 미국 우량주 그룹 포함", value=True)
    with m_col2: scan_kr = st.checkbox("🇰🇷 한국 우량주 그룹 포함", value=False)

    scan_list = []
    if scan_us: scan_list.extend(US_SCAN_LIST)
    if scan_kr: scan_list.extend(KR_SCAN_LIST)

    if st.button("🚀  실시간 전수 조건 검색 조사 스캔 시작"):
        st.session_state.pop("cached_scan", None)
        scan_results = []
        prog_bar = st.progress(0)

        # 상향 가독성을 위한 LONG/SHORT 조합 통합 매핑 조사 스캔
        all_combos = [(sym, "LONG (매수)") for sym in scan_list] + [(sym, "SHORT (공매도)") for sym in scan_list]
        raw_buffer = {}

        def thread_scanner(args):
            s, p = args
            return (s, p), get_yahoo_custom_analysis(s, scanner_interval, forced_position=p)
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            for idx, (combo_k, m) in enumerate(executor.map(thread_scanner, all_combos)):
                raw_buffer[combo_k] = m
                prog_bar.progress(min(1.0, (idx + 1) / len(all_combos)))

        for sym in scan_list:
            rl = raw_buffer.get((sym, "LONG (매수)"))
            rs = raw_buffer.get((sym, "SHORT (공매도)"))
            if not rl and not rs: continue
            
            ref_m = rl if rl else rs
            scan_results.append({
                "티커": sym, "종목명": STOCK_MAP.get(sym, sym), "현재가": f"{ref_m['currency']}{ref_m['current_price']:,.2f}",
                "long_score_raw": rl["score"] if rl else 0, "short_score_raw": rs["score"] if rs else 0,
                "long_signal": rl["lbl"] if rl else "관망", "short_signal": rs["lbl"] if rs else "관망"
            })
            
        if scan_results:
            st.session_state["cached_scan"] = sorted(scan_results, key=lambda x: x["long_score_raw"] + x["short_score_raw"], reverse=True)

    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        data = st.session_state["cached_scan"]
        df_view = pd.DataFrame([{
            "종목코드": d["티커"], "종목명": d["종목명"], "현재시세": d["현재가"],
            "📈 LONG 스코어": f"{d['long_score_raw']}/{max_possible_score}", "LONG 시그널": d["long_signal"],
            "📉 SHORT 스코어": f"{d['short_score_raw']}/{max_possible_score}", "SHORT 시그널": d["short_signal"]
        } for d in data])

        def color_signal_cell(val):
            v = str(val).replace(" ", "")
            if "사격" in v: return "background-color: #d1f5e0; color: #1c6b3a; font-weight: 600;"
            if "위험" in v: return "background-color: #fde8e8; color: #9b1c1c; font-weight: 600;"
            return "background-color: #fef9c3; color: #7d5a00; font-weight: 600;"

        styled_df = df_view.style.map(color_signal_cell, subset=['LONG 시그널', 'SHORT 시그널'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # 하단 카드 리스트 Top 10 레이아웃
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'>실시간 스캔 매칭률 Top 10 합산 정렬</p>", unsafe_allow_html=True)
        
        top_10 = data[:10]
        for row_idx in range(0, len(top_10), 5):
            grid_cols = st.columns(5)
            for idx, item in enumerate(top_10[row_idx:row_idx+5]):
                with grid_cols[idx]:
                    l_fg, l_bg, l_lbl = get_signal_theme(item["long_score_raw"], max_possible_score)
                    s_fg, s_bg, s_lbl = get_signal_theme(item["short_score_raw"], max_possible_score)
                    sym_code = item["티커"]
                    
                    st.markdown(
                        f"<div style='background:#fff; border:1px solid #e5e5ea; border-radius:14px; padding:14px 12px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); margin-bottom:8px;'>"
                        f"<div style='font-size:13px; font-weight:700; color:#1c1c1e; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{item['종목명']}</div>"
                        f"<div style='font-size:16px; font-weight:800; color:#1c1c1e; margin:6px 0;'>{item['현재가']}</div>"
                        f"<div style='display:flex; gap:4px; justify-content:center; flex-wrap:wrap;'>"
                        f"<div style='background:{l_bg}; border-radius:8px; padding:4px 8px; flex:1;'>"
                        f"<div style='font-size:9px; color:{l_fg}; font-weight:600;'>📈 LONG</div>"
                        f"<div style='font-size:12px; font-weight:800; color:{l_fg};'>{item['long_score_raw']}/{max_possible_score}</div></div>"
                        f"<div style='background:{s_bg}; border-radius:8px; padding:4px 8px; flex:1;'>"
                        f"<div style='font-size:9px; color:{s_fg}; font-weight:600;'>📉 SHORT</div>"
                        f"<div style='font-size:12px; font-weight:800; color:{s_fg};'>{item['short_score_raw']}/{max_possible_score}</div></div>"
                        f"</div></div>", unsafe_allow_html=True)
                    
                    if st.button(f"🔍 {sym_code} 분석", key=f"grid_trig_{sym_code}_{row_idx}_{idx}", use_container_width=True):
                        st.session_state["ticker_buffer"] = sym_code
                        st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                        st.session_state["input_key_trigger"] += 1
                        st.rerun()
