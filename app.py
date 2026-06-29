import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 0. 전역 설정 및 더미 데이터 (시스템 환경에 맞게 변경 가능)
# ==========================================
COND_LABELS = [
    "RSI 과매도 구간 여부", "Bollinger Bands 하단 터치", "이동평균선 정배열", 
    "MACD 골든크로스", "거래량 급증", "지지선 근접", 
    "기관 수급 유입", "외인 수급 유입", "단기 모멘텀 턴어라운드", "추세 강도(ADX) 충족"
]
max_possible_score = 10

# 과부하 및 오류 방지를 위한 상위 우량주 선별 리스트 (예시)
US_SCAN_LIST = ["IONQ", "TSLA", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"]
KR_SCAN_LIST = ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "051910.KS"]

STOCK_MAP = {
    "IONQ": "아이온큐", "TSLA": "테슬라", "AAPL": "애플", "MSFT": "마이크로소프트", 
    "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "구글", "META": "메타",
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "035420.KS": "네이버", 
    "035720.KS": "카카오", "051910.KS": "LG화학"
}

# Session State 초기화 예외 처리
if "input_key_trigger" not in st.session_state:
    st.session_state["input_key_trigger"] = 0
if "mode_buffer" not in st.session_state:
    st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
if "ticker_buffer" not in st.session_state:
    st.session_state["ticker_buffer"] = ""

# ==========================================
# 1. 가상의 야후 파이낸스 분석 함수 (오류 대응 완화 로직 포함)
# ==========================================
def get_yahoo_custom_analysis(symbol, interval):
    """
    네트워크 불안정 또는 티커 오류 발생 시 프로그램이 멈추지 않도록 예외 처리(try-except)를 강화했습니다.
    """
    try:
        # 실제 환경에서는 yf.Ticker(symbol).history(...) 등을 활용하여 지표 연산 수행
        # 여기서는 연동 테스트를 위한 안정적인 데모 데이터를 반환합니다.
        import random
        scores = random.randint(1, 10)
        status = "사격 개시" if scores >= 7 else ("관망" if scores >= 4 else "위험구역")
        currency = "$" if not symbol.endswith(".KS") else "₩"
        base_price = 200.0 if not symbol.endswith(".KS") else 75000.0
        
        return {
            "current_price": round(base_price * random.uniform(0.9, 1.1), 2),
            "currency": currency,
            "score": scores,
            "status_text": f"🎯 {status} ({scores}개 조건 충족)"
        }
    except Exception as e:
        # 특정 종목 조회 실패 시 에러를 뿜지 않고 None을 반환하여 스캐너 전체가 멈추는 현상 방지
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
st.title("📊 Algorithmic Trading Dashboard")

# ------------------------------------------
# 모드 1: 단일 종목 집중 감시 룸
# ------------------------------------------
if app_mode == "🎯 단일 종목 검색":
    st.markdown("### 🎯 단일 종목 집중 감시 대시보드")
    
    # 리다이렉트 버퍼가 있으면 해당 티커를 기본값으로 사용
    default_ticker = st.session_state["ticker_buffer"]
    ticker_input = st.text_input(
        "종목 티커 입력 (예: IONQ, TSLA, 005930.KS)", 
        value=default_ticker,
        key=f"ticker_input_inside_{st.session_state['input_key_trigger']}"
    )

    if ticker_input:
        st.markdown(f"#### 🔍 {ticker_input.upper()} 분석 결과")
        
        # 임의의 단일 종목 분석 결과 및 체크리스트 예시 플래그
        active_conditions = [True, True, True, False, True, False, False, True, True, False]
        ref_res = {"c_results": [True, False, True, False, True, False, False, True, False, False]}
        
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
        st.warning("⚠️ 왼쪽 제어 콘솔에서 종목 티커(예: IONQ, TSLA)를 입력하거나 보관함에서 불러올 전략을 클릭해 주세요.")

# ------------------------------------------
# 모드 2: 주요 종목 마스터 스캐너 룸 (오류 방지 및 그리드 완성)
# ------------------------------------------
else:
    st.markdown(f"### 🔍 한/미 주요 종목 마스터 스캐너 ({scanner_interval} 기준)")
    
    # 검색 범위를 상위 우량주 셋으로 제한하여 오류 가능성 최소화
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
            # 버그 수정: 새로운 스캔 시작 시 이전 세션 캐시 초기화
            st.session_state.pop("cached_scan", None)

            scan_results = []
            prog_bar = st.progress(0)

            # 멀티스레딩 스캔 개시 (최대 8개 쓰레드로 속도 최적화 및 타임아웃 방지)
            def thread_scanner(sym): 
                return get_yahoo_custom_analysis(sym, scanner_interval)
                
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(thread_scanner, s) for s in scan_list]
                for idx, fut in enumerate(futures):
                    m = fut.result()
                    if m: # None으로 리턴된 에러 종목은 제외하고 안전한 데이터만 추가
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
            else:
                st.warning("⚠️ 스캔 결과가 존재하지 않거나 데이터 로드에 실패했습니다.")

    # 캐시된 데이터가 존재할 경우 테이블 및 Top 10 그리드 출력
    if "cached_scan" in st.session_state and st.session_state["cached_scan"]:
        df_display = pd.DataFrame(st.session_state["cached_scan"])
        df_view = df_display.drop(columns=["현재가_raw", "스코어_raw"], errors="ignore")

        # 셀 컬러 스타일링 함수
        def color_signal_cell(val):
            if "사격 개시" in str(val): return "background-color: #d4edda; color: #155724; font-weight: bold;"
            if "관망" in str(val): return "background-color: #fff3cd; color: #856404; font-weight: bold;"
            if "위험구역" in str(val): return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
            return "color: #333333;"

        styled_df = df_view.style.map(color_signal_cell, subset=['통합 시그널'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### ⚡ 실시간 스캔 매칭률 Top 10 고득점 정렬 리스트")
        
        # 고득점 순으로 정렬 후 상위 10개 슬라이싱
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

                        # 가독성 높은 HTML 카드 렌더링
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

                        # 분석 룸으로 즉시 이동(Redirect) 연동 버튼 구현
                        if st.button(f"📈 {item_ticker} 분석", key=f"grid_redirect_{item_ticker}_{i}_{idx}", use_container_width=True):
                            st.session_state["ticker_buffer"] = item_ticker
                            st.session_state["mode_buffer"] = "🎯 단일 종목 검색"
                            st.session_state["input_key_trigger"] += 1
                            st.rerun()
