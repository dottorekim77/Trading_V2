import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 0. 전역 설정 및 검증 지표 정의
# ==========================================
COND_LABELS = [
    "RSI 과매도 구간 여부 (RSI < 35)", 
    "Bollinger Bands 하단 터치 또는 이하", 
    "이동평균선 정배열 (5일 > 20일 > 60일)", 
    "MACD 골든크로스 (MACD > Signal)", 
    "거래량 급증 (전일 대비 1.5배 이상)", 
    "단기 모멘텀 턴어라운드 (종가 > 5일평균)"
]
max_possible_score = len(COND_LABELS)

# 오류 방지를 위한 상위 우량주 선별 리스트
US_SCAN_LIST = ["IONQ", "TSLA", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"]
KR_SCAN_LIST = ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "051910.KS"]

STOCK_MAP = {
    "IONQ": "아이온큐", "TSLA": "테슬라", "AAPL": "애플", "MSFT": "마이크로소프트", 
    "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "구글", "META": "메타",
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "035420.KS": "네이버", 
    "035720.KS": "카카오", "051910.KS": "LG화학"
}

# Session State 초기화
if "input_key_trigger" not in st.session_state:
    st.session_state["input_key_trigger"] = 0
if "mode_buffer" not in st.session_state:
    st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
if "ticker_buffer" not in st.session_state:
    st.session_state["ticker_buffer"] = ""

# ==========================================
# 1. [핵심 변경] 실시간 주식 데이터 기반 조건식 연산 함수
# ==========================================
def get_yahoo_custom_analysis(symbol, interval):
    """
    Yahoo Finance 실시간 데이터를 받아와 기술적 지표 조건식을 검증합니다.
    """
    try:
        # 타임프레임 변환 매핑 (yfinance 표준 스펙 맞춤)
        yf_period = "60d" if interval in ["1D", "4H"] else "7d"
        yf_interval = "1d" if interval == "1D" else ("4h" if interval == "4H" else "1h")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=yf_period, interval=yf_interval)
        
        if df.empty or len(df) < 25:
            return None
            
        # 기본 가격 정보
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        volume = df['Volume'].iloc[-1]
        prev_volume = df['Volume'].iloc[-2]
        
        currency = "$" if not symbol.endswith(".KS") else "₩"
        
        # --- [조건식 1] RSI (14) 연산 ---
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        c1 = rsi_val < 35  # 과매도 구간 진입 조건
        
        # --- [조건식 2] Bollinger Bands (20, 2) 연산 ---
        ma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        lower_band = ma20 - (2 * std20)
        c2 = current_price <= lower_band.iloc[-1] # 하단 터치 조건
        
        # --- [조건식 3] 이동평균선 정배열 (5, 20, 60) ---
        ma5 = df['Close'].rolling(window=5).mean().iloc[-1]
        ma20_val = ma20.iloc[-1]
        # 데이터가 부족할 경우를 대비해 60일선 선언 유연화
        ma60 = df['Close'].rolling(window=min(60, len(df))).mean().iloc[-1]
        c3 = ma5 > ma20_val > ma60
        
        # --- [조건식 4] MACD (12, 26, 9) ---
        exp12 = df['Close'].ewm(span=12, adjust=False).mean()
        exp26 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal_line = macd.ewm(span=9, adjust=False).mean()
        c4 = macd.iloc[-1] > signal_line.iloc[-1] # 골든크로스/상승유지 조건
        
        # --- [조건식 5] 거래량 급증 ---
        c5 = volume >= (prev_volume * 1.5)
        
        # --- [조건식 6] 단기 모멘텀 턴어라운드 ---
        c6 = current_price > ma5

        # 조건 결과 결합
        c_results = [c1, c2, c3, c4, c5, c6]
        score = sum(c_results)
        
        # 통합 시그널 텍스트 정의
        if score >= 4:
            status_text = "🚀 사격 개시"
        elif score >= 2:
            status_text = "⏳ 관망"
        else:
            status_text = "🚨 위험구역"
            
        return {
            "current_price": current_price,
            "currency": currency,
            "score": score,
            "status_text": f"{status_text} ({score}/{max_possible_score} 충족)",
            "c_results": c_results
        }
    except Exception as e:
        return None

# ==========================================
# 2. 사이드바 및 제어 콘솔 환경 구성
# ==========================================
st.sidebar.title("🛠️ 제어 콘솔")
app_mode = st.sidebar.radio(
    "모드 선택", 
    ["🎯 단일 종목 검색", "🔍 주요 종목 마스터 스캐너"],
    index=0 if st.session_state["mode_buffer"] == "🎯 단일 종목 검색" else 1
)
scanner_interval = st.sidebar.selectbox("스캔 타임프레임", ["1D", "4H", "1H"], index=0)

# ==========================================
# 3. 메인 대시보드 렌더링 영역
# ==========================================
st.title("📊 Algorithmic Trading Dashboard v2")

# ------------------------------------------
# 모드 1: 단일 종목 집중 감시 룸
# ------------------------------------------
if app_mode == "🎯 단일 종목 검색":
    st.markdown("### 🎯 단일 종목 집중 감시 대시보드")
    
    default_ticker = st.session_state["ticker_buffer"]
    ticker_input = st.text_input(
        "종목 티커 입력 (예: IONQ, TSLA, 005930.KS)", 
        value=default_ticker,
        key=f"ticker_input_inside_{st.session_state['input_key_trigger']}"
    ).upper().strip()

    if ticker_input:
        with st.spinner(f"🔄 {ticker_input}의 실시간 기술적 지표 분석 중..."):
            res = get_yahoo_custom_analysis(ticker_input, scanner_interval)
            
        if res:
            st.markdown(f"#### 🔍 {STOCK_MAP.get(ticker_input, ticker_input)} ({ticker_input}) 분석 결과")
            st.metric(label="현재가", value=f"{res['currency']}{res['current_price']:,.2f}")
            st.subheader(f"통합 시그널: {res['status_text']}")
            
            st.markdown("##### ⚡ 세부 지표 체크리스트")
            check_cols = st.columns(2)
            for idx, (label, passed) in enumerate(zip(COND_LABELS, res["c_results"])):
                col = check_cols[0] if idx < 3 else check_cols[1]
                if passed: 
                    col.success(f"⭕ [충족] {label}")
                else:       
                    col.error(f"❌ [미달] {label}")
        else:
            st.error("❌ 데이터를 가져오지 못했습니다. 티커명이 올바른지 혹은 야후 파이낸스 네트워크 상태를 확인해 주세요.")
    else:
        st.warning("⚠️ 분석할 종목 티커를 입력해 주세요.")

# ------------------------------------------
# 모드 2: 주요 종목 마스터 스캐너 룸
# ------------------------------------------
else:
    st.markdown(f"### 🔍 한/미 주요 종목 마스터 스캐너 ({scanner_interval} 기준)")
    
    m_col1, m_col2 = st.columns(2)
    with m_col1: scan_us = st.checkbox("🇺🇸 미국 우량주 포함 (선별 리스트)", value=True)
    with m_col2: scan_kr = st.checkbox("🇰🇷 한국 우량주 포함 (선별 리스트)", value=False)

    scan_list = []
    if scan_us: scan_list.extend(US_SCAN_LIST)
    if scan_kr: scan_list.extend(KR_SCAN_LIST)

    if st.button("🚀 실시간 프리마켓 전수 조사 스캔 개시"):
        if not scan_list:
            st.error("❌ 스캔할 국가를 최소 하나 이상 선택해 주세요.")
        else:
            st.session_state.pop("cached_scan", None)
            scan_results = []
            prog_bar = st.progress(0)

            def thread_scanner(sym): 
                return get_yahoo_custom_analysis(sym, scanner_interval)
                
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

    # 캐시 출력 및 고득점 Top 10 그리드 출력
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
                                📊 스코어: <b style="color:#2b6cb0;">{item_score}</b></div>
                            <div style="background-color:{badge_color}; color:{text_color}; font-size:11px;
                                padding:4px; border-radius:5px; font-weight:bold;
                                overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{signal}</div>
                        </div>""", unsafe_allow_html=True)

                        if st.button(f"📈 {item_ticker} 분석", key=f"grid_redirect_{item_ticker}_{i}_{idx}", use_container_width=True):
                            st.session_state["ticker_buffer"] = item_ticker
                            st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                            st.session_state["input_key_trigger"] += 1
                            st.rerun()
