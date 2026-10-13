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
                    cat_cols = ["Ticker", "Stock", "Strategy", "Quarterly Directional Bias", "Daily Directional Bias", "Market Profile / TPO Structure", "Auction Dynamics", "Stock Prediction"]
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
        

	# 1. Precise Session-Aware Price Resolution (Yesterday Close / Today Regular / Now Real-Time)
        prior_close = float(hist_daily['Close'].iloc[-2])
        today_reg = float(hist_daily['Close'].iloc[-1])
        
        # Priority 1: High-frequency 1-minute bar with extended hours enabled
        real_time_now = None
        try:
            hist_live = tk.history(period="1d", interval="1m", prepost=True)
            if not hist_live.empty:
                real_time_now = float(hist_live['Close'].iloc[-1])
        except Exception:
            pass

        # Priority 2: fast_info direct stream
        if real_time_now is None:
            try:
                real_time_now = float(tk.fast_info.get("last_price", 0.0))
                if real_time_now <= 0:
                    real_time_now = None
            except Exception:
                pass

        # Priority 3: Extended hours quotes from info
        if real_time_now is None:
            post_p = info.get("postMarketPrice")
            pre_p = info.get("preMarketPrice")
            reg_p = info.get("regularMarketPrice")
            cur_cand = post_p or pre_p or reg_p or today_reg
            try:
                real_time_now = float(cur_cand)
            except (ValueError, TypeError):
                real_time_now = today_reg

        # Spot anchor: use actual real-time price if available, otherwise regular close
        spot = real_time_now if real_time_now and real_time_now > 0 else today_reg
        dtn_str = f"${prior_close:.2f} / ${today_reg:.2f} / ${spot:.2f}"



        asset_name = info.get("shortName") or info.get("longName") or symbol
        
        # 2. Fundamentals
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

        # 3. Moving Averages & Trend
        ema20 = float(hist_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(hist_daily['Close'].rolling(window=50).mean().iloc[-1])
        sma200 = float(hist_daily['Close'].rolling(window=200).mean().iloc[-1]) if len(hist_daily) >= 200 else np.nan
        
        if not np.isnan(sma200):
            q_bias = "Bullish" if (spot > sma50 and sma50 > sma200) else ("Bearish" if (spot < sma50 and sma50 < sma200) else "Neutral Consolidation")
        else:
            q_bias = "Bullish" if spot > sma50 else "Neutral"
            
        d_bias = "Strong Bull" if spot > ema20 * 1.015 else ("Bullish Pullback" if spot > ema20 else ("Bearish" if spot < ema20 * 0.985 else "Neutral Compression"))

        # 4. Momentum (RSI & MACD)
        delta = hist_daily['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float(100 - (100 / (1 + rs)).iloc[-1])
        
        ema12 = hist_daily['Close'].ewm(span=12, adjust=False).mean()
        ema26 = hist_daily['Close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        macd_val = float(macd_hist.iloc[-1])
        macd_str = "Bullish Expansion" if macd_val > 0 and macd_val > macd_hist.iloc[-2] else ("Bullish Diverging" if macd_val > 0 else ("Bearish Expansion" if macd_val < 0 and macd_val < macd_hist.iloc[-2] else "Bearish Weakening"))

        # 5. Volume Profile & Auction Dynamics
        prior_vol = float(hist_daily['Volume'].iloc[-2])
        if not hist_hourly.empty:
            vpoc = float(hist_hourly.groupby(pd.cut(hist_hourly['Close'], bins=15))['Volume'].sum().idxmax().mid)
        else:
            vpoc = float(hist_daily['Close'].tail(20).median())
            
        recent_20 = hist_daily.tail(20)
        daily_rng = recent_20['High'] - recent_20['Low']
        avg_rng = float(daily_rng.mean())
        last_rng = float(daily_rng.iloc[-1])
        
        if last_rng > avg_rng * 1.3:
            tpo_structure = "Trend Day (Single Prints)"
            auction_dyn = "Initiative Buying" if spot > prior_close else "Initiative Selling"
        elif abs(spot - vpoc) / spot < 0.008:
            tpo_structure = "Normal Day (Rotational POC)"
            auction_dyn = "Balanced / Two-Way Auction"
        else:
            tpo_structure = "Neutral-Extreme (Distribution)"
            auction_dyn = "Responsive Absorption"

        # 6. Technical S/R Levels
        pivot = float((recent_20['High'].max() + recent_20['Low'].min() + spot) / 3)
        tr = np.maximum(
            hist_daily['High'] - hist_daily['Low'],
            np.maximum(
                abs(hist_daily['High'] - hist_daily['Close'].shift(1)),
                abs(hist_daily['Low'] - hist_daily['Close'].shift(1))
            )
        )
        atr14 = float(tr.rolling(window=14).mean().iloc[-1])
        
        s1 = round(spot - (atr14 * 0.75), 2)
        s2 = round(spot - (atr14 * 1.5), 2)
        s3 = round(float(recent_20['Low'].min()), 2)
        
        r1 = round(spot + (atr14 * 0.75), 2)
        r2 = round(spot + (atr14 * 1.5), 2)
        r3 = round(float(recent_20['High'].max()), 2)
        
        # 7. Volatility & IVR
        log_ret = np.log(hist_daily['Close'] / hist_daily['Close'].shift(1)).dropna()
        hv30 = float(log_ret.tail(30).std() * math.sqrt(252) * 100)
        hv_rolling = log_ret.rolling(window=30).std() * math.sqrt(252) * 100
        hv_min, hv_max = float(hv_rolling.min()), float(hv_rolling.max())
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
                pcr = round(float(put_v / call_v), 2) if call_v > 0 else 1.0
        except Exception:
            pass

        bull_trigger = f">{r1:.2f} (Target: ${r2:.2f})"
        bear_trigger = f"<{s1:.2f} (Target: ${s2:.2f})"
        target_30d = f"${round(spot + (atr14 * 2.5), 2) if 'Bull' in d_bias else round(spot - (atr14 * 2.0), 2)}"

        return {
            "Ticker": symbol,
            "Asset Name": asset_name,
            "1 D/T/N": dtn_str,
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


# --- RESILIENT OPTIONS ENGINE (EXPANDED STRATEGY CATALOG / 19-COLUMN SCHEMA) ---
def scan_derivatives_strategy(symbol, raw_spot, s1, r1, earnings_date, stock_prediction, strategy_name, book_type):
    try:
        tk = yf.Ticker(symbol)
        expiries = tk.options
        if not expiries:
            return []
        
        now = datetime.now()
        cur_date_str = now.strftime("%Y-%m-%d")
        
        target_expiries = []
        for e in expiries:
            d = (datetime.strptime(e, "%Y-%m-%d") - now).days
            if 15 <= d <= 45:
                target_expiries.append((e, d))
                
        if not target_expiries:
            fallback = [(e, (datetime.strptime(e, "%Y-%m-%d") - now).days) for e in expiries if (datetime.strptime(e, "%Y-%m-%d") - now).days >= 14]
            if fallback:
                target_expiries.append(fallback[0])
            else:
                return []
                
        gap = 10.0 if raw_spot >= 250 else 5.0
        results = []

        def get_clean_mid(row):
            if row.empty:
                return 0.0
            r = row.iloc[0]
            bid, ask, last = float(r.get('bid', 0.0)), float(r.get('ask', 0.0)), float(r.get('lastPrice', 0.0))
            if bid > 0 and ask > 0:
                return (bid + ask) / 2.0
            return last if last > 0 else 0.50

        def get_nearest(df, target_k):
            if df.empty:
                return df
            return df.iloc[(df['strike'] - target_k).abs().argsort()[:1]]

        for exp, dte in target_expiries[:3]:
            try:
                chain = tk.option_chain(exp)
            except Exception:
                continue

            # ==========================================
            # 1. EXPANDED CREDIT STRATEGIES
            # ==========================================
            if book_type == "Credit":
                if "Bull Put Credit Spread" in strategy_name:
                    target_short = raw_spot * 0.92
                    s_row = get_nearest(chain.puts, target_short)
                    if not s_row.empty:
                        actual_short_k = float(s_row.iloc[0]['strike'])
                        l_row = get_nearest(chain.puts[chain.puts['strike'] < actual_short_k], actual_short_k - gap)
                        if not l_row.empty:
                            actual_long_k = float(l_row.iloc[0]['strike'])
                            actual_gap = actual_short_k - actual_long_k
                            net_credit = max(round(get_clean_mid(s_row) - get_clean_mid(l_row), 2), 0.25)
                            max_loss = round((actual_gap - net_credit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Bull Put Spread (${actual_gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": f"${actual_long_k:.0f}", "Short Put": f"${actual_short_k:.0f}",
                                "Short Call": "—", "Long Call": "—", "Premium": f"${net_credit:.2f}",
                                "Total Premium": f"${net_credit * 100:.2f}", "Sold Idea": "OTM Put Credit below S1 Support (POP ~78%)",
                                "Profit": f"${net_credit * 100:.2f}", "Loss": f"${max_loss:.2f}",
                                "Comments": f"Buffer: {((raw_spot - actual_short_k)/raw_spot)*100:.1f}%. Target 50% max profit exit."
                            })
                            break

                elif "Bear Call Credit Spread" in strategy_name:
                    target_short = raw_spot * 1.08
                    s_row = get_nearest(chain.calls, target_short)
                    if not s_row.empty:
                        actual_short_k = float(s_row.iloc[0]['strike'])
                        l_row = get_nearest(chain.calls[chain.calls['strike'] > actual_short_k], actual_short_k + gap)
                        if not l_row.empty:
                            actual_long_k = float(l_row.iloc[0]['strike'])
                            actual_gap = actual_long_k - actual_short_k
                            net_credit = max(round(get_clean_mid(s_row) - get_clean_mid(l_row), 2), 0.25)
                            max_loss = round((actual_gap - net_credit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Bear Call Spread (${actual_gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": "—", "Short Put": "—",
                                "Short Call": f"${actual_short_k:.0f}", "Long Call": f"${actual_long_k:.0f}",
                                "Premium": f"${net_credit:.2f}", "Total Premium": f"${net_credit * 100:.2f}",
                                "Sold Idea": "OTM Call Credit above R1 Resistance (POP ~77%)", "Profit": f"${net_credit * 100:.2f}",
                                "Loss": f"${max_loss:.2f}", "Comments": f"Buffer: {((actual_short_k - raw_spot)/raw_spot)*100:.1f}%. Manage at 50% profit."
                            })
                            break

                elif "Iron Condor" in strategy_name:
                    sp_row = get_nearest(chain.puts, raw_spot * 0.91)
                    sc_row = get_nearest(chain.calls, raw_spot * 1.09)
                    if not sp_row.empty and not sc_row.empty:
                        short_p = float(sp_row.iloc[0]['strike'])
                        short_c = float(sc_row.iloc[0]['strike'])
                        lp_row = get_nearest(chain.puts[chain.puts['strike'] < short_p], short_p - gap)
                        lc_row = get_nearest(chain.calls[chain.calls['strike'] > short_c], short_c + gap)
                        if not lp_row.empty and not lc_row.empty:
                            long_p = float(lp_row.iloc[0]['strike'])
                            long_c = float(lc_row.iloc[0]['strike'])
                            wing_p = short_p - long_p
                            cr_p = max(get_clean_mid(sp_row) - get_clean_mid(lp_row), 0.15)
                            cr_c = max(get_clean_mid(sc_row) - get_clean_mid(lc_row), 0.15)
                            tot_credit = round(cr_p + cr_c, 2)
                            max_loss = round((wing_p - tot_credit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Iron Condor (${wing_p:.0f} Wings)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": f"${long_p:.0f}", "Short Put": f"${short_p:.0f}",
                                "Short Call": f"${short_c:.0f}", "Long Call": f"${long_c:.0f}",
                                "Premium": f"${tot_credit:.2f}", "Total Premium": f"${tot_credit * 100:.2f}",
                                "Sold Idea": "Range-bound Theta harvest (POP ~73%)",
                                "Profit": f"${tot_credit * 100:.2f}", "Loss": f"${max_loss:.2f}",
                                "Comments": f"Wings buffer +/-9%. Exit at 50% profit or 21 DTE."
                            })
                            break

                elif "Iron Butterfly" in strategy_name:
                    atm_c_row = get_nearest(chain.calls, raw_spot)
                    atm_p_row = get_nearest(chain.puts, raw_spot)
                    if not atm_c_row.empty and not atm_p_row.empty:
                        pin_k = float(atm_c_row.iloc[0]['strike'])
                        lp_row = get_nearest(chain.puts[chain.puts['strike'] < pin_k], pin_k - gap)
                        lc_row = get_nearest(chain.calls[chain.calls['strike'] > pin_k], pin_k + gap)
                        if not lp_row.empty and not lc_row.empty:
                            long_p = float(lp_row.iloc[0]['strike'])
                            long_c = float(lc_row.iloc[0]['strike'])
                            c_p = max(get_clean_mid(atm_p_row) - get_clean_mid(lp_row), 0.20)
                            c_c = max(get_clean_mid(atm_c_row) - get_clean_mid(lc_row), 0.20)
                            tot_credit = round(c_p + c_c, 2)
                            max_loss = round((gap - tot_credit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Iron Butterfly (${gap:.0f} Wings)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": f"${long_p:.0f}", "Short Put": f"${pin_k:.0f}",
                                "Short Call": f"${pin_k:.0f}", "Long Call": f"${long_c:.0f}",
                                "Premium": f"${tot_credit:.2f}", "Total Premium": f"${tot_credit * 100:.2f}",
                                "Sold Idea": "High-Credit Pin Harvest at Fair Value/POC",
                                "Profit": f"${tot_credit * 100:.2f}", "Loss": f"${max_loss:.2f}",
                                "Comments": f"Optimal pin near ${pin_k:.0f}. Close at 35%-40% max profit."
                            })
                            break

                elif "Covered Call" in strategy_name:
                    c_row = get_nearest(chain.calls, raw_spot * 1.05)
                    if not c_row.empty:
                        target_k = float(c_row.iloc[0]['strike'])
                        mid = round(get_clean_mid(c_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Covered Call / Buy-Write", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": "—", "Short Put": "—",
                            "Short Call": f"${target_k:.0f}", "Long Call": "—",
                            "Premium": f"${mid:.2f}", "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "Income generation against 100 shares capped at R1",
                            "Profit": f"${round((target_k - raw_spot + mid) * 100, 2):.2f}",
                            "Loss": f"${round((raw_spot - mid) * 100, 2):.2f}",
                            "Comments": f"Upside capped at ${target_k:.0f}. Downside hedge: ${mid:.2f}/sh."
                        })
                        break

                elif "Cash-Secured Put" in strategy_name:
                    p_row = get_nearest(chain.puts, raw_spot * 0.90)
                    if not p_row.empty:
                        target_k = float(p_row.iloc[0]['strike'])
                        mid = round(get_clean_mid(p_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Cash-Secured Put (Target Buy)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": "—", "Short Put": f"${target_k:.0f}",
                            "Short Call": "—", "Long Call": "—",
                            "Premium": f"${mid:.2f}", "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "Acquire shares below S2 support at net discount",
                            "Profit": f"${mid * 100:.2f}", "Loss": f"${round((target_k - mid) * 100, 2):.2f}",
                            "Comments": f"Effective buy price: ${target_k - mid:.2f}. Capital req: ${target_k * 100:.2f}."
                        })
                        break

                elif "Jade Lizard" in strategy_name:
                    sp_row = get_nearest(chain.puts, raw_spot * 0.92)
                    sc_row = get_nearest(chain.calls, raw_spot * 1.06)
                    if not sp_row.empty and not sc_row.empty:
                        short_p = float(sp_row.iloc[0]['strike'])
                        short_c = float(sc_row.iloc[0]['strike'])
                        lc_row = get_nearest(chain.calls[chain.calls['strike'] > short_c], short_c + gap)
                        if not lc_row.empty:
                            long_c = float(lc_row.iloc[0]['strike'])
                            p_mid = get_clean_mid(sp_row)
                            c_credit = max(get_clean_mid(sc_row) - get_clean_mid(lc_row), 0.15)
                            tot_credit = round(p_mid + c_credit, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Jade Lizard (${long_c - short_c:.0f} Call Spread)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": "—", "Short Put": f"${short_p:.0f}",
                                "Short Call": f"${short_c:.0f}", "Long Call": f"${long_c:.0f}",
                                "Premium": f"${tot_credit:.2f}", "Total Premium": f"${tot_credit * 100:.2f}",
                                "Sold Idea": "Zero Upside Risk structure (Credit >= Call Width)",
                                "Profit": f"${tot_credit * 100:.2f}", "Loss": f"${round((short_p - tot_credit) * 100, 2):.2f}",
                                "Comments": f"No upside loss. Downside risk starts below ${short_p - tot_credit:.2f}."
                            })
                            break

                elif "Short Strangle" in strategy_name:
                    sp_row = get_nearest(chain.puts, raw_spot * 0.88)
                    sc_row = get_nearest(chain.calls, raw_spot * 1.12)
                    if not sp_row.empty and not sc_row.empty:
                        short_p = float(sp_row.iloc[0]['strike'])
                        short_c = float(sc_row.iloc[0]['strike'])
                        tot_credit = round(get_clean_mid(sp_row) + get_clean_mid(sc_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Short Strangle (High IV Seller)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": "—", "Short Put": f"${short_p:.0f}",
                            "Short Call": f"${short_c:.0f}", "Long Call": "—",
                            "Premium": f"${tot_credit:.2f}", "Total Premium": f"${tot_credit * 100:.2f}",
                            "Sold Idea": "Volatility Implosion & Wide Strangle Wing Harvest",
                            "Profit": f"${tot_credit * 100:.2f}", "Loss": "Undefined (Margin)",
                            "Comments": f"Breakevens: ${short_p - tot_credit:.2f} to ${short_c + tot_credit:.2f}. Close at 50% max profit."
                        })
                        break

                elif "Short Straddle" in strategy_name:
                    atm_c = get_nearest(chain.calls, raw_spot)
                    atm_p = get_nearest(chain.puts, raw_spot)
                    if not atm_c.empty and not atm_p.empty:
                        pin_k = float(atm_c.iloc[0]['strike'])
                        tot_credit = round(get_clean_mid(atm_c) + get_clean_mid(atm_p), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Short Straddle (Maximum Premium)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": "—", "Short Put": f"${pin_k:.0f}",
                            "Short Call": f"${pin_k:.0f}", "Long Call": "—",
                            "Premium": f"${tot_credit:.2f}", "Total Premium": f"${tot_credit * 100:.2f}",
                            "Sold Idea": "Pure Volatility Implosion pinned at Fair Value",
                            "Profit": f"${tot_credit * 100:.2f}", "Loss": "Undefined (Margin)",
                            "Comments": f"Manage early at 25%-30% max profit. Breakeven +/-${tot_credit:.2f}."
                        })
                        break

            # ==========================================
            # 2. EXPANDED DEBIT STRATEGIES
            # ==========================================
            elif book_type == "Debit":
                if "Bull Call Debit Spread" in strategy_name:
                    l_row = get_nearest(chain.calls, raw_spot * 0.99)
                    if not l_row.empty:
                        long_k = float(l_row.iloc[0]['strike'])
                        s_row = get_nearest(chain.calls[chain.calls['strike'] > long_k], long_k + gap)
                        if not s_row.empty:
                            short_k = float(s_row.iloc[0]['strike'])
                            spread_w = short_k - long_k
                            net_debit = min(max(round(get_clean_mid(l_row) - get_clean_mid(s_row), 2), 0.35), spread_w - 0.10)
                            max_profit = round((spread_w - net_debit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Bull Call Debit Spread (${spread_w:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": "—", "Short Put": "—",
                                "Short Call": f"${short_k:.0f}", "Long Call": f"${long_k:.0f}",
                                "Premium": f"${net_debit:.2f}", "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Bullish Breakout Leverage (ATM Buy / OTM Sell)",
                                "Profit": f"${max_profit:.2f}", "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Max ROI: {(max_profit/(net_debit*100))*100:.1f}%. Full profit at ${short_k:.0f}."
                            })
                            break

                elif "Bear Put Debit Spread" in strategy_name:
                    l_row = get_nearest(chain.puts, raw_spot * 1.01)
                    if not l_row.empty:
                        long_k = float(l_row.iloc[0]['strike'])
                        s_row = get_nearest(chain.puts[chain.puts['strike'] < long_k], long_k - gap)
                        if not s_row.empty:
                            short_k = float(s_row.iloc[0]['strike'])
                            spread_w = long_k - short_k
                            net_debit = min(max(round(get_clean_mid(l_row) - get_clean_mid(s_row), 2), 0.35), spread_w - 0.10)
                            max_profit = round((spread_w - net_debit) * 100, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Bear Put Debit Spread (${spread_w:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "#Contract": 1, "Long Put": f"${long_k:.0f}", "Short Put": f"${short_k:.0f}",
                                "Short Call": "—", "Long Call": "—",
                                "Premium": f"${net_debit:.2f}", "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Directional Breakdown hedge below S1 Support",
                                "Profit": f"${max_profit:.2f}", "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Max ROI: {(max_profit/(net_debit*100))*100:.1f}%. Full profit at ${short_k:.0f}."
                            })
                            break

                elif "Long Directional Single Call" in strategy_name:
                    c_row = get_nearest(chain.calls, raw_spot)
                    if not c_row.empty:
                        atm_k = float(c_row.iloc[0]['strike'])
                        mid = round(get_clean_mid(c_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": f"Long ATM Call (${atm_k:.0f} Strike)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": "—", "Short Put": "—", "Short Call": "—",
                            "Long Call": f"${atm_k:.0f}", "Premium": f"${mid:.2f}", "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "High-Conviction Directional Trend Continuation",
                            "Profit": "Unlimited", "Loss": f"${mid * 100:.2f}",
                            "Comments": f"Breakeven at ${atm_k + mid:.2f}. Cut loss if spot breaks below S1."
                        })
                        break

                elif "Long Directional Single Put" in strategy_name:
                    p_row = get_nearest(chain.puts, raw_spot)
                    if not p_row.empty:
                        atm_k = float(p_row.iloc[0]['strike'])
                        mid = round(get_clean_mid(p_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": f"Long ATM Put (${atm_k:.0f} Strike)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": f"${atm_k:.0f}", "Short Put": "—",
                            "Short Call": "—", "Long Call": "—",
                            "Premium": f"${mid:.2f}", "Total Premium": f"${mid * 100:.2f}",
                            "Sold Idea": "High-Conviction Directional Breakdown Hedge",
                            "Profit": f"${round((atm_k - mid) * 100, 2):.2f}", "Loss": f"${mid * 100:.2f}",
                            "Comments": f"Breakeven at ${atm_k - mid:.2f}. Cut loss if spot reclaims R1."
                        })
                        break

                elif "Poor Man's Covered Call" in strategy_name:
                    leaps_exps = [e for e in expiries if (datetime.strptime(e, "%Y-%m-%d") - now).days >= 180]
                    if leaps_exps:
                        l_exp = leaps_exps[0]
                        l_dte = (datetime.strptime(l_exp, "%Y-%m-%d") - now).days
                        l_chain = tk.option_chain(l_exp).calls
                        lc = get_nearest(l_chain, raw_spot * 0.82)
                        sc = get_nearest(chain.calls, raw_spot * 1.06)
                        if not lc.empty and not sc.empty:
                            l_k = float(lc.iloc[0]['strike'])
                            s_k = float(sc.iloc[0]['strike'])
                            l_mid = get_clean_mid(lc)
                            s_mid = get_clean_mid(sc)
                            net_debit = round(l_mid - s_mid, 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": "Poor Man's Covered Call (PMCC)", "Expiry": f"{exp} ({dte}d) / {l_exp} ({l_dte}d)",
                                "#Contract": 1, "Long Put": "—", "Short Put": "—",
                                "Short Call": f"${s_k:.0f}", "Long Call": f"${l_k:.0f} (LEAPS)",
                                "Premium": f"${net_debit:.2f}", "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Diagonal Theta extraction against 80Δ LEAPS",
                                "Profit": f"${round(s_mid * 100, 2):.2f} (Cycle 1)", "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Cycle 1 yield: {(s_mid/max(net_debit, 1.0))*100:.1f}%. Roll short call monthly."
                            })
                            break

                elif "Long Call Calendar Spread" in strategy_name:
                    back_exps = [e for e in expiries if 40 <= (datetime.strptime(e, "%Y-%m-%d") - now).days <= 80]
                    if back_exps:
                        b_exp = back_exps[0]
                        b_dte = (datetime.strptime(b_exp, "%Y-%m-%d") - now).days
                        b_chain = tk.option_chain(b_exp).calls
                        sc = get_nearest(chain.calls, raw_spot)
                        bc = get_nearest(b_chain, raw_spot)
                        if not sc.empty and not bc.empty:
                            atm_k = float(sc.iloc[0]['strike'])
                            net_debit = round(max(get_clean_mid(bc) - get_clean_mid(sc), 0.50), 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Long Call Calendar Spread (${atm_k:.0f}K)", "Expiry": f"{exp} ({dte}d) / {b_exp} ({b_dte}d)",
                                "#Contract": 1, "Long Put": "—", "Short Put": "—",
                                "Short Call": f"${atm_k:.0f}", "Long Call": f"${atm_k:.0f} (Back)",
                                "Premium": f"${net_debit:.2f}", "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Horizontal Theta decay differential exploitation",
                                "Profit": f"${round(net_debit * 0.45 * 100, 2):.2f}", "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Optimal exit at front expiration near ${atm_k:.0f}."
                            })
                            break

                elif "Long Put Calendar Spread" in strategy_name:
                    back_exps = [e for e in expiries if 40 <= (datetime.strptime(e, "%Y-%m-%d") - now).days <= 80]
                    if back_exps:
                        b_exp = back_exps[0]
                        b_dte = (datetime.strptime(b_exp, "%Y-%m-%d") - now).days
                        b_chain = tk.option_chain(b_exp).puts
                        sp = get_nearest(chain.puts, s1)
                        bp = get_nearest(b_chain, s1)
                        if not sp.empty and not bp.empty:
                            target_k = float(sp.iloc[0]['strike'])
                            net_debit = round(max(get_clean_mid(bp) - get_clean_mid(sp), 0.50), 2)
                            results.append({
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                                "Strategy": f"Long Put Calendar Spread (${target_k:.0f}K)", "Expiry": f"{exp} ({dte}d) / {b_exp} ({b_dte}d)",
                                "#Contract": 1, "Long Put": f"${target_k:.0f} (Back)", "Short Put": f"${target_k:.0f}",
                                "Short Call": "—", "Long Call": "—",
                                "Premium": f"${net_debit:.2f}", "Total Premium": f"${net_debit * 100:.2f}",
                                "Sold Idea": "Bearish drift toward S1 Support with expanding Vega",
                                "Profit": f"${round(net_debit * 0.45 * 100, 2):.2f}", "Loss": f"${net_debit * 100:.2f}",
                                "Comments": f"Target exit at front expiration if spot rests near ${target_k:.0f}."
                            })
                            break

                elif "Long Straddle" in strategy_name:
                    atm_c = get_nearest(chain.calls, raw_spot)
                    atm_p = get_nearest(chain.puts, raw_spot)
                    if not atm_c.empty and not atm_p.empty:
                        pin_k = float(atm_c.iloc[0]['strike'])
                        tot_debit = round(get_clean_mid(atm_c) + get_clean_mid(atm_p), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Long Straddle (Volatility Expansion)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": f"${pin_k:.0f}", "Short Put": "—",
                            "Short Call": "—", "Long Call": f"${pin_k:.0f}",
                            "Premium": f"${tot_debit:.2f}", "Total Premium": f"${tot_debit * 100:.2f}",
                            "Sold Idea": "Asymmetric Volatility Expansion / Breakout",
                            "Profit": "Unlimited", "Loss": f"${tot_debit * 100:.2f}",
                            "Comments": f"Requires move > +/-${tot_debit:.2f} to profit. Close before IV crush."
                        })
                        break

                elif "Long Strangle" in strategy_name:
                    lp_row = get_nearest(chain.puts, raw_spot * 0.94)
                    lc_row = get_nearest(chain.calls, raw_spot * 1.06)
                    if not lp_row.empty and not lc_row.empty:
                        long_p = float(lp_row.iloc[0]['strike'])
                        long_c = float(lc_row.iloc[0]['strike'])
                        tot_debit = round(get_clean_mid(lp_row) + get_clean_mid(lc_row), 2)
                        results.append({
                            "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                            "Support": f"${s1:.2f}", "Resistance": f"${r1:.2f}", "Stock Prediction": stock_prediction,
                            "Strategy": "Long Strangle (Tail Risk Breakout)", "Expiry": f"{exp} ({dte}d)",
                            "#Contract": 1, "Long Put": f"${long_p:.0f}", "Short Put": "—",
                            "Short Call": "—", "Long Call": f"${long_c:.0f}",
                            "Premium": f"${tot_debit:.2f}", "Total Premium": f"${tot_debit * 100:.2f}",
                            "Sold Idea": "Outsized Tail Move capture across earnings or macro shock",
                            "Profit": "Unlimited", "Loss": f"${tot_debit * 100:.2f}",
                            "Comments": f"Cheaper than Straddle. Profits if spot breaches ${long_p - tot_debit:.2f} or ${long_c + tot_debit:.2f}."
                        })
                        break

        return results
    except Exception:
        return []

# ==========================================
# PAGE VIEW HIERARCHY
# ==========================================

# --- SECTION 0: MACRO RADAR & HIGH-LEVEL OUTLOOK ---
st.title("⚡ Institutional Derivatives & Market Execution Terminal")
st.caption(f"Quantitative Options Intelligence Engine | Standard Window: **15 to 45 DTE** | Live Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
        "Ticker", "Asset Name", "1 D/T/N", "PEG ratio",
        "Earnings Date", "Price-to-Earnings (P/E)", "Quarterly Directional Bias",
        "Daily Directional Bias", "Market Profile / TPO Structure", "Current POC / VPOC",
        "Auction Dynamics", "Support 1 (S1)", "Support 2 (S2)", "Support 3 (S3 / Macro Support)",
        "Pivot / Fair Value (POC/HVN)", "Resistance 1 (R1)", "Resistance 2 (R2)",
        "Resistance 3 (R3 / Liquidity Target)", "RSI (14)", "MACD Momentum",
        "Options Volume", "Prior Stock Volume", "Put/Call Ratio (PCR)", "IV Rank (%)",
        "Expected Move (+/-)", "Bull Trigger & Target", "Bear Trigger & Target", "30-Day Outlook Target"
    ]
    display_df = master_df[master_cols]

    # Quick Ticker Filter
    all_avail_tickers = sorted(list(display_df["Ticker"].unique()))
    quick_tickers = st.multiselect(
        "🎯 Quick Ticker Filter (Pick 1 or many for instant view):",
        options=all_avail_tickers,
        default=[],
        placeholder="Select ticker(s) e.g., NVDA, AMD..."
    )
    if quick_tickers:
        display_df = display_df[display_df["Ticker"].isin(quick_tickers)]

    filtered_master_df = filter_dataframe(display_df, key_prefix="matrix")

    # 20-Row Pagination
    ROWS_PER_PAGE = 20
    total_rows = len(filtered_master_df)
    total_pages = max(1, math.ceil(total_rows / ROWS_PER_PAGE))

    if total_pages > 1:
        p_col1, p_col2, p_col3 = st.columns([1, 2, 5])
        with p_col1:
            page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
        with p_col2:
            st.markdown(f"<div style='padding-top: 2rem; font-weight: 600;'>Showing page {page_num} of {total_pages} ({total_rows} total rows)</div>", unsafe_allow_html=True)
    else:
        page_num = 1

    start_idx = (page_num - 1) * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    paged_df = filtered_master_df.iloc[start_idx:end_idx]

    # Sticky Columns CSS: Frozen Columns 1 (Ticker), 2 (Asset Name), 3 (1 D/T/N)
    html_code = """
    <style>
        .custom-grid-container {
            max-width: 100%;
            overflow-x: auto;
            max-height: 800px;
            overflow-y: auto;
            border: 1px solid #2e3546;
            border-radius: 8px;
            background-color: #0e1117;
            margin-bottom: 1rem;
        }
        .frozen-table {
            border-collapse: collapse;
            width: 100%;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 0.85rem;
            color: #fafafa;
            white-space: nowrap;
        }
        .frozen-table th, .frozen-table td {
            padding: 8px 14px;
            border-bottom: 1px solid #232734;
            text-align: left;
        }
        .frozen-table th {
            background-color: #161b26;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 5;
        }
        /* Sticky Column 1: Ticker (Width ~85px) */
        .frozen-table th:nth-child(1), .frozen-table td:nth-child(1) {
            position: sticky;
            left: 0px;
            background-color: #121620;
            min-width: 85px;
            z-index: 4;
            font-weight: 700;
            border-right: 1px solid #232734;
        }
        /* Sticky Column 2: Asset Name (Width ~170px, starts at 85px) */
        .frozen-table th:nth-child(2), .frozen-table td:nth-child(2) {
            position: sticky;
            left: 85px;
            background-color: #121620;
            min-width: 170px;
            z-index: 4;
            border-right: 1px solid #232734;
        }
        /* Sticky Column 3: 1 D/T/N (Yesterday/Today/Now, starts at 255px) */
        .frozen-table th:nth-child(3), .frozen-table td:nth-child(3) {
            position: sticky;
            left: 255px;
            background-color: #121620;
            min-width: 220px;
            z-index: 4;
            font-weight: 600;
            color: #60a5fa;
            box-shadow: 4px 0 6px -2px rgba(0,0,0,0.45);
            border-right: 2px solid #3b82f6;
        }
        .frozen-table th:nth-child(1), .frozen-table th:nth-child(2), .frozen-table th:nth-child(3) {
            z-index: 10;
            background-color: #1a2233;
        }
        .frozen-table tr:hover td {
            background-color: #1f2737;
        }
    </style>
    <div class="custom-grid-container">
        <table class="frozen-table">
            <thead>
                <tr>
    """
    for col in paged_df.columns:
        html_code += f"<th>{col}</th>"
    html_code += "</tr></thead><tbody>"

    for _, row in paged_df.iterrows():
        html_code += "<tr>"
        for _, val in row.items():
            html_code += f"<td>{val}</td>"
        html_code += "</tr>"
    html_code += "</tbody></table></div>"

    st.markdown(html_code, unsafe_allow_html=True)
else:
    st.warning("No ticker profile data retrieved for active watchlist.")

st.markdown("---")

# --- SECTION 2: OPTIONS EXECUTION HUB (FULL CREDIT / DEBIT STRATEGY CATALOG) ---
st.subheader("2. Institutional Options Execution Hub (15 to 45 DTE Window)")
st.caption("Quantitative screening matching Greeks, volatility regimes, and POP metrics.")

CREDIT_STRATEGIES = [
    "Bull Put Credit Spread ($5-$10 Gap)",
    "Bear Call Credit Spread ($5-$10 Gap)",
    "Iron Condor (POP > 70%)",
    "Iron Butterfly (High-Credit Pin)",
    "Covered Call / Buy-Write",
    "Cash-Secured Put (Target Buy)",
    "Jade Lizard (Zero Upside Risk)",
    "Short Strangle (High IV Seller)",
    "Short Straddle (Maximum Premium)"
]

DEBIT_STRATEGIES = [
    "Bull Call Debit Spread ($5-$10 Gap)",
    "Bear Put Debit Spread ($5-$10 Gap)",
    "Long Directional Single Call",
    "Long Directional Single Put",
    "Poor Man's Covered Call (PMCC)",
    "Long Call Calendar Spread",
    "Long Put Calendar Spread",
    "Long Straddle (Volatility Expansion)",
    "Long Strangle (Tail Risk Breakout)"
]

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

if "active_options_results" not in st.session_state:
    st.session_state.active_options_results = []
if "active_strategy_label" not in st.session_state:
    st.session_state.active_strategy_label = ""

if go_credit:
    st.session_state.active_strategy_label = f"Credit Book: {selected_credit}"
    scanned_candidates = []
    with st.spinner(f"Screening credit options chains (15-45 DTE) for '{selected_credit}'..."):
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

if go_debit:
    st.session_state.active_strategy_label = f"Debit Book: {selected_debit}"
    scanned_candidates = []
    with st.spinner(f"Screening debit options chains (15-45 DTE) for '{selected_debit}'..."):
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

st.markdown("#### 📋 Strategy Execution Analysis Grid")

# 19-Column Schema (M/E Removed)
REQUIRED_19_COLS = [
    "Date", "Stock", "Earnings", "Support", "Resistance", 
    "Stock Prediction", "Strategy", "Expiry", "#Contract", 
    "Long Put", "Short Put", "Short Call", "Long Call", 
    "Premium", "Total Premium", "Sold Idea", "Profit", "Loss", "Comments"
]

if st.session_state.active_options_results:
    st.markdown(f"**Active Execution Matrix:** `{st.session_state.active_strategy_label}`")
    strat_df = pd.DataFrame(st.session_state.active_options_results)
    for c in REQUIRED_19_COLS:
        if c not in strat_df.columns:
            strat_df[c] = "—"
    ordered_df = strat_df[REQUIRED_19_COLS]
    
    # Quick Ticker Filter for Options Grid
    all_opt_tickers = sorted(list(ordered_df["Stock"].unique()))
    opt_quick_tickers = st.multiselect(
        "🎯 Filter Tickers in Options Grid:",
        options=all_opt_tickers,
        default=[],
        key="opt_quick_filter"
    )
    if opt_quick_tickers:
        ordered_df = ordered_df[ordered_df["Stock"].isin(opt_quick_tickers)]

    filtered_strat_df = filter_dataframe(ordered_df, key_prefix="options_hub")
    st.dataframe(filtered_strat_df, use_container_width=True, hide_index=True)
    
    c_csv = filtered_strat_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Strategy Analysis (CSV)",
        data=c_csv,
        file_name=f"Options_Strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
elif st.session_state.active_strategy_label:
    st.info(f"Scan complete for '{st.session_state.active_strategy_label}'. No contracts in the 15-45 DTE window met strict liquidity and spread gates.")
else:
    st.info("Choose a Credit or Debit strategy above and click its corresponding **Go** button to screen contracts.")
