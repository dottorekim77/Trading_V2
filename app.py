import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ==========================================
# 1. 페이지 기본 설정 및 상태 초기화 (기존 UI 100% 유지)
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

INV_STOCK_MAP = {v.lower(): k for k, v in STOCK_MAP.items()}
for k in STOCK_MAP.keys():
    INV_STOCK_MAP[k.lower()] = k

US_STOCK_LIST = [k for k in STOCK_MAP.keys() if not (k.endswith(".KS") or k.endswith(".KQ"))]
KR_STOCK_LIST = [k for k in STOCK_MAP.keys() if k.endswith(".KS") or k.endswith(".KQ")]

if "saved_strategies" not in st.session_state:
    if os.path.exists("saved_strategies.json"):
        try:
            with open("saved_strategies.json", "r", encoding="utf-8") as f:
                st.session_state["saved_strategies"] = json.load(f)
        except:
            st.session_state["saved_strategies"] = {}
    else:
        st.session_state["saved_strategies"] = {}

def save_strategies():
    with open("saved_strategies.json", "w", encoding="utf-8") as f:
        json.dump(st.session_state["saved_strategies"], f, ensure_ascii=False, indent=4)

if "ticker_buffer" not in st.session_state: st.session_state["ticker_buffer"] = "IONQ"
if "mode_buffer" not in st.session_state: st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
if "position_buffer" not in st.session_state: st.session_state["position_buffer"] = "LONG (매수)"
if "selected_entry_price" not in st.session_state: st.session_state["selected_entry_price"] = 0.0
if "target_tp_pct" not in st.session_state: st.session_state["target_tp_pct"] = 10.0
if "target_sl_pct" not in st.session_state: st.session_state["target_sl_pct"] = 5.0
if "input_key_trigger" not in st.session_state: st.session_state["input_key_trigger"] = 0
if "active_strategy_name" not in st.session_state: st.session_state["active_strategy_name"] = "임시 미지정 전략"
if "cur_conds" not in st.session_state: st.session_state["cur_conds"] = [True] * 10

kt = st.session_state["input_key_trigger"]

# ==========================================
# 2. 사이드바 제어판 (기존 UI 디자인 유지)
# ==========================================
st.sidebar.title("🎛️ 제어 콘솔")

app_mode = st.sidebar.radio("작동 모드 선택:", ["🎯 단일 종목 검색", "🔍 조건 스캐너"], 
                            index=0 if st.session_state["mode_buffer"] == "🎯 단일 종목 검색" else 1, key=f"mode_radio_{kt}")
st.session_state["mode_buffer"] = app_mode

raw_ticker_input = st.sidebar.text_input("종목명 또는 티커 검색:", value=st.session_state["ticker_buffer"], key=f"ticker_input_{kt}").strip()
st.session_state["ticker_buffer"] = raw_ticker_input

ticker = INV_STOCK_MAP.get(raw_ticker_input.lower(), raw_ticker_input.upper()) if raw_ticker_input else ""

if app_mode == "🔍 조건 스캐너":
    scanner_interval = st.sidebar.selectbox("스캐너 데이터 주기:", ["1d", "1h"], index=0, key=f"interval_select_{kt}")
else:
    scanner_interval = "1d"

position_side = st.sidebar.radio("포지션 방향 설정:", ["LONG (매수)", "SHORT (매도)"], 
                                 index=0 if st.session_state["position_buffer"] == "LONG (매수)" else 1, key=f"pos_radio_{kt}")
st.session_state["position_buffer"] = position_side

current_entry_price = st.sidebar.number_input("내 진입 평단가 (0 입력시 비활성화):", value=float(st.session_state["selected_entry_price"]), step=0.01, key=f"entry_input_{kt}")
st.session_state["selected_entry_price"] = current_entry_price

target_tp_pct = st.sidebar.number_input("목표 익절 제한폭 (%)", value=float(st.session_state["target_tp_pct"]), step=0.1, key=f"tp_input_{kt}")
st.session_state["target_tp_pct"] = target_tp_pct

target_sl_pct = st.sidebar.number_input("제한 손절 한계폭 (%)", value=float(st.session_state["target_sl_pct"]), step=0.1, key=f"sl_input_{kt}")
st.session_state["target_sl_pct"] = target_sl_pct

# ── 요청하신 새로운 10가지 조건식 라벨 반영 ──
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

st.sidebar.markdown("---")
st.sidebar.subheader("나만의 전략 보관함")
saved_keys = list(st.session_state["saved_strategies"].keys())
if saved_keys:
    for sk in saved_keys:
        col_load, col_del = st.sidebar.columns([4, 1])
        with col_load:
            if st.button(f"📂 {sk}", key=f"load_strat_{sk}", use_container_width=True):
                st.session_state["active_strategy_name"] = sk
                s_data = st.session_state["saved_strategies"][sk]
                st.session_state["cur_conds"] = s_data.get("conds", [True]*10)
                st.session_state["ticker_buffer"] = s_data.get("ticker", "")
                st.session_state["position_buffer"] = s_data.get("pos", "LONG (매수)")
                st.session_state["selected_entry_price"] = s_data.get("entry", 0.0)
                st.session_state["target_tp_pct"] = s_data.get("tp", 10.0)
                st.session_state["target_sl_pct"] = s_data.get("sl", 5.0)
                st.session_state["input_key_trigger"] += 1
                st.rerun()
        with col_del:
            if st.button("❌", key=f"del_strat_{sk}", use_container_width=True):
                del st.session_state["saved_strategies"][sk]
                save_strategies()
                if st.session_state["active_strategy_name"] == sk:
                    st.session_state["active_strategy_name"] = "임시 미지정 전략"
                st.rerun()
else:
    st.sidebar.caption("저장된 맞춤 전략이 없습니다.")

st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ 활성화 조건 커스텀 세팅", expanded=False):
    c_defaults = st.session_state["cur_conds"]
    active_conds = []
    for idx, lbl in enumerate(COND_LABELS):
        val = st.checkbox(lbl, value=c_defaults[idx] if idx < len(c_defaults) else True, key=f"chk_cond_{idx}")
        active_conds.append(val)

max_possible_score = sum(active_conds)

strat_input_val = "" if st.session_state["active_strategy_name"] == "임시 미지정 전략" else st.session_state["active_strategy_name"]
new_strategy_name = st.sidebar.text_input("새 전략 이름 입력:", value=strat_input_val, placeholder="예: 미너비니 추세추종")
if st.sidebar.button("💾 현재 설정 전략 저장/업데이트", use_container_width=True):
    s_name = new_strategy_name.strip() if new_strategy_name.strip() else f"전략 {datetime.now().strftime('%M%S')}"
    st.session_state["saved_strategies"][s_name] = {
        "conds": active_conds, "ticker": st.session_state["ticker_buffer"], "pos": position_side,
        "entry": current_entry_price, "tp": target_tp_pct, "sl": target_sl_pct
    }
    save_strategies()
    st.session_state["active_strategy_name"] = s_name
    st.session_state["cur_conds"] = active_conds
    st.session_state["input_key_trigger"] += 1
    st.rerun()

# ==========================================
# 3. 새로운 10가지 알고리즘 기반 데이터 연산 엔진
# ==========================================
def fetch_and_analyze(symbol, interval_str):
    if not symbol: return None
    symbol = symbol.upper().strip()
    period = "3y" if interval_str in ["1d", "1wk"] else "730d"

    try:
        # [1번 조건] 지수 필터링용 매핑
        if ".KS" in symbol: index_symbol = "^KS11"
        elif ".KQ" in symbol: index_symbol = "^KQ11"
        else: index_symbol = "^GSPC"
        
        idx_df = yf.Ticker(index_symbol).history(period="100d", interval=interval_str)
        if not idx_df.empty:
            idx_df['EMA20'] = idx_df['Close'].ewm(span=20, adjust=False).mean()
            market_filter = bool(idx_df['Close'].iloc[-1] > idx_df['EMA20'].iloc[-1])
        else:
            market_filter = True

        df = yf.Ticker(symbol).history(period=period, interval=interval_str)
        if df.empty or len(df) < 252: return None
        df = df.sort_index(ascending=True).ffill().bfill()

        # 기술적 지표 생성
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA150'] = df['Close'].ewm(span=150, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # 52주 고가/저가 및 20일 저항선 추출
        df['Min_52wk'] = df['Low'].rolling(window=252, min_periods=50).min()
        df['Max_52wk'] = df['High'].rolling(window=252, min_periods=50).max()
        df['Max_20v'] = df['High'].shift(1).rolling(window=20).max()
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        
        # ADX / DMI 계산
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
        
        # [4번 조건] 변동성 축소 패턴 (VCP) 연산
        recent_range = df['High'].tail(15).max() - df['Low'].tail(15).min()
        prior_range = df['High'].iloc[-45:-15].max() - df['Low'].iloc[-45:-15].min()
        vcp_pattern = bool(recent_range < prior_range)

        # [8, 9번 조건] 손절선 및 기대수익비 산출
        resistance_price = last['Max_52wk']
        stop_loss_price = last['Close'] - (2 * last['ATR'])
        reward_side = resistance_price - last['Close']
        risk_side = last['Close'] - stop_loss_price
        profit_ratio_cond = bool(reward_side >= (risk_side * 2))

        # ── 새로운 10가지 조건식 판정 로직 (LONG 기준) ──
        long_results = [
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

        # SHORT 판정 로직 (반대 포지션 헷지용 스케일링)
        short_results = [
            not market_filter,
            bool(last['Close'] < last['EMA50'] < last['EMA150'] < last['EMA200']),
            bool(last['Close'] <= last['Max_52wk'] * 0.75),
            vcp_pattern,
            bool(last['Close'] <= df['Low'].shift(1).rolling(window=20).min().iloc[-1]),
            bool(last['Volume'] >= last['Vol_MA20'] * 2.5),
            bool(last['ADX'] >= 20 and last['Minus_DI'] > last['Plus_DI']),
            bool(risk_side > 0),
            bool((last['Close'] - last['Min_52wk']) >= ((last['Close'] + 2*last['ATR']) - last['Close']) * 2),
            bool(last['Close'] < last['EMA20'])
        ]

        long_score = sum([1 for i, active in enumerate(active_conds) if active and long_results[i]])
        short_score = sum([1 for i, active in enumerate(active_conds) if active and short_results[i]])

        return {
            "df": df, "long_score": long_score, "short_score": short_score,
            "long_results": long_results, "short_results": short_results,
            "price": last['Close'], "atr": last['ATR'], "stop_line": stop_loss_price,
            "currency": "₩" if (".KS" in symbol or ".KQ" in symbol) else "$"
        }
    except Exception as e:
        return None

# ==========================================
# 4. 메인 대시보드 - 단일 종목 검색 뷰
# ==========================================
if app_mode == "🎯 단일 종목 검색":
    st.title("📈 실시간 통합 마스터 대시보드")
    if not ticker:
        st.info("💡 제어 콘솔 창에서 분석 대상 기업 명칭이나 티커를 입력해 주세요.")
        st.stop()

    with st.spinner("데이터 동기화 및 10대 마스터 스크리닝 알고리즘 연산 중..."):
        res = fetch_and_analyze(ticker, "1d")

    if res is None:
        st.error("데이터 패치 실패. 입력하신 부호나 시장 구분을 다시 검증하세요.")
        st.stop()

    disp_name = STOCK_MAP.get(ticker, ticker)
    c_price, curr = res["price"], res["currency"]

    # ── 실시간 자산 관리 상태 모니터링 (기존 구성 유지) ──
    st.markdown(f"### 🔍 {disp_name} ({ticker}) 분석 요약")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("현재가", f"{curr}{c_price:,.2f}")
    m_col2.metric("시스템 추천 손절선 (2×ATR)", f"{curr}{res['stop_line']:,.2f}")

    if current_entry_price > 0:
        profit_pct = ((c_price - current_entry_price) / current_entry_price) * 100
        proj_tp = current_entry_price * (1 + target_tp_pct/100)
        proj_sl = current_entry_price * (1 - target_sl_pct/100)
        m_col3.metric(f"목표 익절가 ({target_tp_pct}%)", f"{curr}{proj_tp:,.2f}", f"{profit_pct:+.2f}%")
        m_col4.metric(f"수동 제한 로스컷 ({target_sl_pct}%)", f"{curr}{proj_sl:,.2f}")
    else:
        m_col3.metric("목표 익절가", "평단가 미입력")
        m_col4.metric("수동 제한 로스컷", "평단가 미입력")

    # ── 스코어 가이드 바 및 체크리스트 ──
    cur_side_score = res["long_score"] if "LONG" in position_side else res["short_score"]
    cur_side_results = res["long_results"] if "LONG" in position_side else res["short_results"]
    
    match_ratio = int((cur_side_score / max_possible_score)*100) if max_possible_score > 0 else 0
    
    st.markdown("---")
    st.markdown(f"#### 📊 선택 포지션 [{position_side}] 추세 매칭 지수: **{cur_side_score} / {max_possible_score} 점** ({match_ratio}%)")
    st.progress(match_ratio / 100)

    st.markdown("<br>", unsafe_allow_html=True)
    c_left, c_right = st.columns(2)
    for i, (label, active) in enumerate(zip(COND_LABELS, active_conds)):
        target_col = c_left if i < 5 else c_right
        if active:
            if cur_side_results[i]:
                target_col.success(f"✅ {label} — **조건 충족**")
            else:
                target_col.error(f"❌ {label} — **조건 미달**")
        else:
            target_col.warning(f"⚪ {label} — **검증 비활성화**")

# ==========================================
# 5. 메인 대시보드 - 조건 스캐너 뷰 (기존 그리드뷰 유지)
# ==========================================
else:
    st.title("🔍 실시간 우량 자산 전수 검색기")
    
    sc_col1, sc_col2 = st.columns(2)
    with sc_col1: use_us = st.checkbox("🇺🇸 미국 프리미엄 우량주 포함", value=True)
    with sc_col2: use_kr = st.checkbox("🇰🇷 한국 대형 우량주 포함", value=False)

    scan_pool = []
    if use_us: scan_pool.extend(US_STOCK_LIST)
    if use_kr: scan_pool.extend(KR_STOCK_LIST)

    if st.button("🚀 스캔 매칭 매트릭스 가동", use_container_width=True):
        st.session_state.pop("scanner_cache", None)
        computed_list = []
        progress_bar = st.progress(0)

        def worker(sym):
            return sym, fetch_and_analyze(sym, scanner_interval)

        with ThreadPoolExecutor(max_workers=8) as executor:
            for idx, (sym, data) in enumerate(executor.map(worker, scan_pool)):
                if data:
                    computed_list.append({
                        "ticker": sym, "name": STOCK_MAP.get(sym, sym),
                        "price": f"{data['currency']}{data['price']:,.2f}",
                        "long_score_raw": data["long_score"], "short_score_raw": data["short_score"]
                    })
                progress_bar.progress(min(1.0, (idx + 1) / len(scan_pool)))

        if computed_list:
            st.session_state["scanner_cache"] = sorted(computed_list, key=lambda x: x["long_score_raw"], reverse=True)

    if "scanner_cache" in st.session_state:
        cache = st.session_state["scanner_cache"]
        
        df_display = pd.DataFrame([{
            "종목코드": item["ticker"], "종목명": item["name"], "현재시세": item["price"],
            "LONG 매칭 스코어": f"{item['long_score_raw']} / {max_possible_score}",
            "SHORT 매칭 스코어": f"{item['short_score_raw']} / {max_possible_score}"
        } for item in cache])
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("### 📊 실시간 트렌드 타점 스캐닝 매트릭스 (TOP 10)")
        top_10 = cache[:10]
        
        #기존 원본의 각진 5열 카드 레이아웃 구조 100% 동기화
        for r_idx in range(0, len(top_10), 5):
            cols = st.columns(5)
            for idx, item in enumerate(top_10[r_idx:r_idx+5]):
                with cols[idx]:
                    l_ratio = item['long_score_raw'] / max_possible_score if max_possible_score > 0 else 0
                    s_ratio = item['short_score_raw'] / max_possible_score if max_possible_score > 0 else 0
                    
                    l_bg = "#ebf8ff" if l_ratio >= 0.8 else "#f7fafc"
                    l_fg = "#2b6cb0" if l_ratio >= 0.8 else "#4a5568"
                    s_bg = "#fff5f5" if s_ratio >= 0.8 else "#f7fafc"
                    s_fg = "#c53030" if s_ratio >= 0.8 else "#4a5568"

                    st.markdown(f"""
                    <div style="border:1px solid #e2e8f0; background-color:#ffffff; padding:12px; margin-bottom:10px; box-shadow:0px 2px 4px rgba(0,0,0,0.04);">
                        <span style="font-weight:700; color:#1a202c; font-size:14px; display:block; text-overflow:ellipsis; white-space:nowrap; overflow:hidden;">{item['name']}</span>
                        <code style="color:#4a5568; font-size:11px; background-color:#f7fafc; padding:2px 6px; border-radius:4px;">{item['ticker']}</code>
                        <div style="font-size:18px; font-weight:800; color:#2d3748; margin:8px 0;">{item['price']}</div>
                        <div style="display:flex; gap:4px; justify-content:center; flex-wrap:wrap;">
                            <div style="background:{l_bg}; padding:4px 8px; border-radius:4px; text-align:center;">
                                <div style="font-size:9px; color:{l_fg}; font-weight:600;">📈 LONG</div>
                                <div style="font-size:13px; font-weight:800; color:{l_fg};">{item['long_score_raw']}/{max_possible_score}</div>
                            </div>
                            <div style="background:{s_bg}; padding:4px 8px; border-radius:4px; text-align:center;">
                                <div style="font-size:9px; color:{s_fg}; font-weight:600;">📉 SHORT</div>
                                <div style="font-size:13px; font-weight:800; color:{s_fg};">{item['short_score_raw']}/{max_possible_score}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"📈 {item['ticker']} 분석", key=f"btn_redirect_{item['ticker']}_{r_idx}_{idx}", use_container_width=True):
                        st.session_state["ticker_buffer"] = item['ticker']
                        st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                        st.session_state["input_key_trigger"] += 1
                        st.rerun()
