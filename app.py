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
st.set_page_config(page_title="AlgoTrader", layout="wide", page_icon="📈")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif !important;
}

/* 전체 배경 */
.stApp { background-color: #f5f5f7; }

/* 사이드바 */
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

/* 메인 컨텐츠 */
.block-container { padding: 1.5rem 2rem 2rem 2rem !important; max-width: 1400px; }

/* Streamlit 기본 헤더 숨기기 */
#MainMenu, footer, header { visibility: hidden; }

/* metric 카드 */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 14px;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label { color: #8e8e93 !important; font-size: 11px !important; font-weight: 500 !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 18px !important; font-weight: 700 !important; color: #1c1c1e !important; }

/* progress bar */
div[data-testid="stProgress"] > div { border-radius: 99px !important; height: 6px !important; }
div[data-testid="stProgress"] > div > div { border-radius: 99px !important; background: #0a84ff !important; }

/* success / error / warning */
div[data-testid="stAlert"] { border-radius: 10px !important; border: none !important; font-size: 12px !important; }

/* 버튼 */
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

/* dataframe */
div[data-testid="stDataFrame"] { border-radius: 14px !important; overflow: hidden; border: 1px solid #e5e5ea !important; }

/* expander */
details { border-radius: 12px !important; border: 1px solid #e5e5ea !important; background: #fff !important; }
summary { font-weight: 600 !important; font-size: 13px !important; }

/* 구분선 */
hr { border: none !important; border-top: 1px solid #e5e5ea !important; margin: 12px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── 헬퍼: 카드 컴포넌트 ──────────────────────────────────────────────────
def card(content_html, bg="#ffffff", border="#e5e5ea", radius=14, padding="14px 18px"):
    return (f"<div style='background:{bg}; border:1px solid {border}; border-radius:{radius}px; "
            f"padding:{padding}; box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:8px;'>"
            f"{content_html}</div>")

def pill(text, fg, bg):
    return (f"<span style='background:{bg}; color:{fg}; font-size:11px; font-weight:600; "
            f"padding:3px 9px; border-radius:99px; white-space:nowrap;'>{text}</span>")

def signal_style(score, max_score):
    if max_score == 0: return "#8e8e93", "#f2f2f7", "—"
    r = score / max_score
    if r >= 0.8:   return "#1c6b3a", "#d1f5e0", "🟢 사격개시"
    if r <= 0.4:   return "#9b1c1c", "#fde8e8", "🔴 위험구역"
    return "#7d5a00", "#fef9c3", "🟡 관망"

# ==========================================
# 2. 데이터
# ==========================================
STOCK_MAP = {
    "TSLA":"Tesla","NVDA":"Nvidia","AAPL":"Apple","MSFT":"Microsoft","AMZN":"Amazon",
    "GOOGL":"Alphabet","META":"Meta","NFLX":"Netflix","IONQ":"IonQ","PLTR":"Palantir",
    "AMD":"AMD","SOFI":"SoFi","MARA":"Marathon Digital","COIN":"Coinbase","BABA":"Alibaba",
    "AVGO":"Broadcom","QCOM":"Qualcomm","INTC":"Intel","SMCI":"Super Micro","CRM":"Salesforce",
    "ORCL":"Oracle","UBER":"Uber","HOOD":"Robinhood","SQ":"Block","PYPL":"PayPal",
    "MU":"Micron","SOL-USD":"Solana","SMH":"VanEck Semi ETF",
    "TQQQ":"ProShares TQQQ","SOXL":"Direxion SOXL","SPY":"S&P 500 ETF","QQQ":"Invesco QQQ",
    "LLY":"Eli Lilly","TSM":"TSMC","ASML":"ASML","CVNA":"Carvana","WMT":"Walmart",
    "COST":"Costco","NET":"Cloudflare","RKLB":"Rocket Lab","ASTS":"AST SpaceMobile",
    "005930.KS":"삼성전자","000660.KS":"SK하이닉스","005450.KQ":"형지I&C","042660.KS":"한화오션",
    "035420.KS":"NAVER","035720.KS":"카카오","005380.KS":"현대차","000270.KS":"기아",
    "247540.KQ":"에코프로비엠","086520.KQ":"에코프로","068270.KS":"셀트리온","005490.KS":"POSCO홀딩스",
    "373220.KS":"LG에너지솔루션","000100.KS":"유한양행","012330.KS":"현대모비스","207940.KS":"삼성바이오",
    "051910.KS":"LG화학","006400.KS":"삼성SDI","015760.KS":"한국전력","012450.KS":"한화에어로",
    "066570.KS":"LG전자","034020.KS":"두산에너빌리티","009540.KS":"HD한국조선","267250.KS":"HD현대일렉",
    "035900.KQ":"JYP Ent.","041510.KQ":"에스엠","259960.KS":"크래프톤","105560.KS":"KB금융",
    "055550.KS":"신한지주","000030.KS":"우리금융","011200.KS":"HMM","009830.KS":"한화솔루션",
    "272210.KS":"한화시스템","402340.KS":"SK스퀘어","022100.KQ":"포스코DX","058470.KQ":"리노공업",
    "293490.KQ":"카카오게임즈","263750.KQ":"펄어비스","138040.KS":"메리츠금융","003550.KS":"LG"
}
INV_STOCK_MAP = {k.lower(): k for k in STOCK_MAP}
for k, v in STOCK_MAP.items(): INV_STOCK_MAP[v.lower()] = k
US_SCAN_LIST = [k for k in STOCK_MAP if not k.endswith((".KS",".KQ"))]
KR_SCAN_LIST = [k for k in STOCK_MAP if k.endswith((".KS",".KQ"))]
INTERVALS    = ["15m","30m","1h","1d"]

# ==========================================
# 3. Session state 초기화
# ==========================================
if "saved_strategies" not in st.session_state:
    try:
        st.session_state["saved_strategies"] = (
            json.load(open("saved_strategies.json","r",encoding="utf-8"))
            if os.path.exists("saved_strategies.json") else {}
        )
    except: st.session_state["saved_strategies"] = {}

def save_permanently():
    json.dump(st.session_state["saved_strategies"],
              open("saved_strategies.json","w",encoding="utf-8"),
              ensure_ascii=False, indent=4)

_D = {"ticker_buffer":"IONQ","mode_buffer":"🎯 단일 종목 검색",
      "position_buffer":"LONG (매수)","selected_entry_price":0.0,
      "target_tp_pct":5.0,"target_sl_pct":2.0,"input_key_trigger":0,
      "cur_short_ma":20,"cur_mid_ma":50,"cur_long_ma":200,"cur_vol_break":2.5,
      "cur_conds":[True]*10}
for k,v in _D.items():
    if k not in st.session_state: st.session_state[k] = v

strat_keys = list(st.session_state["saved_strategies"].keys())
if "active_strategy_name" not in st.session_state or \
   st.session_state.active_strategy_name not in st.session_state["saved_strategies"]:
    st.session_state.active_strategy_name = strat_keys[0] if strat_keys else "기본 전략"

if strat_keys and st.session_state.active_strategy_name in st.session_state["saved_strategies"]:
    sd = st.session_state["saved_strategies"][st.session_state.active_strategy_name]
    for _k,_f,_d in [("cur_short_ma","short_ma",20),("cur_mid_ma","mid_ma",50),
                      ("cur_long_ma","long_ma",200),("cur_vol_break","vol_breakout",2.5)]:
        st.session_state[_k] = (int if _k!="cur_vol_break" else float)(sd.get(_f,_d))
    st.session_state["cur_conds"]      = sd.get("active_conds",[True]*10)
    st.session_state["target_tp_pct"]  = float(sd.get("target_tp_pct",5.0))
    st.session_state["target_sl_pct"]  = float(sd.get("target_sl_pct",2.0))

# ==========================================
# 4. 사이드바
# ==========================================
kt = st.session_state["input_key_trigger"]
sb  = st.sidebar

# 앱 타이틀
sb.markdown("<div style='padding:16px 4px 8px 4px;'>"
            "<span style='font-size:18px; font-weight:700; color:#f5f5f7; letter-spacing:-0.3px;'>📈 AlgoTrader</span>"
            "<br><span style='font-size:11px; color:#8e8e93;'>전설적 트레이더 조건 스크리너</span></div>",
            unsafe_allow_html=True)
sb.markdown("<hr style='border-color:#3a3a3c;margin:0 0 12px 0;'>", unsafe_allow_html=True)

# 모드 선택
mode_options = ["🎯 단일 종목", "🔍 조건 스캐너"]
try: mode_idx = mode_options.index(st.session_state["mode_buffer"])
except: mode_idx = 0
app_mode = sb.radio("모드", mode_options, index=mode_idx, key=f"m_{kt}")
st.session_state["mode_buffer"] = app_mode

sb.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)

# 티커 입력
raw_in = sb.text_input("종목명 / 티커", value=st.session_state["ticker_buffer"],
                        placeholder="예: IONQ, Tesla, 삼성전자", key=f"t_{kt}").strip()
st.session_state["ticker_buffer"] = raw_in
ticker = INV_STOCK_MAP.get(raw_in.lower(), raw_in.upper()) if raw_in else ""

# 스캐너 시간대 (스캐너 모드만)
if "스캐너" in app_mode:
    scanner_interval = sb.selectbox("스캐너 시간대", INTERVALS, key=f"si_{kt}")
else:
    scanner_interval = "1d"

sb.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
sb.markdown("<span style='font-size:11px; font-weight:600; color:#8e8e93; text-transform:uppercase; letter-spacing:0.5px;'>포지션 설정</span>", unsafe_allow_html=True)

pos_options = ["LONG (매수)", "SHORT (공매도)"]
try: pos_idx = pos_options.index(st.session_state["position_buffer"])
except: pos_idx = 0
position_side = sb.radio("방향", pos_options, index=pos_idx, key=f"p_{kt}")
st.session_state["position_buffer"] = position_side

current_entry = sb.number_input("진입 평단가", value=float(st.session_state["selected_entry_price"]),
                                  step=0.01, key=f"e_{kt}")
st.session_state["selected_entry_price"] = current_entry

target_tp_pct = sb.number_input("익절 비율 (%)", value=float(st.session_state["target_tp_pct"]),
                                  step=0.1, key=f"tp_{kt}")
st.session_state["target_tp_pct"] = target_tp_pct

target_sl_pct = sb.number_input("손절 비율 (%)", value=float(st.session_state["target_sl_pct"]),
                                  step=0.1, key=f"sl_{kt}")
st.session_state["target_sl_pct"] = target_sl_pct

curr_sign = "₩" if (".KS" in ticker or ".KQ" in ticker) else "$"
if current_entry > 0:
    side_tp = current_entry*(1+(target_tp_pct/100)) if "LONG" in position_side else current_entry*(1-(target_tp_pct/100))
    side_sl = current_entry*(1-(target_sl_pct/100)) if "LONG" in position_side else current_entry*(1+(target_sl_pct/100))
    sb.markdown(
        f"<div style='display:flex;gap:6px;margin-top:4px;'>"
        f"<div style='flex:1;background:#1a3a2a;border:1px solid #1c6b3a;border-radius:10px;padding:8px 10px;text-align:center;'>"
        f"<div style='font-size:9px;color:#30d158;font-weight:600;'>익절선</div>"
        f"<div style='font-size:13px;color:#30d158;font-weight:700;'>{curr_sign}{side_tp:,.2f}</div></div>"
        f"<div style='flex:1;background:#3a1a1a;border:1px solid #9b1c1c;border-radius:10px;padding:8px 10px;text-align:center;'>"
        f"<div style='font-size:9px;color:#ff453a;font-weight:600;'>손절선</div>"
        f"<div style='font-size:13px;color:#ff453a;font-weight:700;'>{curr_sign}{side_sl:,.2f}</div></div>"
        f"</div>", unsafe_allow_html=True)

# ── 전략 보관함 ──────────────────────────────────────────────────────────
sb.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
sb.markdown("<span style='font-size:11px; font-weight:600; color:#8e8e93; text-transform:uppercase; letter-spacing:0.5px;'>전략 보관함</span>", unsafe_allow_html=True)
strat_keys = list(st.session_state["saved_strategies"].keys())
if strat_keys:
    for si, key in enumerate(strat_keys):
        is_active = (key == st.session_state.active_strategy_name)
        c1, c2 = sb.columns([5, 1])
        lbl = f"✦ {key}" if is_active else f"  {key}"
        with c1:
            if st.button(lbl, key=f"load_{si}", use_container_width=True):
                st.session_state["active_strategy_name"] = key
                tsd = st.session_state["saved_strategies"][key]
                for _k,_f,_d in [("cur_short_ma","short_ma",20),("cur_mid_ma","mid_ma",50),
                                   ("cur_long_ma","long_ma",200),("cur_vol_break","vol_breakout",2.5)]:
                    st.session_state[_k] = (int if _k!="cur_vol_break" else float)(tsd.get(_f,_d))
                st.session_state["cur_conds"]     = tsd.get("active_conds",[True]*10)
                st.session_state["ticker_buffer"] = tsd.get("ticker","IONQ")
                st.session_state["position_buffer"] = tsd.get("position_side","LONG (매수)")
                st.session_state["selected_entry_price"] = float(tsd.get("entry_price",0.0))
                st.session_state["target_tp_pct"] = float(tsd.get("target_tp_pct",5.0))
                st.session_state["target_sl_pct"] = float(tsd.get("target_sl_pct",2.0))
                st.session_state["input_key_trigger"] += 1
                st.rerun()
        with c2:
            if st.button("✕", key=f"del_{si}", use_container_width=True):
                del st.session_state["saved_strategies"][key]
                save_permanently()
                rk = list(st.session_state["saved_strategies"].keys())
                st.session_state.active_strategy_name = rk[0] if rk else "기본 전략"
                st.session_state["input_key_trigger"] += 1
                st.rerun()
else:
    sb.caption("저장된 전략이 없습니다.")

# ── 조건 컨트롤러 (expander) ─────────────────────────────────────────────
sb.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
dk = f"{st.session_state.active_strategy_name}_{kt}"

short_ma  = st.session_state["cur_short_ma"]
mid_ma    = st.session_state["cur_mid_ma"]
long_ma   = st.session_state["cur_long_ma"]
vol_break = st.session_state["cur_vol_break"]
active_conditions = list(st.session_state["cur_conds"])

COND_LABELS_LONG = [
    "① [오닐/존스] 시장 지수 > MA20 (상승장)",
    "② [미너비니] 주가 > MA50 > MA150 > MA200",
    "③ [미너비니] 52주 저가+25% & 고가-25% 이내",
    "④ [미너비니/오닐] 최근 변동폭 축소 (힘의 응축)",
    "⑤ [다바스/덴니스] 20일 최고가 상향 돌파",
    "⑥ [다바스/오닐] 거래량 ≥ 평균 × 2.5배",
    "⑦ [덴니스] ADX ≥ 20 & +DI > -DI",
    "⑧ [코브너] 2×ATR(14) 손절선 산출",
    "⑨ [미너비니/소로스] 수익비 ≥ 2:1",
    "⑩ [세이코타] 종가 > MA20 (추세 유지)",
]
COND_LABELS_SHORT = [
    "① [오닐/존스] 시장 지수 < MA20 (하락장)",
    "② [미너비니] 주가 < MA50 < MA150 < MA200",
    "③ [미너비니] 52주 고가-25% & 저가+25% 이내",
    "④ [미너비니/오닐] 최근 변동폭 축소 후 하락",
    "⑤ [다바스/덴니스] 20일 최저가 하향 이탈",
    "⑥ [다바스/오닐] 거래량 ≥ 평균 × 2.5배",
    "⑦ [덴니스] ADX ≥ 20 & -DI > +DI",
    "⑧ [코브너] 2×ATR(14) 손절선 산출",
    "⑨ [미너비니/소로스] 수익비 ≥ 2:1",
    "⑩ [세이코타] 종가 < MA20 (추세 유지)",
]
COND_LABELS = COND_LABELS_LONG if "LONG" in position_side else COND_LABELS_SHORT

with sb.expander(f"⚙️ 조건 설정 — {st.session_state.active_strategy_name}", expanded=False):
    short_ma  = st.number_input("단기 MA", value=st.session_state["cur_short_ma"], key=f"sma_{dk}")
    mid_ma    = st.number_input("중기 MA", value=st.session_state["cur_mid_ma"],   key=f"mma_{dk}")
    long_ma   = st.number_input("장기 MA", value=st.session_state["cur_long_ma"],  key=f"lma_{dk}")
    vol_break = st.number_input("거래량 배수", value=st.session_state["cur_vol_break"], step=0.1, key=f"vbk_{dk}")
    st.markdown("---")
    active_conditions = []
    c_defaults = st.session_state["cur_conds"]
    for i in range(10):
        v = st.checkbox(COND_LABELS[i], value=c_defaults[i] if i < len(c_defaults) else True, key=f"cb_{i}_{dk}")
        active_conditions.append(v)

max_possible_score = sum(active_conditions)

# 저장
sb.markdown("<hr style='border-color:#3a3a3c;'>", unsafe_allow_html=True)
new_name = sb.text_input("전략 이름", value="" if st.session_state.active_strategy_name=="기본 전략"
                           else st.session_state.active_strategy_name,
                           placeholder="이름 입력 후 저장", key=f"sname_{dk}")
if sb.button("💾  저장 / 수정", use_container_width=True, key=f"save_{dk}"):
    sk = new_name.strip() or "나의 전략"
    st.session_state["saved_strategies"][sk] = {
        "ticker": st.session_state["ticker_buffer"], "position_side": position_side,
        "entry_price": current_entry, "target_tp_pct": target_tp_pct, "target_sl_pct": target_sl_pct,
        "short_ma": short_ma, "mid_ma": mid_ma, "long_ma": long_ma, "vol_breakout": vol_break,
        "active_conds": active_conditions
    }
    save_permanently()
    st.session_state.active_strategy_name = sk
    for _k,_v in [("cur_short_ma",short_ma),("cur_mid_ma",mid_ma),("cur_long_ma",long_ma),
                   ("cur_vol_break",vol_break),("cur_conds",active_conditions),
                   ("target_tp_pct",target_tp_pct),("target_sl_pct",target_sl_pct)]:
        st.session_state[_k] = _v
    st.session_state["input_key_trigger"] += 1
    st.rerun()

# ==========================================
# 5. 분석 엔진
# ==========================================
def analyse(symbol, interval, forced_position=None):
    if not symbol: return None
    symbol = symbol.upper().strip()
    period_str = "60d" if interval in ["1m","2m","5m","15m","30m"] else ("730d" if interval=="1h" else "2y")
    _pos = forced_position or position_side
    try:
        df = yf.Ticker(symbol).history(period=period_str, interval=interval,
                                        prepost=interval in ["15m","30m","1h"])
        if df.empty or len(df) < 60: return None
        df = df.sort_index().ffill().bfill()
        cl, hi, lo, vo = df['Close'], df['High'], df['Low'], df['Volume']

        ma20  = cl.rolling(20).mean()
        ma50  = cl.rolling(50).mean()
        ma150 = cl.rolling(min(150,len(df))).mean()
        ma200 = cl.rolling(min(200,len(df))).mean()

        lb52      = min(252,len(df))
        high_52   = hi.rolling(lb52).max().iloc[-1]
        low_52    = lo.rolling(lb52).min().iloc[-1]
        rec_rng   = hi.iloc[-20:].max()-lo.iloc[-20:].min() if len(df)>=20 else 0
        pri_rng   = hi.iloc[-50:-20].max()-lo.iloc[-50:-20].min() if len(df)>=50 else rec_rng+1
        brk_hi    = hi.iloc[-21:-1].max() if len(df)>21 else hi.iloc[:-1].max()
        brk_lo    = lo.iloc[-21:-1].min() if len(df)>21 else lo.iloc[:-1].min()
        vol_avg20 = vo.rolling(20).mean().iloc[-1]

        hi_d, lo_d = hi.diff(), lo.diff()
        pdm = np.where((hi_d>lo_d)&(hi_d>0), hi_d, 0.0)
        mdm = np.where((lo_d>hi_d)&(lo_d>0), lo_d, 0.0)
        tr  = pd.concat([hi-lo, abs(hi-cl.shift(1)), abs(lo-cl.shift(1))], axis=1).max(axis=1)
        atr14    = tr.rolling(14).mean()
        plus_di  = 100*(pd.Series(pdm,index=df.index).rolling(14).mean()/(atr14+1e-9))
        minus_di = 100*(pd.Series(mdm,index=df.index).rolling(14).mean()/(atr14+1e-9))
        adx      = ((abs(plus_di-minus_di)/(plus_di+minus_di+1e-9))*100).rolling(14).mean()

        atr_v  = atr14.iloc[-1]
        pdi_v  = plus_di.iloc[-1]
        mdi_v  = minus_di.iloc[-1]
        adx_v  = adx.iloc[-1]

        try:
            isym   = "^KS11" if (".KS" in symbol or ".KQ" in symbol) else "SPY"
            idx_df = yf.Ticker(isym).history(period="60d",interval="1d").sort_index().ffill().bfill()
            il, im = idx_df['Close'].iloc[-1], idx_df['Close'].rolling(20).mean().iloc[-1]
        except: il, im = 1.0, 0.9

        cp    = cl.iloc[-1]
        m20v  = ma20.iloc[-1]; m50v = ma50.iloc[-1]
        m150v = ma150.iloc[-1]; m200v = ma200.iloc[-1]
        sl_p  = (cp-2*atr_v) if "LONG" in _pos else (cp+2*atr_v)
        tp_p  = (brk_hi+3*atr_v) if "LONG" in _pos else (brk_lo-3*atr_v)
        rr_ok = abs(tp_p-cp) >= 2*abs(cp-sl_p)

        if "LONG" in _pos:
            cr = [bool(il>im), bool(cp>m50v>m150v>m200v),
                  bool(cp>=low_52*1.25 and cp>=high_52*0.75),
                  bool(rec_rng<pri_rng), bool(cp>brk_hi),
                  bool(vo.iloc[-1]>=vol_avg20*2.5),
                  bool(adx_v>=20 and pdi_v>mdi_v),
                  bool(atr_v>0), bool(rr_ok), bool(cp>m20v)]
        else:
            cr = [bool(il<im), bool(cp<m50v<m150v<m200v),
                  bool(cp<=high_52*0.75 and cp<=low_52*1.25),
                  bool(rec_rng<pri_rng), bool(cp<brk_lo),
                  bool(vo.iloc[-1]>=vol_avg20*2.5),
                  bool(adx_v>=20 and mdi_v>pdi_v),
                  bool(atr_v>0), bool(rr_ok), bool(cp<m20v)]

        score = sum(1 for i,a in enumerate(active_conditions) if a and cr[i])
        fg,bg,lbl = signal_style(score, max_possible_score)
        if max_possible_score>0:
            status = f"{lbl} ({score}/{max_possible_score})"
        else:
            status = "— 조건 없음"

        curr_sym = "₩" if (".KS" in symbol or ".KQ" in symbol) else "$"
        return {"score":score,"status":status,"price":cp,"currency":curr_sym,
                "c_results":cr,"atr":atr_v,"sl":sl_p,"tp":tp_p,"fg":fg,"bg":bg}
    except: return None

# ==========================================
# 6. 메인 — 단일 종목
# ==========================================
if "단일" in app_mode:
    # 페이지 타이틀
    name_disp = STOCK_MAP.get(ticker, ticker)
    st.markdown(
        f"<div style='margin-bottom:20px;'>"
        f"<h2 style='font-size:22px;font-weight:700;color:#1c1c1e;margin:0;letter-spacing:-0.5px;'>"
        f"{name_disp}</h2>"
        f"<span style='font-size:13px;color:#8e8e93;font-weight:500;'>{ticker}</span>"
        f"</div>" if ticker else
        "<div style='margin-bottom:20px;'><h2 style='font-size:22px;font-weight:700;color:#1c1c1e;'>종목을 입력하세요</h2></div>",
        unsafe_allow_html=True)

    if not ticker:
        st.info("← 왼쪽 사이드바에서 종목 티커를 입력하세요 (예: IONQ, TSLA, 삼성전자)")
        st.stop()

    # 8개 조합 병렬 로드
    combos = [(iv, pos) for iv in INTERVALS for pos in ["LONG (매수)","SHORT (공매도)"]]
    with st.spinner(""):
        mtf = {}
        def _fetch(args):
            iv, ps = args
            return (iv, ps), analyse(ticker, iv, forced_position=ps)
        with ThreadPoolExecutor(max_workers=8) as ex:
            for k2, r in ex.map(_fetch, combos): mtf[k2] = r

    res_ref = mtf.get(("1d","LONG (매수)")) or mtf.get(("1d","SHORT (공매도)"))
    if not res_ref:
        st.error("데이터를 가져올 수 없습니다. 티커를 확인하거나 잠시 후 다시 시도하세요.")
        st.stop()

    cp   = res_ref["price"]
    curr = res_ref["currency"]

    # ── 시간대별 점수 테이블 ────────────────────────────────────────────
    st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;"
                "letter-spacing:0.5px;margin-bottom:8px;'>시간대별 LONG / SHORT 스코어</p>",
                unsafe_allow_html=True)

    # 헤더
    hc0, hc1, hc2 = st.columns([1,5,5])
    hc1.markdown("<div style='background:#e8f0fe;border-radius:8px;padding:5px 12px;text-align:center;"
                 "font-size:12px;font-weight:600;color:#1a56db;'>📈 LONG (매수)</div>",
                 unsafe_allow_html=True)
    hc2.markdown("<div style='background:#fde8e8;border-radius:8px;padding:5px 12px;text-align:center;"
                 "font-size:12px;font-weight:600;color:#9b1c1c;'>📉 SHORT (공매도)</div>",
                 unsafe_allow_html=True)

    for iv in INTERVALS:
        rc0, rc1, rc2 = st.columns([1,5,5])
        rl = mtf.get((iv,"LONG (매수)"))
        rs = mtf.get((iv,"SHORT (공매도)"))

        rc0.markdown(
            f"<div style='display:flex;align-items:center;justify-content:center;min-height:38px;'>"
            f"<span style='font-size:12px;font-weight:700;color:#1c1c1e;background:#f2f2f7;"
            f"padding:4px 10px;border-radius:8px;border:1px solid #e5e5ea;'>{iv}</span></div>",
            unsafe_allow_html=True)

        for col, res, side_c in [(rc1,rl,"#1a56db"),(rc2,rs,"#9b1c1c")]:
            if res:
                fg,bg,lbl = signal_style(res["score"], max_possible_score)
                side_lbl = "📈 LONG" if col==rc1 else "📉 SHORT"
                col.markdown(
                    f"<div style='background:{bg};border:1px solid {fg}30;border-radius:10px;"
                    f"padding:7px 14px;display:flex;align-items:center;gap:10px;'>"
                    f"<span style='font-size:11px;font-weight:600;color:{side_c};'>{side_lbl}</span>"
                    f"<span style='font-size:14px;font-weight:800;color:{fg};'>{res['score']}/{max_possible_score}</span>"
                    f"<span style='font-size:11px;font-weight:600;color:{fg};'>{lbl}</span>"
                    f"</div>", unsafe_allow_html=True)
            else:
                col.markdown("<div style='color:#c7c7cc;font-size:12px;padding:7px 14px;'>데이터 없음</div>",
                             unsafe_allow_html=True)

    # ── 모니터링 카드 ───────────────────────────────────────────────────
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;"
                "letter-spacing:0.5px;margin-bottom:8px;'>실시간 모니터링</p>", unsafe_allow_html=True)

    if current_entry > 0:
        if "LONG" in position_side:
            profit = ((cp-current_entry)/current_entry)*100
            ctp = current_entry*(1+target_tp_pct/100)
            csl = current_entry*(1-target_sl_pct/100)
        else:
            profit = ((current_entry-cp)/current_entry)*100
            ctp = current_entry*(1-target_tp_pct/100)
            csl = current_entry*(1+target_sl_pct/100)
    else:
        profit=ctp=csl=0.0

    pfg = "#1c6b3a" if profit>=0 else "#9b1c1c"
    pbg = "#d1f5e0" if profit>=0 else "#fde8e8"

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("🔥 현재가",  f"{curr}{cp:,.2f}")
    m2.metric("📊 수익률",  f"{profit:+.2f}%" if current_entry>0 else "—")
    m3.metric(f"🎯 익절 {target_tp_pct}%", f"{curr}{ctp:,.2f}" if current_entry>0 else "—")
    m4.metric(f"🚨 손절 {target_sl_pct}%", f"{curr}{csl:,.2f}" if current_entry>0 else "—")

    # ── 체크리스트 ──────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    ref = mtf.get(("1d", position_side)) or res_ref
    if ref:
        st.markdown(
            f"<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;"
            f"letter-spacing:0.5px;margin-bottom:8px;'>세부 조건 체크리스트 (1D · {position_side[:5]})</p>",
            unsafe_allow_html=True)

        sc1, sc2 = st.columns([1,3])
        fg,bg,lbl = signal_style(ref["score"], max_possible_score)
        with sc1:
            st.markdown(card(
                f"<div style='font-size:11px;color:#8e8e93;font-weight:500;'>종합 스코어</div>"
                f"<div style='font-size:28px;font-weight:800;color:{fg};margin:4px 0;'>"
                f"{ref['score']}<span style='font-size:14px;color:#8e8e93;'>/{max_possible_score}</span></div>"
                f"<div>{pill(lbl, fg, bg)}</div>"
            ), radius=14)
        with sc2:
            if max_possible_score>0:
                pct = int(ref["score"]/max_possible_score*100)
                st.markdown(
                    f"<div style='background:#fff;border:1px solid #e5e5ea;border-radius:14px;"
                    f"padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.06);'>"
                    f"<div style='font-size:11px;color:#8e8e93;font-weight:500;margin-bottom:8px;'>조건 달성률</div>"
                    f"<div style='background:#f2f2f7;border-radius:99px;height:8px;overflow:hidden;'>"
                    f"<div style='background:{fg};width:{pct}%;height:8px;border-radius:99px;"
                    f"transition:width 0.5s ease;'></div></div>"
                    f"<div style='font-size:20px;font-weight:700;color:{fg};margin-top:8px;'>{pct}%</div>"
                    f"</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        cl1, cl2 = st.columns(2)
        for i,(label,active,passed) in enumerate(zip(COND_LABELS, active_conditions, ref["c_results"])):
            col = cl1 if i<5 else cl2
            if active:
                if passed:
                    col.markdown(card(
                        f"<span style='font-size:13px;'>✅</span> "
                        f"<span style='font-size:12px;font-weight:500;color:#1c6b3a;'>{label}</span>",
                        bg="#f0fdf4", border="#bbf7d0"), unsafe_allow_html=True)
                else:
                    col.markdown(card(
                        f"<span style='font-size:13px;'>❌</span> "
                        f"<span style='font-size:12px;font-weight:500;color:#9b1c1c;'>{label}</span>",
                        bg="#fff5f5", border="#fecaca"), unsafe_allow_html=True)
            else:
                col.markdown(card(
                    f"<span style='font-size:13px;'>⬜</span> "
                    f"<span style='font-size:12px;color:#c7c7cc;'>{label}</span>",
                    bg="#fafafa", border="#e5e5ea"), unsafe_allow_html=True)

        # ATR 요약
        atr_v, sl_v, tp_v = ref.get("atr",0), ref.get("sl",0), ref.get("tp",0)
        if atr_v and atr_v>0:
            rr = abs(tp_v-cp)/(abs(cp-sl_v)+1e-9)
            st.markdown(
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;'>"
                f"<div style='background:#f2f2f7;border:1px solid #e5e5ea;border-radius:10px;"
                f"padding:8px 14px;font-size:11px;color:#3a3a3c;'>"
                f"<b>ATR(14)</b> {curr}{atr_v:,.2f}</div>"
                f"<div style='background:#fff5f5;border:1px solid #fecaca;border-radius:10px;"
                f"padding:8px 14px;font-size:11px;color:#9b1c1c;'>"
                f"<b>손절선</b> {curr}{sl_v:,.2f}</div>"
                f"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;"
                f"padding:8px 14px;font-size:11px;color:#1c6b3a;'>"
                f"<b>목표가</b> {curr}{tp_v:,.2f}</div>"
                f"<div style='background:#fffbeb;border:1px solid #fde68a;border-radius:10px;"
                f"padding:8px 14px;font-size:11px;color:#7d5a00;'>"
                f"<b>수익비</b> {rr:.1f}:1</div>"
                f"</div>", unsafe_allow_html=True)

# ==========================================
# 7. 메인 — 조건 스캐너
# ==========================================
else:
    st.markdown(
        f"<h2 style='font-size:22px;font-weight:700;color:#1c1c1e;letter-spacing:-0.5px;margin-bottom:4px;'>"
        f"조건 스캐너</h2>"
        f"<p style='font-size:13px;color:#8e8e93;margin-bottom:20px;'>{scanner_interval} 기준 · LONG / SHORT 동시 분석</p>",
        unsafe_allow_html=True)

    mc1, mc2 = st.columns(2)
    with mc1: scan_us = st.checkbox("🇺🇸 미국 우량주", value=True)
    with mc2: scan_kr = st.checkbox("🇰🇷 한국 우량주", value=False)

    scan_list = []
    if scan_us: scan_list.extend(US_SCAN_LIST)
    if scan_kr: scan_list.extend(KR_SCAN_LIST)

    if st.button("🚀  전수 스캔 시작", use_container_width=False, key="scan_btn"):
        st.session_state.pop("cached_scan", None)
        results = []
        prog = st.progress(0)
        total = len(scan_list)

        # LONG + SHORT 동시 패치
        all_combos = [(sym,"LONG (매수)") for sym in scan_list] + \
                     [(sym,"SHORT (공매도)") for sym in scan_list]

        raw = {}
        def _scan(args):
            sym, ps = args
            return (sym, ps), analyse(sym, scanner_interval, forced_position=ps)
        with ThreadPoolExecutor(max_workers=10) as ex:
            for i,(k2,r) in enumerate(ex.map(_scan, all_combos)):
                raw[k2] = r
                prog.progress(min(1.0, (i+1)/len(all_combos)))

        for sym in scan_list:
            rl = raw.get((sym,"LONG (매수)"))
            rs = raw.get((sym,"SHORT (공매도)"))
            if not rl and not rs: continue
            cp    = (rl or rs)["price"]
            curr2 = (rl or rs)["currency"]

            l_sc = rl["score"] if rl else 0
            s_sc = rs["score"] if rs else 0
            l_fg,l_bg,l_lbl = signal_style(l_sc, max_possible_score)
            s_fg,s_bg,s_lbl = signal_style(s_sc, max_possible_score)

            results.append({
                "name": STOCK_MAP.get(sym, sym),
                "price": f"{curr2}{cp:,.2f}",
                "price_raw": cp,
                "long_score_raw": l_sc,
                "short_score_raw": s_sc,
                "LONG_signal": l_lbl,
                "SHORT signal": s_lbl,
                "_sym": sym,
            })
        if results:
            st.session_state["cached_scan"] = sorted(results, key=lambda x: x["long_score_raw"]+x["short_score_raw"], reverse=True)

    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        data = st.session_state["cached_scan"]

        # 테이블 출력
        def style_sig(val):
            if "사격개시" in str(val): return "background:#d1f5e0;color:#1c6b3a;font-weight:600;"
            if "위험구역" in str(val): return "background:#fde8e8;color:#9b1c1c;font-weight:600;"
            if "관망" in str(val):    return "background:#fef9c3;color:#7d5a00;font-weight:600;"
            return ""

        df_show = pd.DataFrame([{
            "name":      d.get["name", "N/A"],
            "price":      d.get["price", "N/A"],
            "📈 LONG":     f"{d.get('long_score_raw', 0)}/{max_possible_score}",
            "LONG signal": d.get("long_signal", "관망"),
            "📉 SHORT":    f"{d.get('short_score_raw', 0)}/{max_possible_score}",
            "SHORT signal":d.get("short_signal", "관망"),
        } for d in data])

        def style_sig(val):
            val_str = str(val).replace(" ", "") # 공백을 강제로 제거하여 "사격 개시", "사격개시" 둘 다 잡음
            if "사격개시" in val_str: return "background:#d1f5e0;color:#1c6b3a;font-weight:600;"
            if "위험구역" in val_str: return "background:#fde8e8;color:#9b1c1c;font-weight:600;"
            if "관망" in val_str:     return "background:#fef9c3;color:#7d5a00;font-weight:600;"
            return "
            
        styled = df_show.style.map(style_sig, subset=["LONG signal","SHORT signal"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Top 10 카드 그리드
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:11px;font-weight:600;color:#8e8e93;text-transform:uppercase;"
                    "letter-spacing:0.5px;margin-bottom:12px;'>Top 10 — LONG+SHORT 합산 고득점</p>",
                    unsafe_allow_html=True)

        top10 = sorted(data, key=lambda x: x["long_score_raw"]+x["short_score_raw"], reverse=True)[:10]
        for row_start in range(0,len(top10),5):
            cols = st.columns(5)
            for ci, item in enumerate(top10[row_start:row_start+5]):
                sym   = item["_sym"]
                l_fg,l_bg,l_lbl = signal_style(item["long_score_raw"],  max_possible_score)
                s_fg,s_bg,s_lbl = signal_style(item["short_score_raw"], max_possible_score)
                with cols[ci]:
                    st.markdown(
                        f"<div style='background:#fff;border:1px solid #e5e5ea;border-radius:14px;"
                        f"padding:14px 12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.05);margin-bottom:8px;'>"
                        f"<div style='font-size:13px;font-weight:700;color:#1c1c1e;margin-bottom:2px;"
                        f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{item['종목명']}</div>"
                        f"<div style='font-size:16px;font-weight:800;color:#1c1c1e;margin:6px 0;'>{item['현재가']}</div>"
                        f"<div style='display:flex;gap:4px;justify-content:center;flex-wrap:wrap;'>"
                        f"<div style='background:{l_bg};border-radius:8px;padding:4px 8px;'>"
                        f"<div style='font-size:9px;color:{l_fg};font-weight:600;'>📈 LONG</div>"
                        f"<div style='font-size:13px;font-weight:800;color:{l_fg};'>{item['long_score_raw']}/{max_possible_score}</div>"
                        f"</div>"
                        f"<div style='background:{s_bg};border-radius:8px;padding:4px 8px;'>"
                        f"<div style='font-size:9px;color:{s_fg};font-weight:600;'>📉 SHORT</div>"
                        f"<div style='font-size:13px;font-weight:800;color:{s_fg};'>{item['short_score_raw']}/{max_possible_score}</div>"
                        f"</div></div></div>", unsafe_allow_html=True)
                    if st.button(f"분석", key=f"go_{sym}_{row_start}_{ci}", use_container_width=True):
                        st.session_state["ticker_buffer"] = sym
                        st.session_state["mode_buffer"]   = "🎯 단일 종목"
                        st.session_state["input_key_trigger"] += 1
                        st.rerun()
