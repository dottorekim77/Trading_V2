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
st.set_page_config(page_title="추세추종 대가들의 마스터 대시보드", layout="wide", page_icon="📈")

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

# ── 애플 스타일 카드 컨텐츠 컴포넌트 헬퍼 ────────────────
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

_defaults = {"ticker_buffer": "IONQ", "mode_buffer": "🎯 단일 종목 검색", "position_buffer": "LONG (매수)",
             "selected_entry_price": 0.0, "target_tp_pct": 10.0, "target_sl_pct": 5.0, "input_key_trigger": 0,
             "cur_conds": [True]*10}
for _sk, _sv in _defaults.items():
    if _sk not in st.session_state: st.session_state[_sk] = _sv

strat_keys = list(st.session_state["saved_strategies"].keys())
if "active_strategy_name" not in st.session_state or st.session_state.active_strategy_name not in st.session_state["saved_strategies"]:
    st.session_state.active_strategy_name = strat_keys[0] if strat_keys else "임시 미지정 전략"

if strat_keys and st.session_state.active_strategy_name in st.session_state["saved_strategies"]:
    sd = st.session_state["saved_strategies"][st.session_state.active_strategy_name]
    st.session_state["cur_conds"] = sd.get("active_conds", [True]*10)
    st.session_state["target_tp_pct"] = float(sd.get("target_tp_pct", 10.0))
    st.session_state["target_sl_pct"] = float(sd.get("target_sl_pct", 5.0))

kt = st.session_state["input_key_trigger"]

# ==========================================
# 4. 마스터 제어 콘솔 (사이드바 - 애플 다크뷰)
# ==========================================
st.sidebar.markdown("<div style='padding:16px 4px 8px 4px;'>"
                    "<span style='font-size:16px; font-weight:700; color:#f5f5f7; letter-spacing:-0.3px;'>📉 TrendMaster Pro</span>"
                    "<br><span style='font-size:11px; color:#8e8e93;'>Premium Trend Following Screen</span></div>",
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
    scanner_interval = st.sidebar.selectbox("스캐너 시간대 설정:", options=["1d", "1h"], index=0, key=f"i_select_{kt}")
else:
    scanner_interval = "1d"

st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
st.sidebar.markdown("<span style='font-size:11px; font-weight:600; color:#8e8e93; text-transform:uppercase;'>내 포지션 전략</span>", unsafe_allow_html=True)

# 추세추종 특성상 LONG 기준 최적화 유지를 권장하나 컴포넌트 유지
position_side = "LONG (매수)"

current_entry = st.sidebar.number_input("내 실제 진입 평단가", value=float(st.session_state["selected_entry_price"]), step=0.01, key=f"e_input_{kt}")
st.session_state["selected_entry_price"] = current_entry

target_tp_pct = st.sidebar.number_input("목표 익절 비율 (%)", value=float(st.session_state["target_tp_pct"]), step=0.1, key=f"tp_input_{kt}")
st.session_state["target_tp_pct"] = target_tp_pct

target_sl_pct = st.sidebar.number_input("제한 손절 비율 (%)", value=float(st.session_state["target_sl_pct"]), step=0.1, key=f"sl_input_{kt}")
st.session_state["target_sl_pct"] = target_sl_pct

curr_sign = "₩" if (".KS" in ticker or ".KQ" in ticker) else "$"

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
                st.session_state["cur_conds"] = tsd.get("active_conds", [True]*10)
                st.session_state["ticker_buffer"] = tsd.get("ticker", "IONQ")
                st.session_state["selected_entry_price"] = float(tsd.get("entry_price", 0.0))
                st.session_state["target_tp_pct"] = float(tsd.get("target_tp_pct", 10.0))
                st.session_state["target_sl_pct"] = float(tsd.get("target_sl_pct", 5.0))
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

# ── 새로운 10가지 조건식 라벨 구성 ──────────────────────────────────────────
COND_LABELS = [
    "① 시장/지수 필터링 (Index > 20EMA)",
    "② 장기 정배열 (Price > 50 > 150 > 200 EMA)",
    "③ 주가 위치 필터 (52주 최저+25% 이상, 최고-25% 이내)",
    "④ 변동성 축소 패턴 (최근 변동폭 < 전월 변동폭)",
    "⑤ 박스권 돌파 (종가 > 최근 20일 최고가)",
    "⑥ 메이저 수급 폭발 (거래량 > 20일 평균의 250%)",
    "⑦ 추세 강도 검증 (ADX ≥ 20 및 +DI > -DI 골든크로스)",
    "⑧ 위험 한계 준수 (현재가 대비 2×ATR 하락 여유 확보)",
    "⑨ 기대 수익비 우위 (상단 저항폭 ≥ 하단 손절폭의 2배)",
    "⑩ 추적 이탈 방지 상태 (종가 > 20일 이동평균선 지지)"
]

dk = f"{st.session_state.active_strategy_name}_{kt}"
with st.sidebar.expander(f"⚙️ 조건 활성화 설정", expanded=False):
    active_conditions = []
    c_defaults = st.session_state["cur_conds"]
    for i in range(10):
        v = st.checkbox(COND_LABELS[i], value=c_defaults[i] if i < len(c_defaults) else True, key=f"c_box_{i}_{dk}")
        active_conditions.append(v)

max_possible_score = sum(active_conditions)

st.sidebar.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
default_input_name = "" if st.session_state.active_strategy_name == "임시 미지정 전략" else st.session_state.active_strategy_name
new_strat_name = st.sidebar.text_input("전략 이름", value=default_input_name, placeholder="이름 입력 후 저장", key=f"s_name_{dk}")
if st.sidebar.button("💾  전략 저장 / 수정", use_container_width=True, key=f"save_btn_{dk}"):
    save_key = new_strat_name.strip() if new_strat_name.strip() else "추세추종 마스터 전략"
    st.session_state["saved_strategies"][save_key] = {
        "ticker": st.session_state["ticker_buffer"], "position_side": position_side,
        "entry_price": current_entry, "target_tp_pct": target_tp_pct, "target_sl_pct": target_sl_pct,
        "active_conds": active_conditions
    }
    save_strategies_permanently()
    st.session_state.active_strategy_name = save_key
    st.session_state["cur_conds"] = active_conditions
    st.session_state["target_tp_pct"] = target_tp_pct
    st.session_state["target_sl_pct"] = target_sl_pct
    st.session_state["input_key_trigger"] += 1
    st.rerun()

# ==========================================
# 5. 수학/기술적 분석 엔진 (대가들의 10대 조건식 적용)
# ==========================================
def get_yahoo_custom_analysis(symbol, interval, forced_position=None):
    if not symbol: return None
    symbol = symbol.upper().strip()
    
    # 지표 산출을 위한 충분한 역사적 데이터 확보
    period_str = "3y" if interval in ["1d", "1wk"] else "730d"

    try:
        # 시장 지수 매핑 필터링 결정용 지수 확보
        if ".KS" in symbol: index_symbol = "^KS11"
        elif ".KQ" in symbol: index_symbol = "^KQ11"
        else: index_symbol = "^GSPC"
        
        idx_df = yf.Ticker(index_symbol).history(period="100d", interval=interval)
        if not idx_df.empty:
            idx_df['EMA20'] = idx_df['Close'].ewm(span=20, adjust=False).mean()
            market_filter = bool(idx_df['Close'].iloc[-1] > idx_df['EMA20'].iloc[-1])
        else:
            market_filter = True

        df = yf.Ticker(symbol).history(period=period_str, interval=interval)
        if df.empty or len(df) < 252: return None
        df = df.sort_index(ascending=True).ffill().bfill()

        # 기술적 지표 계산 
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA150'] = df['Close'].ewm(span=150, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        
        # 52주 최고/최저가
        df['Min_52wk'] = df['Low'].rolling(window=252, min_periods=50).min()
        df['Max_52wk'] = df['High'].rolling(window=252, min_periods=50).max()
        
        # 최근 최고가 저항선 변수 (20일 최고가)
        df['Max_20v'] = df['High'].shift(1).rolling(window=20).max()
        
        # 거래량 평활
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        
        # ADX / DMI 수치 연산
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

        last, prev = df.iloc[-1], df.iloc[-2]
        
        # 4번 조건: 최근 15거래일 변동폭 vs 그 전 30거래일(한 달간) 변동폭 비교
        recent_range = df['High'].tail(15).max() - df['Low'].tail(15).min()
        prior_range = df['High'].iloc[-45:-15].max() - df['Low'].iloc[-45:-15].min()
        vcp_pattern = bool(recent_range < prior_range)

        # 9번 조건: 기대수익비 산출
        resistance_price = last['Max_52wk'] # 직전 주요 고가 저항선 대용
        stop_loss_price = last['Close'] - (2 * last['ATR'])
        reward_side = resistance_price - last['Close']
        risk_side = last['Close'] - stop_loss_price
        profit_ratio_cond = bool(reward_side >= (risk_side * 2))

        # 10가지 조건 탐지식 바인딩
        c_results = [
            market_filter,                                                                  # 1
            bool(last['Close'] > last['EMA50'] > last['EMA150'] > last['EMA200']),         # 2
            bool(last['Close'] >= last['Min_52wk'] * 125 and last['Close'] >= last['Max_52wk'] * 0.75), # 3
            vcp_pattern,                                                                    # 4
            bool(last['Close'] >= last['Max_20v']),                                         # 5
            bool(last['Volume'] >= last['Vol_MA20'] * 2.5),                                 # 6
            bool(last['ADX'] >= 20 and last['Plus_DI'] > last['Minus_DI']),                 # 7
            bool(risk_side > 0),                                                            # 8 (구조상 항상 충족)
            profit_ratio_cond,                                                              # 9
            bool(last['Close'] > last['EMA20'])                                             # 10
        ]

        score = sum([1 for i, active in enumerate(active_conditions) if active and c_results[i]])
        fg, bg, lbl = get_signal_theme(score, max_possible_score)
        return {"df": df, "score": score, "status_text": f"{lbl} ({score}/{max_possible_score})",
                "current_price": last['Close'], "currency": "₩" if (".KS" in symbol or ".KQ" in symbol) else "$",
                "c_results": c_results, "fg": fg, "bg": bg, "lbl": lbl, "atr": last['ATR'], "stop_line": stop_loss_price}
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

    INTERVALS = ["1d"]
    with st.spinner("⏳ 대가들의 알고리즘 기반 분석 연산 실행 중..."):
        res = get_yahoo_custom_analysis(ticker, "1d")

    if res is None:
        st.error("❌ 현재 시세 데이터를 불러오지 못했습니다. 티커 부호 상태나 데이터셋 구성을 점검하세요.")
        st.stop()

    c_price, curr = res["current_price"], res["currency"]

    # 실시간 자산 관리 상태 모니터링
    st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>실시간 시스템 산출 모니터링</p>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔥 현재가", f"{curr}{c_price:,.2f}")
    m2.metric("🛡️ 시스템 권장 손절선 (2×ATR)", f"{curr}{res['stop_line']:,.2f}")
    
    if current_entry > 0:
        realtime_profit = ((c_price - current_entry) / current_entry) * 100
        calculated_tp = current_entry * (1 + target_tp_pct / 100)
        calculated_sl = current_entry * (1 - target_sl_pct / 100)
        m3.metric(f"🎯 목표 익절가 ({target_tp_pct}%)", f"{curr}{calculated_tp:,.2f}")
        m4.metric(f"🚨 수동 로스컷 가격 ({target_sl_pct}%)", f"{curr}{calculated_sl:,.2f}")
    else:
        m3.metric("🎯 내 목표 익절가", "평단가 미입력")
        m4.metric("🚨 수동 로스컷 가격", "평단가 미입력")

    st.markdown("<hr>", unsafe_allow_html=True)

    # 종합 스코어바 및 타점 체크리스트 구현
    st.markdown(f"<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>대가들의 조건식 체크리스트 검증 결과</p>", unsafe_allow_html=True)
    sc1, sc2 = st.columns([1, 3])
    with sc1:
        st.markdown(create_apple_html_card(
            f"<div style='font-size:11px;color:#8e8e93;font-weight:500;'>종합 추세 부합도</div>"
            f"<div style='font-size:28px;font-weight:800;color:{res['fg']};margin:4px 0;'>{res['score']}<span style='font-size:14px;color:#8e8e93;'>/{max_possible_score}</span></div>"
            f"<div>{create_apple_pill(res['lbl'], res['fg'], res['bg'])}</div>"
        ), unsafe_allow_html=True)
    with sc2:
        if max_possible_score > 0:
            pct = int(res["score"] / max_possible_score * 100)
            st.markdown(f"<div style='background:#fff; border:1px solid #e5e5ea; border-radius:14px; padding:14px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
                        f"<div style='font-size:11px;color:#8e8e93;font-weight:500;margin-bottom:8px;'>추세 조건 매칭률</div>"
                        f"<div style='background:#f2f2f7; border-radius:99px; height:8px; overflow:hidden;'>"
                        f"<div style='background:{res['fg']}; width:{pct}%; height:8px; border-radius:99px; transition:width 0.5s ease;'></div></div>"
                        f"<div style='font-size:20px; font-weight:700; color:{res['fg']}; margin-top:8px;'>{pct}%</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    check_cols = st.columns(2)
    for idx, (label, active, passed) in enumerate(zip(COND_LABELS, active_conditions, res["c_results"])):
        col = check_cols[0] if idx < 5 else check_cols[1]
        if active:
            if passed: col.markdown(create_apple_html_card(f"✅ <span style='font-size:12px;font-weight:600;color:#1c6b3a;'>{label}</span>", bg="#f0fdf4", border="#bbf7d0"), unsafe_allow_html=True)
            else: col.markdown(create_apple_html_card(f"❌ <span style='font-size:12px;font-weight:500;color:#9b1c1c;'>{label}</span>", bg="#fff5f5", border="#fecaca"), unsafe_allow_html=True)
        else: col.markdown(create_apple_html_card(f"⬜ <span style='font-size:12px;color:#c7c7cc;'>{label}</span>", bg="#fafafa", border="#e5e5ea"), unsafe_allow_html=True)

# ==========================================
# 7. 메인 뷰 — 주요 종목 마스터 스캐너 모드
# ==========================================
else:
    st.markdown(f"<h2 style='font-size:22px;font-weight:700;color:#1c1c1e;margin-bottom:4px;'>추세 마스터 스캐너</h2>"
                f"<p style='font-size:13px;color:#8e8e93;margin-bottom:20px;'>지정 시간대({scanner_interval}) 통합 우량 추세 풀 검증 조건 검색</p>", unsafe_allow_html=True)
    
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

        def thread_scanner(sym):
            return sym, get_yahoo_custom_analysis(sym, scanner_interval)
            
        with ThreadPoolExecutor(max_workers=8) as executor:
            for idx, (sym_k, m) in enumerate(executor.map(thread_scanner, scan_list)):
                if m:
                    scan_results.append({
                        "티커": sym_k, "종목명": STOCK_MAP.get(sym_k, sym_k), "현재가": f"{m['currency']}{m['current_price']:,.2f}",
                        "score_raw": m["score"], "signal_lbl": m["lbl"], "fg": m["fg"], "bg": m["bg"]
                    })
                prog_bar.progress(min(1.0, (idx + 1) / len(scan_list)))
            
        if scan_results:
            st.session_state["cached_scan"] = sorted(scan_results, key=lambda x: x["score_raw"], reverse=True)

    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        data = st.session_state["cached_scan"]
        df_view = pd.DataFrame([{
            "종목코드": d["티커"], "종목명": d["종목명"], "현재시세": d["현재가"],
            "📊 스코어 스케일": f"{d['score_raw']}/{max_possible_score}", "추세 부합 상태": d["signal_lbl"]
        } for d in data])

        def color_signal_cell(val):
            v = str(val).replace(" ", "")
            if "사격" in v: return "background-color: #d1f5e0; color: #1c6b3a; font-weight: 600;"
            if "위험" in v: return "background-color: #fde8e8; color: #9b1c1c; font-weight: 600;"
            return "background-color: #fef9c3; color: #7d5a00; font-weight: 600;"

        styled_df = df_view.style.map(color_signal_cell, subset=['추세 부합 상태'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # 하단 카드 리스트 Top 10 레이아웃
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'>실시간 스캔 매칭률 Top 10 순위군</p>", unsafe_allow_html=True)
        
        top_10 = data[:10]
        for row_idx in range(0, len(top_10), 5):
            grid_cols = st.columns(5)
            for idx, item in enumerate(top_10[row_idx:row_idx+5]):
                with grid_cols[idx]:
                    st.markdown(
                        f"<div style='background:#fff; border:1px solid #e5e5ea; border-radius:14px; padding:14px 12px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); margin-bottom:8px;'>"
                        f"<div style='font-size:13px; font-weight:700; color:#1c1c1e; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{item['종목명']}</div>"
                        f"<div style='font-size:16px; font-weight:800; color:#1c1c1e; margin:6px 0;'>{item['현재가']}</div>"
                        f"<div style='background:{item['bg']}; border-radius:8px; padding:6px; margin-bottom:8px;'>"
                        f"<div style='font-size:10px; color:{item['fg']}; font-weight:600;'>SCORE</div>"
                        f"<div style='font-size:14px; font-weight:800; color:{item['fg']};'>{item['score_raw']}/{max_possible_score}</div>"
                        f"<div style='font-size:11px; font-weight:600; color:{item['fg']};'>{item['signal_lbl']}</div></div>"
                        f"</div>", unsafe_allow_html=True)
                    
                    if st.button(f"🔍 {item['티커']} 분석", key=f"grid_trig_{item['티커']}_{row_idx}_{idx}", use_container_width=True):
                        st.session_state["ticker_buffer"] = item['티커']
                        st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                        st.session_state["input_key_trigger"] += 1
                        st.rerun()
