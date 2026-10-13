import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
import ssl

# --- PERSISTENT WATCHLIST SETUP ---
WATCHLIST_FILE = "watchlist.json"
DEFAULT_TICKERS = ["NVDA", "AMD", "NFLX", "NET", "SPOT", "APP", "CRWD", "NOW", "SPY", "QQQ"]

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return [str(t).strip().upper() for t in data]
        except Exception:
            pass
    return DEFAULT_TICKERS.copy()

def save_watchlist(tickers_list):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(tickers_list, f)
    except Exception:
        pass

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Institutional Derivatives & Options Execution Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem; font-weight: 700; }
    .stSelectbox label { font-weight: 600; }
    .stDataFrame { border: 1px solid #2e3546; border-radius: 8px; }
    .index-card {
        background-color: #1a1e29;
        border: 1px solid #2e3546;
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: CONTROLS & BENCHMARKS ---
st.sidebar.title("⚡ Market Control Engine")

# 1. Watchlist Manager
st.sidebar.subheader("Watchlist Manager")
add_col1, add_col2 = st.sidebar.columns([3, 1])
with add_col1:
    new_ticker = st.text_input("Add Ticker", placeholder="e.g. TSLA", label_visibility="collapsed").strip().upper()
with add_col2:
    if st.button("Add"):
        if new_ticker and new_ticker not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_ticker)
            save_watchlist(st.session_state.watchlist)
            st.rerun()

selected_remove = st.sidebar.multiselect(
    "Active Watchlist (Select to delete)",
    options=st.session_state.watchlist,
    default=[]
)
if selected_remove:
    if st.sidebar.button("Remove Selected"):
        st.session_state.watchlist = [t for t in st.session_state.watchlist if t not in selected_remove]
        save_watchlist(st.session_state.watchlist)
        st.rerun()

refresh_btn = st.sidebar.button("🔄 Pull Latest Live Market Data", use_container_width=True)

# 2. Top 5 Major Indices Panel
st.sidebar.markdown("---")
st.sidebar.subheader("Major Index Benchmarks")

@st.cache_data(ttl=60)
def fetch_top_indices():
    indices = ["SPY", "QQQ", "DIA", "IWM", "^VIX"]
    data = {}
    try:
        df = yf.download(indices, period="5d", interval="1d", progress=False, group_by="ticker")
        for sym in indices:
            sym_df = df[sym].dropna() if sym in df else pd.DataFrame()
            if not sym_df.empty and len(sym_df) >= 2:
                last_p = float(sym_df['Close'].iloc[-1])
                prev_p = float(sym_df['Close'].iloc[-2])
                pct_chg = ((last_p - prev_p) / prev_p) * 100
                
                if sym == "^VIX":
                    if last_p < 16.0 or pct_chg < -3.0:
                        bias = "Bullish Regime"
                        color = "#00c853"
                    elif last_p > 20.0 or pct_chg > 5.0:
                        bias = "Bearish Vol Spike"
                        color = "#ff3b30"
                    else:
                        bias = "Neutral Tape"
                        color = "#ffcc00"
                else:
                    if pct_chg > 0.2:
                        bias = "Bullish"
                        color = "#00c853"
                    elif pct_chg < -0.2:
                        bias = "Bearish"
                        color = "#ff3b30"
                    else:
                        bias = "Neutral"
                        color = "#ffcc00"
                        
                data[sym] = {
                    "price": last_p,
                    "chg": pct_chg,
                    "bias": bias,
                    "color": color
                }
    except Exception:
        pass
    return data

index_metrics = fetch_top_indices()

for sym in ["SPY", "QQQ", "DIA", "IWM", "^VIX"]:
    if sym in index_metrics:
        m = index_metrics[sym]
        st.sidebar.markdown(f"""
        <div class="index-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; font-size: 0.95rem;">{sym}</span>
                <span style="color: {m['color']}; font-weight: 600; font-size: 0.85rem;">{m['bias']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                <span style="font-size: 1.05rem; font-weight: 600;">${m['price']:.2f}</span>
                <span style="color: {'#00c853' if m['chg'] >= 0 else '#ff3b30'}; font-weight: 600; font-size: 0.9rem;">
                    {'+' if m['chg'] >= 0 else ''}{m['chg']:.2f}%
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.text(f"{sym}: Data Loading...")

# --- MACRO RADAR & QUANTITATIVE BAROMETERS ---
@st.cache_data(ttl=300)
def fetch_macro_catalysts():
    barometers = {}
    try:
        b_df = yf.download(["^TNX", "CL=F", "DX-Y.NYB"], period="5d", interval="1d", progress=False, group_by="ticker")
        for sym, name in [("^TNX", "10Y Treasury Yield"), ("CL=F", "WTI Crude Oil"), ("DX-Y.NYB", "US Dollar (DXY)")]:
            s_df = b_df[sym].dropna() if sym in b_df else pd.DataFrame()
            if not s_df.empty and len(s_df) >= 2:
                last_p = float(s_df['Close'].iloc[-1])
                prev_p = float(s_df['Close'].iloc[-2])
                chg = ((last_p - prev_p) / prev_p) * 100
                barometers[name] = (last_p, chg)
    except Exception:
        pass
    return barometers

# --- UNIVERSAL PER-COLUMN DATAFRAME FILTER ---
def filter_dataframe(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    modify = st.checkbox("🔍 Enable Column-by-Column Filters", key=f"{key_prefix}_toggle")
    if not modify:
        return df

    filtered_df = df.copy()
    with st.expander("Active Column Filter Controls", expanded=True):
        cols_to_filter = st.multiselect("Select columns to apply conditions:", filtered_df.columns, key=f"{key_prefix}_cols")
        col_chunks = [cols_to_filter[i:i + 3] for i in range(0, len(cols_to_filter), 3)]
        for chunk in col_chunks:
            row_cols = st.columns(len(chunk))
            for i, col_name in enumerate(chunk):
                with row_cols[i]:
                    cat_cols = ["Ticker", "Stock", "Strategy", "Quarterly Directional Bias", "Daily Directional Bias", "Market Profile / TPO Structure", "Auction Dynamics", "Stock Prediction", "M/E"]
                    if col_name in cat_cols:
                        options = sorted(list(filtered_df[col_name].dropna().unique()))
                        selected = st.multiselect(f"Filter {col_name}", options, default=options, key=f"{key_prefix}_{col_name}")
                        filtered_df = filtered_df[filtered_df[col_name].isin(selected)]
                    else:
                        val = st.text_input(f"Filter {col_name} (contains)", key=f"{key_prefix}_{col_name}")
                        if val:
                            filtered_df = filtered_df[filtered_df[col_name].astype(str).str.contains(val, case=False, na=False)]
    return filtered_df

# --- DATA ENGINE: INSTITUTIONAL TECHNICAL PROFILE ---
@st.cache_data(ttl=300)
def fetch_institutional_profile(symbol):
    try:
        tk = yf.Ticker(symbol)
        hist_daily = tk.history(period="1y")
        if hist_daily.empty or len(hist_daily) < 50:
            return None
            
        hist_hourly = tk.history(period="5d", interval="60m")
        info = tk.info or {}
        
        spot = hist_daily['Close'].iloc[-1]
        prior_close = hist_daily['Close'].iloc[-2]
        pre_market = info.get("preMarketPrice") or info.get("regularMarketPrice") or spot
        asset_name = info.get("shortName") or info.get("longName") or symbol
        
        trailing_pe = info.get("trailingPE")
        pe_str = f"{trailing_pe:.1f}x" if trailing_pe else "N/A"
        peg = info.get("pegRatio")
        peg_str = f"{peg:.2f}" if peg else "N/A"
        
        earnings_date = "N/A"
        try:
            cal = tk.calendar
            if cal is not None and "Earnings Date" in cal:
                e_dates = cal["Earnings Date"]
                if len(e_dates) > 0:
                    earnings_date = str(e_dates[0])[:10]
        except Exception:
            pass
        if earnings_date == "N/A" and "earningsTimestamp" in info and info["earningsTimestamp"]:
            earnings_date = datetime.fromtimestamp(info["earningsTimestamp"]).strftime("%Y-%m-%d")

        ema20 = hist_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        sma50 = hist_daily['Close'].rolling(window=50).mean().iloc[-1]
        sma200 = hist_daily['Close'].rolling(window=200).mean().iloc[-1] if len(hist_daily) >= 200 else np.nan
        
        if not np.isnan(sma200):
            q_bias = "Bullish" if (spot > sma50 and sma50 > sma200) else ("Bearish" if (spot < sma50 and sma50 < sma200) else "Neutral Consolidation")
        else:
            q_bias = "Bullish" if spot > sma50 else "Neutral"
            
        d_bias = "Strong Bull" if spot > ema20 * 1.015 else ("Bullish Pullback" if spot > ema20 else ("Bearish" if spot < ema20 * 0.985 else "Neutral Compression"))

        delta = hist_daily['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        ema12 = hist_daily['Close'].ewm(span=12, adjust=False).mean()
        ema26 = hist_daily['Close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        macd_val = macd_hist.iloc[-1]
        macd_str = "Bullish Expansion" if macd_val > 0 and macd_val > macd_hist.iloc[-2] else ("Bullish Diverging" if macd_val > 0 else ("Bearish Expansion" if macd_val < 0 and macd_val < macd_hist.iloc[-2] else "Bearish Weakening"))

        prior_vol = hist_daily['Volume'].iloc[-2]
        if not hist_hourly.empty:
            vpoc = hist_hourly.groupby(pd.cut(hist_hourly['Close'], bins=15))['Volume'].sum().idxmax().mid
        else:
            vpoc = hist_daily['Close'].tail(20).median()
            
        recent_20 = hist_daily.tail(20)
        daily_rng = recent_20['High'] - recent_20['Low']
        avg_rng = daily_rng.mean()
        last_rng = daily_rng.iloc[-1]
        
        if last_rng > avg_rng * 1.3:
            tpo_structure = "Trend Day (Single Prints)"
            auction_dyn = "Initiative Buying" if spot > prior_close else "Initiative Selling"
        elif abs(spot - vpoc) / spot < 0.008:
            tpo_structure = "Normal Day (Rotational POC)"
            auction_dyn = "Balanced / Two-Way Auction"
        else:
            tpo_structure = "Neutral-Extreme (Distribution)"
            auction_dyn = "Responsive Absorption"

        pivot = (recent_20['High'].max() + recent_20['Low'].min() + spot) / 3
        tr = np.maximum(
            hist_daily['High'] - hist_daily['Low'],
            np.maximum(
                abs(hist_daily['High'] - hist_daily['Close'].shift(1)),
                abs(hist_daily['Low'] - hist_daily['Close'].shift(1))
            )
        )
        atr14 = tr.rolling(window=14).mean().iloc[-1]
        
        s1 = round(spot - (atr14 * 0.75), 2)
        s2 = round(spot - (atr14 * 1.5), 2)
        s3 = round(recent_20['Low'].min(), 2)
        
        r1 = round(spot + (atr14 * 0.75), 2)
        r2 = round(spot + (atr14 * 1.5), 2)
        r3 = round(recent_20['High'].max(), 2)
        
        log_ret = np.log(hist_daily['Close'] / hist_daily['Close'].shift(1)).dropna()
        hv30 = log_ret.tail(30).std() * math.sqrt(252) * 100
        hv_rolling = log_ret.rolling(window=30).std() * math.sqrt(252) * 100
        hv_min, hv_max = hv_rolling.min(), hv_rolling.max()
        ivr = 100 * (hv30 - hv_min) / (hv_max - hv_min) if hv_max > hv_min else 25.0
        
        opt_vol = 0
        pcr = 1.0
        expected_move = round(spot * (hv30 / 100) * math.sqrt(30 / 365), 2)
        
        try:
            expiries = tk.options
            if expiries:
                chain = tk.option_chain(expiries[0])
                call_v = chain.calls['volume'].fillna(0).sum()
                put_v = chain.puts['volume'].fillna(0).sum()
                opt_vol = int(call_v + put_v)
                pcr = round(put_v / call_v, 2) if call_v > 0 else 1.0
        except Exception:
            pass

        bull_trigger = f">{r1:.2f} (Target: ${r2:.2f})"
        bear_trigger = f"<{s1:.2f} (Target: ${s2:.2f})"
        target_30d = f"${round(spot + (atr14 * 2.5), 2) if 'Bull' in d_bias else round(spot - (atr14 * 2.0), 2)}"

        return {
            "Ticker": symbol,
            "Asset Name": asset_name,
            "Prior Close": f"${prior_close:.2f}",
            "Pre-Market Price": f"${pre_market:.2f}",
            "PEG ratio": peg_str,
            "Earnings Date": earnings_date,
            "Price-to-Earnings (P/E)": pe_str,
            "Quarterly Directional Bias": q_bias,
            "Daily Directional Bias": d_bias,
            "Market Profile / TPO Structure": tpo_structure,
            "Current POC / VPOC": f"${vpoc:.2f}",
            "Auction Dynamics": auction_dyn,
            "Support 1 (S1)": f"${s1:.2f}",
            "Support 2 (S2)": f"${s2:.2f}",
            "Support 3 (S3 / Macro Support)": f"${s3:.2f}",
            "Pivot / Fair Value (POC/HVN)": f"${pivot:.2f}",
            "Resistance 1 (R1)": f"${r1:.2f}",
            "Resistance 2 (R2)": f"${r2:.2f}",
            "Resistance 3 (R3 / Liquidity Target)": f"${r3:.2f}",
            "RSI (14)": f"{rsi:.1f}",
            "MACD Momentum": macd_str,
            "Options Volume": f"{opt_vol:,}" if opt_vol > 0 else "N/A",
            "Prior Stock Volume": f"{int(prior_vol):,}",
            "Put/Call Ratio (PCR)": f"{pcr:.2f}",
            "IV Rank (%)": f"{int(np.clip(ivr, 0, 100))}%",
            "Expected Move (+/-)": f"+/-${expected_move:.2f}",
            "Bull Trigger & Target": bull_trigger,
            "Bear Trigger & Target": bear_trigger,
            "30-Day Outlook Target": target_30d,
            "Raw_Spot": spot,
            "Raw_S1": s1,
            "Raw_R1": r1,
            "Raw_Earnings": earnings_date,
            "Raw_Bias": d_bias
        }
    except Exception:
        return None

# --- COMPREHENSIVE DERIVATIVES SCANNER (7 TO 30 DTE STRICT WINDOW) ---
def scan_derivatives_strategy(symbol, raw_spot, s1, r1, earnings_date, stock_prediction, strategy_name, book_type):
    """
    Screens institutional option setups within a strict 7 to 30 DTE window.
    Populates standardized 20-column schema across Credit and Debit books.
    """
    try:
        tk = yf.Ticker(symbol)
        expiries = tk.options
        if not expiries:
            return []
        
        now = datetime.now()
        cur_date_str = now.strftime("%Y-%m-%d")
        me_session = "M" if now.hour < 12 else "E"
        
        # Strict 7 to 30 Days to Expiration
        target_expiries = [exp for exp in expiries if 7 <= (datetime.strptime(exp, "%Y-%m-%d") - now).days <= 30]
        if not target_expiries:
            return []
            
        exp = target_expiries[0]
        dte = (datetime.strptime(exp, "%Y-%m-%d") - now).days
        chain = tk.option_chain(exp)
        gap = 10.0 if raw_spot >= 250 else 5.0
        results = []
        
        # ==========================================
        # 1. CREDIT STRATEGIES (NET SELLING)
        # ==========================================
        if book_type == "Credit":
            if "Bull Put Credit Spread" in strategy_name:
                puts = chain.puts.sort_values(by="strike")
                short_k = round((raw_spot * 0.92) / gap) * gap
                long_k = short_k - gap
                s_row = puts[(puts['strike'] - short_k).abs() < 1.0]
                l_row = puts[(puts['strike'] - long_k).abs() < 1.0]
                if not s_row.empty and not l_row.empty:
                    s_mid = (s_row.iloc[0]['bid'] + s_row.iloc[0]['ask']) / 2 if s_row.iloc[0]['bid'] > 0 else s_row.iloc[0]['lastPrice']
                    l_mid = (l_row.iloc[0]['bid'] + l_row.iloc[0]['ask']) / 2 if l_row.iloc[0]['bid'] > 0 else l_row.iloc[0]['lastPrice']
                    net_credit = round(s_mid - l_mid, 2)
                    if net_credit >= (gap * 0.18):
                        max_loss = round((gap - net_credit) * 100, 2)
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Bull Put Spread (${gap:.0f} Gap)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": f"${long_k:.0f}",
                            "Short Put": f"${short_k:.0f}",
                            "Short Call": "—",
                            "Long Call": "—",
                            "Premium": f"${net_credit:.2f}",
                            "Total Premium": f"${net_credit * 100:.2f}",
                            "Sold Idea": "OTM Put Credit below S1 Support (Delta ~0.18)",
                            "Profit": f"${net_credit * 100:.2f}",
                            "Loss": f"${max_loss:.2f}",
                            "Comments": f"Buffer: {((raw_spot - short_k)/raw_spot)*100:.1f}%. Close at 50% max profit or roll at S1 breach."
                        })

            elif "Bear Call Credit Spread" in strategy_name:
                calls = chain.calls.sort_values(by="strike")
                short_k = round((raw_spot * 1.07) / gap) * gap
                long_k = short_k + gap
                s_row = calls[(calls['strike'] - short_k).abs() < 1.0]
                l_row = calls[(calls['strike'] - long_k).abs() < 1.0]
                if not s_row.empty and not l_row.empty:
                    s_mid = (s_row.iloc[0]['bid'] + s_row.iloc[0]['ask']) / 2 if s_row.iloc[0]['bid'] > 0 else s_row.iloc[0]['lastPrice']
                    l_mid = (l_row.iloc[0]['bid'] + l_row.iloc[0]['ask']) / 2 if l_row.iloc[0]['bid'] > 0 else l_row.iloc[0]['lastPrice']
                    net_credit = round(s_mid - l_mid, 2)
                    if net_credit >= (gap * 0.18):
                        max_loss = round((gap - net_credit) * 100, 2)
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Bear Call Spread (${gap:.0f} Gap)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": "—",
                            "Short Call": f"${short_k:.0f}",
                            "Long Call": f"${long_k:.0f}",
                            "Premium": f"${net_credit:.2f}",
                            "Total Premium": f"${net_credit * 100:.2f}",
                            "Sold Idea": "OTM Call Credit above R1 Resistance (Delta ~0.18)",
                            "Profit": f"${net_credit * 100:.2f}",
                            "Loss": f"${max_loss:.2f}",
                            "Comments": f"Buffer: {((short_k - raw_spot)/raw_spot)*100:.1f}%. Manage at 50% profit or roll at R1 test."
                        })

            elif "Iron Condor" in strategy_name:
                short_p = round((raw_spot * 0.92) / gap) * gap
                long_p = short_p - gap
                short_c = round((raw_spot * 1.08) / gap) * gap
                long_c = short_c + gap
                sp = chain.puts[(chain.puts['strike'] - short_p).abs() < 1.0]
                lp = chain.puts[(chain.puts['strike'] - long_p).abs() < 1.0]
                sc = chain.calls[(chain.calls['strike'] - short_c).abs() < 1.0]
                lc = chain.calls[(chain.calls['strike'] - long_c).abs() < 1.0]
                if not sp.empty and not lp.empty and not sc.empty and not lc.empty:
                    c_p = ((sp.iloc[0]['bid'] + sp.iloc[0]['ask'])/2) - ((lp.iloc[0]['bid'] + lp.iloc[0]['ask'])/2)
                    c_c = ((sc.iloc[0]['bid'] + sc.iloc[0]['ask'])/2) - ((lc.iloc[0]['bid'] + lc.iloc[0]['ask'])/2)
                    tot_credit = round(c_p + c_c, 2)
                    if tot_credit >= (gap * 0.28):
                        max_loss = round((gap - tot_credit) * 100, 2)
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Iron Condor (${gap:.0f} Wings)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": f"${long_p:.0f}",
                            "Short Put": f"${short_p:.0f}",
                            "Short Call": f"${short_c:.0f}",
                            "Long Call": f"${long_c:.0f}",
                            "Premium": f"${tot_credit:.2f}",
                            "Total Premium": f"${tot_credit * 100:.2f}",
                            "Sold Idea": "Range-Bound Strangle Wings harvest (POP > 72%)",
                            "Profit": f"${tot_credit * 100:.2f}",
                            "Loss": f"${max_loss:.2f}",
                            "Comments": f"Wings buffer +/-8%. Close at 50% max profit or 21 DTE."
                        })

            elif "Covered Call" in strategy_name:
                target_k = round((raw_spot * 1.05) / gap) * gap
                c_row = chain.calls[(chain.calls['strike'] - target_k).abs() < 1.0]
                if not c_row.empty:
                    mid = round((c_row.iloc[0]['bid'] + c_row.iloc[0]['ask']) / 2, 2)
                    if mid > 0:
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": "Covered Call / Buy-Write",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": "—",
                            "Short Call": f"${target_k:.0f}",
                            "Long Call": "—",
                            "Premium": f"${mid:.2f}",
                            "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "Income generation against 100 shares capped at R1",
                            "Profit": f"${round((target_k - raw_spot + mid) * 100, 2):.2f}",
                            "Loss": f"${round((raw_spot - mid) * 100, 2):.2f}",
                            "Comments": f"Upside capped at ${target_k:.0f}. Downside hedge:${mid:.2f} per share."
                        })

            elif "Jade Lizard" in strategy_name:
                short_p = round((raw_spot * 0.92) / gap) * gap
                short_c = round((raw_spot * 1.06) / gap) * gap
                long_c = short_c + gap
                sp = chain.puts[(chain.puts['strike'] - short_p).abs() < 1.0]
                sc = chain.calls[(chain.calls['strike'] - short_c).abs() < 1.0]
                lc = chain.calls[(chain.calls['strike'] - long_c).abs() < 1.0]
                if not sp.empty and not sc.empty and not lc.empty:
                    p_mid = (sp.iloc[0]['bid'] + sp.iloc[0]['ask']) / 2
                    c_mid = ((sc.iloc[0]['bid'] + sc.iloc[0]['ask']) / 2) - ((lc.iloc[0]['bid'] + lc.iloc[0]['ask']) / 2)
                    tot_credit = round(p_mid + c_mid, 2)
                    if tot_credit >= (gap * 0.35):
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Jade Lizard (${gap:.0f} Call Spread)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": f"${short_p:.0f}",
                            "Short Call": f"${short_c:.0f}",
                            "Long Call": f"${long_c:.0f}",
                            "Premium": f"${tot_credit:.2f}",
                            "Total Premium": f"${tot_credit * 100:.2f}",
                            "Sold Idea": "Zero Upside Risk structure (Total Credit > Call Width)",
                            "Profit": f"${tot_credit * 100:.2f}",
                            "Loss": f"${round((short_p - tot_credit) * 100, 2):.2f}",
                            "Comments": f"No upside loss. Downside risk begins below ${short_p - tot_credit:.2f}."
                        })

        # ==========================================
        # 2. DEBIT STRATEGIES (NET BUYING)
        # ==========================================
        elif book_type == "Debit":
            if "Bull Call Debit Spread" in strategy_name:
                calls = chain.calls.sort_values(by="strike")
                long_k = round((raw_spot * 0.99) / gap) * gap
                short_k = long_k + gap
                l_row = calls[(calls['strike'] - long_k).abs() < 1.0]
                s_row = calls[(calls['strike'] - short_k).abs() < 1.0]
                if not l_row.empty and not s_row.empty:
                    l_mid = (l_row.iloc[0]['bid'] + l_row.iloc[0]['ask']) / 2 if l_row.iloc[0]['bid'] > 0 else l_row.iloc[0]['lastPrice']
                    s_mid = (s_row.iloc[0]['bid'] + s_row.iloc[0]['ask']) / 2 if s_row.iloc[0]['bid'] > 0 else s_row.iloc[0]['lastPrice']
                    net_debit = round(l_mid - s_mid, 2)
                    if 0 < net_debit < gap:
                        max_profit = round((gap - net_debit) * 100, 2)
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Bull Call Debit Spread (${gap:.0f} Gap)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": "—",
                            "Short Call": f"${short_k:.0f}",
                            "Long Call": f"${long_k:.0f}",
                            "Premium": f"${net_debit:.2f}",
                            "Total Premium": f"${net_debit * 100:.2f}",
                            "Sold Idea": "Bullish Breakout Leverage (ATM Buy / OTM Sell)",
                            "Profit": f"${max_profit:.2f}",
                            "Loss": f"${net_debit * 100:.2f}",
                            "Comments": f"Max ROI: {(max_profit/(net_debit*100))*100:.1f}%. Target full profit at ${short_k:.0f}."
                        })

            elif "Bear Put Debit Spread" in strategy_name:
                puts = chain.puts.sort_values(by="strike")
                long_k = round((raw_spot * 1.01) / gap) * gap
                short_k = long_k - gap
                l_row = puts[(puts['strike'] - long_k).abs() < 1.0]
                s_row = puts[(puts['strike'] - short_k).abs() < 1.0]
                if not l_row.empty and not s_row.empty:
                    l_mid = (l_row.iloc[0]['bid'] + l_row.iloc[0]['ask']) / 2 if l_row.iloc[0]['bid'] > 0 else l_row.iloc[0]['lastPrice']
                    s_mid = (s_row.iloc[0]['bid'] + s_row.iloc[0]['ask']) / 2 if s_row.iloc[0]['bid'] > 0 else s_row.iloc[0]['lastPrice']
                    net_debit = round(l_mid - s_mid, 2)
                    if 0 < net_debit < gap:
                        max_profit = round((gap - net_debit) * 100, 2)
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Bear Put Debit Spread (${gap:.0f} Gap)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": f"${long_k:.0f}",
                            "Short Put": f"${short_k:.0f}",
                            "Short Call": "—",
                            "Long Call": "—",
                            "Premium": f"${net_debit:.2f}",
                            "Total Premium": f"${net_debit * 100:.2f}",
                            "Sold Idea": "Directional Breakdown hedge below S1 Support",
                            "Profit": f"${max_profit:.2f}",
                            "Loss": f"${net_debit * 100:.2f}",
                            "Comments": f"Max ROI: {(max_profit/(net_debit*100))*100:.1f}%. Target full profit at ${short_k:.0f}."
                        })

            elif "Poor Man's Covered Call" in strategy_name:
                # Long LEAPS (240+ DTE) + Short Front Month (7-30 DTE)
                leaps_exps = [e for e in expiries if (datetime.strptime(e, "%Y-%m-%d") - now).days >= 240]
                if leaps_exps:
                    l_exp = leaps_exps[0]
                    l_dte = (datetime.strptime(l_exp, "%Y-%m-%d") - now).days
                    l_chain = tk.option_chain(l_exp).calls
                    s_chain = chain.calls
                    target_l_k = raw_spot * 0.82
                    target_s_k = raw_spot * 1.06
                    lc = l_chain.iloc[(l_chain['strike'] - target_l_k).abs().argsort()[:1]].iloc[0]
                    sc = s_chain.iloc[(s_chain['strike'] - target_s_k).abs().argsort()[:1]].iloc[0]
                    l_mid = (lc['bid'] + lc['ask']) / 2 if lc['bid'] > 0 else lc['lastPrice']
                    s_mid = (sc['bid'] + sc['ask']) / 2 if sc['bid'] > 0 else sc['lastPrice']
                    net_debit = round(l_mid - s_mid, 2)
                    if net_debit > 0 and s_mid > 0:
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": "Poor Man's Covered Call (PMCC)",
                            "Expiry": f"{exp} ({dte}d) / {l_exp} ({l_dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": "—",
                            "Short Call": f"${sc['strike']:.0f}",
                            "Long Call": f"${lc['strike']:.0f} (LEAPS)",
                            "Premium": f"${net_debit:.2f}",
                            "Total Premium": f"${net_debit * 100:.2f}",
                            "Sold Idea": "Diagonal Theta extraction against 80Δ LEAPS",
                            "Profit": f"${round(s_mid * 100, 2):.2f} (Cycle 1)",
                            "Loss": f"${net_debit * 100:.2f}",
                            "Comments": f"Cycle 1 yield: {(s_mid/net_debit)*100:.1f}%. Roll short call monthly."
                        })

            elif "Long Calendar Spread" in strategy_name:
                back_exps = [e for e in expiries if 40 <= (datetime.strptime(e, "%Y-%m-%d") - now).days <= 75]
                if back_exps:
                    b_exp = back_exps[0]
                    b_dte = (datetime.strptime(b_exp, "%Y-%m-%d") - now).days
                    b_chain = tk.option_chain(b_exp).calls
                    s_chain = chain.calls
                    atm_k = round(raw_spot / gap) * gap
                    sc = s_chain[(s_chain['strike'] - atm_k).abs() < 1.0]
                    bc = b_chain[(b_chain['strike'] - atm_k).abs() < 1.0]
                    if not sc.empty and not bc.empty:
                        s_mid = (sc.iloc[0]['bid'] + sc.iloc[0]['ask']) / 2
                        b_mid = (bc.iloc[0]['bid'] + bc.iloc[0]['ask']) / 2
                        net_debit = round(b_mid - s_mid, 2)
                        if net_debit > 0:
                            results.append({
                                "Date": cur_date_str,
                                "M/E": me_session,
                                "Stock": symbol,
                                "Earnings": earnings_date,
                                "Support": f"${s1:.2f}",
                                "Resistance": f"${r1:.2f}",
                                "Stock Prediction": stock_prediction,
                                "Strategy": f"Long Call Calendar Spread (${atm_k:.0f}K)",
                                "Expiry": f"{exp} ({dte}d) / {b_exp} ({b_dte}d)",
                                "#Contract": 1,
                                "Long Put": "—",
                                "Short Put": "—",
                                "Short Call": f"${atm_k:.0f}",
                                "Long Call": f"${atm_k:.0f} (Back)",
                                "Premium": f"${net_debit:.2f}",
                                "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Horizontal Theta decay differential exploitation",
                                "Profit": f"${round(net_debit * 0.45 * 100, 2):.2f}",
                                "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Optimal exit at front expiration if spot consolidates near ${atm_k:.0f}."
                            })

            elif "Long Directional Single Call" in strategy_name:
                calls = chain.calls.sort_values(by="strike")
                atm_k = round(raw_spot / gap) * gap
                c_row = calls[(calls['strike'] - atm_k).abs() < 1.0]
                if not c_row.empty:
                    mid = round((c_row.iloc[0]['bid'] + c_row.iloc[0]['ask']) / 2, 2)
                    if mid > 0:
                        results.append({
                            "Date": cur_date_str,
                            "M/E": me_session,
                            "Stock": symbol,
                            "Earnings": earnings_date,
                            "Support": f"${s1:.2f}",
                            "Resistance": f"${r1:.2f}",
                            "Stock Prediction": stock_prediction,
                            "Strategy": f"Long ATM Call (${atm_k:.0f}K)",
                            "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1,
                            "Long Put": "—",
                            "Short Put": "—",
                            "Short Call": "—",
                            "Long Call": f"${atm_k:.0f}",
                            "Premium": f"${mid:.2f}",
                            "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "High-Conviction Directional Trend Continuation",
                            "Profit": "Unlimited",
                            "Loss": f"${mid * 100:.2f}",
                            "Comments": f"Breakeven at ${atm_k + mid:.2f}. Cut loss if spot breaks below S1."
                        })
        return results
    except Exception:
        return []

# ==========================================
# PAGE VIEW HIERARCHY
# ==========================================

# --- SECTION 0: MACRO RADAR & HIGH-LEVEL OUTLOOK ---
st.title("⚡ Institutional Derivatives & Market Execution Terminal")
st.caption(f"Quantitative Options Intelligence Engine | Strict Window: **7 to 30 DTE** | Live Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

barometers = fetch_macro_catalysts()
if barometers:
    b_cols = st.columns(len(barometers))
    for i, (name, (val, chg)) in enumerate(barometers.items()):
        prefix = "$" if "Crude" in name else ""
        suffix = "%" if "Yield" in name else ""
        with b_cols[i]:
            st.metric(label=name, value=f"{prefix}{val:.2f}{suffix}", delta=f"{chg:+.2f}%")

st.markdown("---")

macro_left, macro_right = st.columns([1, 1], gap="medium")
with macro_left:
    st.markdown("### 🏛️ Core Market Drivers & Directional Bias")
    st.markdown("""
    * **Fed Restrictive Policy Stance:** Regional Fed leadership pushes back against rapid rate reductions. **Impact:** Caps valuation multiples on high-beta growth (AMD, NOW, CRWD).
    * **Energy & Fuel Input Overhead:** Crude oil supply resilience tests CPI inputs. **Impact:** Elevates headline inflation expectations and industrial supply chain expenses.
    * **Enterprise AI & Hardware Capex Scrutiny:** Scrutiny over datacenter investments converting into tangible operating margins. **Impact:** High headline volatility around mega-cap guidance (NVDA, MSFT).
    * **10-Year Yield Pressure:** Yield spikes act as the benchmark broad equity discount hurdle, fueling intraday market swings.
    * **US Dollar Index (DXY) Strength:** Dollar resilience acts as an export headwind for multinational blue-chips.
    """)

with macro_right:
    st.markdown("### 📅 High-Impact Catalysts & Market Impact Schedule")
    catalysts = [
        {
            "Event": "September CPI Inflation Print",
            "Date & Time": "Oct 14, 2026 • 8:30 AM EDT",
            "Context / Consensus": "Consensus ~0.2%-0.3% MoM",
            "Expected Market Impact": "Cooler = Tech relief rally, yields drop. Hotter = Immediate equity sell-off."
        },
        {
            "Event": "Federal Reserve Beige Book",
            "Date & Time": "Oct 14, 2026 • 2:00 PM EDT",
            "Context / Consensus": "Regional economic activity",
            "Expected Market Impact": "Wage cooling confirms Fed pause; wage stickiness reignites rate worries."
        },
        {
            "Event": "US Retail Sales Data",
            "Date & Time": "Oct 16, 2026 • 8:30 AM EDT",
            "Context / Consensus": "Consumer resilience gauge",
            "Expected Market Impact": "High read confirms soft-landing; low read triggers cyclical growth fears."
        },
        {
            "Event": "FOMC Interest Rate Decision",
            "Date & Time": "Oct 28, 2026 • 2:00 PM EDT",
            "Context / Consensus": "Target Rate & Press Conference",
            "Expected Market Impact": "Determines year-end institutional liquidity trajectory and bank reserve costs."
        }
    ]
    st.dataframe(pd.DataFrame(catalysts), use_container_width=True, hide_index=True)

st.markdown("---")

# --- SECTION 1: MASTER INSTITUTIONAL REVIEW MATRIX ---
st.subheader("1. Institutional Market Review & Market Profile Matrix")

with st.spinner("Compiling technicals, auction dynamics, and profile levels across active watchlist..."):
    review_rows = []
    for sym in st.session_state.watchlist:
        data = fetch_institutional_profile(sym)
        if data:
            review_rows.append(data)

if review_rows:
    master_df = pd.DataFrame(review_rows)
    master_cols = [
        "Ticker", "Asset Name", "Prior Close", "Pre-Market Price", "PEG ratio",
        "Earnings Date", "Price-to-Earnings (P/E)", "Quarterly Directional Bias",
        "Daily Directional Bias", "Market Profile / TPO Structure", "Current POC / VPOC",
        "Auction Dynamics", "Support 1 (S1)", "Support 2 (S2)", "Support 3 (S3 / Macro Support)",
        "Pivot / Fair Value (POC/HVN)", "Resistance 1 (R1)", "Resistance 2 (R2)",
        "Resistance 3 (R3 / Liquidity Target)", "RSI (14)", "MACD Momentum",
        "Options Volume", "Prior Stock Volume", "Put/Call Ratio (PCR)", "IV Rank (%)",
        "Expected Move (+/-)", "Bull Trigger & Target", "Bear Trigger & Target", "30-Day Outlook Target"
    ]
    display_df = master_df[master_cols]
    filtered_master_df = filter_dataframe(display_df, key_prefix="matrix")
    st.dataframe(filtered_master_df, use_container_width=True, hide_index=True)
else:
    st.warning("No ticker profile data retrieved for active watchlist.")

st.markdown("---")

# --- SECTION 2: OPTIONS EXECUTION HUB (DUAL CREDIT / DEBIT ENGINES) ---
st.subheader("2. Institutional Options Execution Hub (7 to 30 DTE Window)")
st.caption("Quantitative screening matching Greeks, volatility regimes, and POP metrics.")

CREDIT_STRATEGIES = [
    "Bull Put Credit Spread ($5-$10 Gap)",
    "Bear Call Credit Spread ($5-$10 Gap)",
    "Iron Condor (POP > 70%)",
    "Covered Call / Buy-Write",
    "Jade Lizard (Zero Upside Risk)"
]

DEBIT_STRATEGIES = [
    "Bull Call Debit Spread ($5-$10 Gap)",
    "Bear Put Debit Spread ($5-$10 Gap)",
    "Poor Man's Covered Call (PMCC)",
    "Long Calendar Spread (Theta Decay)",
    "Long Directional Single Call"
]

# Side-by-Side Dual Control Panels
hub_col1, hub_col2 = st.columns(2, gap="large")

with hub_col1:
    st.markdown("#### 🟢 Credit Strategies (Net Sellers / Vega Short)")
    c_strat_col, c_btn_col = st.columns([3, 1])
    with c_strat_col:
        selected_credit = st.selectbox("Credit Strategy Selector", CREDIT_STRATEGIES, label_visibility="collapsed")
    with c_btn_col:
        go_credit = st.button("🚀 Go Credit", use_container_width=True)

with hub_col2:
    st.markdown("#### 🔵 Debit Strategies (Net Buyers / Vol Breakout)")
    d_strat_col, d_btn_col = st.columns([3, 1])
    with d_strat_col:
        selected_debit = st.selectbox("Debit Strategy Selector", DEBIT_STRATEGIES, label_visibility="collapsed")
    with d_btn_col:
        go_debit = st.button("🚀 Go Debit", use_container_width=True)

# State initialization for Options Results
if "active_options_results" not in st.session_state:
    st.session_state.active_options_results = []
if "active_strategy_label" not in st.session_state:
    st.session_state.active_strategy_label = ""

# Dispatch Credit Screen
if go_credit:
    st.session_state.active_strategy_label = f"Credit Book: {selected_credit}"
    scanned_candidates = []
    with st.spinner(f"Screening credit options chains (7-30 DTE) for '{selected_credit}'..."):
        for row in review_rows:
            sym = row["Ticker"]
            if sym not in ["SPY", "QQQ"]:
                opt_setups = scan_derivatives_strategy(
                    sym, row["Raw_Spot"], row["Raw_S1"], row["Raw_R1"],
                    row["Raw_Earnings"], row["Raw_Bias"], selected_credit, "Credit"
                )
                if opt_setups:
                    scanned_candidates.extend(opt_setups)
    st.session_state.active_options_results = scanned_candidates

# Dispatch Debit Screen
if go_debit:
    st.session_state.active_strategy_label = f"Debit Book: {selected_debit}"
    scanned_candidates = []
    with st.spinner(f"Screening debit options chains (7-30 DTE) for '{selected_debit}'..."):
        for row in review_rows:
            sym = row["Ticker"]
            if sym not in ["SPY", "QQQ"]:
                opt_setups = scan_derivatives_strategy(
                    sym, row["Raw_Spot"], row["Raw_S1"], row["Raw_R1"],
                    row["Raw_Earnings"], row["Raw_Bias"], selected_debit, "Debit"
                )
                if opt_setups:
                    scanned_candidates.extend(opt_setups)
    st.session_state.active_options_results = scanned_candidates

# Render Exact 20-Column Execution Grid
st.markdown("#### 📋 Strategy Execution Analysis Grid")

REQUIRED_20_COLS = [
    "Date", "M/E", "Stock", "Earnings", "Support", "Resistance", 
    "Stock Prediction", "Strategy", "Expiry", "#Contract", 
    "Long Put", "Short Put", "Short Call", "Long Call", 
    "Premium", "Total Premium", "Sold Idea", "Profit", "Loss", "Comments"
]

if st.session_state.active_options_results:
    st.markdown(f"**Active Execution Matrix:** `{st.session_state.active_strategy_label}`")
    strat_df = pd.DataFrame(st.session_state.active_options_results)
    
    # Ensure exact column ordering
    for c in REQUIRED_20_COLS:
        if c not in strat_df.columns:
            strat_df[c] = "—"
    ordered_df = strat_df[REQUIRED_20_COLS]
    
    filtered_strat_df = filter_dataframe(ordered_df, key_prefix="options_hub")
    st.dataframe(filtered_strat_df, use_container_width=True, hide_index=True)
    
    # Download Options Analysis CSV
    c_csv = filtered_strat_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Strategy Analysis (CSV)",
        data=c_csv,
        file_name=f"Options_Strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
elif st.session_state.active_strategy_label:
    st.info(f"Scan complete for '{st.session_state.active_strategy_label}'. No contracts in the 7-30 DTE window met strict liquidity and spread gates.")
else:
    st.info("Choose a Credit or Debit strategy above and click its corresponding **Go** button to screen contracts.")

# --- EXPORT COMPLETE PORTAL SCRIPT ---
st.markdown("---")
exp_col1, exp_col2 = st.columns([1, 4])
with exp_col1:
    if os.path.exists(__file__):
        with open(__file__, "rb") as app_file:
            st.download_button(
                label="💾 Download Current App Code (.py)",
                data=app_file.read(),
                file_name="app.py",
                mime="text/x-python"
            )