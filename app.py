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
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- PERSISTENT WATCHLIST SETUP (24 MASTER TICKERS) ---
WATCHLIST_FILE = "watchlist.json"
DEFAULT_TICKERS = [
    "SPY", "QQQ", "DIA", "IWM", "TSLA", "NVDA", "SHOP", "NOW", "APP", 
    "MSFT", "AAPL", "META", "GOOGL", "AMD", "LLY", "NET", "SPOT", 
    "AVGO", "CRWD", "NFLX", "PLTR", "MU", "GLD", "TLT"
]

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    loaded = [str(t).strip().upper() for t in data]
                    return list(dict.fromkeys(DEFAULT_TICKERS + loaded))
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
    page_title="Institutional Derivatives Terminal & Intelligence Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling mimicking the left panel navigation layout
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
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .dispatch-box {
        background-color: #161b26;
        border: 1px solid #2e3546;
        border-radius: 8px;
        padding: 16px;
        margin-top: 12px;
    }
    /* Enterprise Sidebar Navigation styling */
    .nav-header {
        background-color: #1b365d;
        color: #ffffff;
        padding: 10px 14px;
        border-radius: 6px 6px 0 0;
        font-weight: 700;
        font-size: 1.05rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    div[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        text-align: left;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-radius: 0;
        margin-bottom: 1px;
        border: 1px solid #2e3546;
        background-color: #121620;
        color: #e2e8f0;
        padding: 10px 14px;
        font-weight: 600;
    }
    div[data-testid="stSidebar"] div.stButton > button:hover {
        background-color: #1e293b;
        color: #60a5fa;
        border-color: #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

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

# --- GLOBAL DATA ENGINE: BENCHMARKS & PRICING ---
@st.cache_data(ttl=60)
def fetch_top_indices():
    indices = ["SPY", "QQQ", "DIA", "IWM", "^VIX", "GLD", "TLT"]
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
                        
                data[sym] = {"price": last_p, "chg": pct_chg, "bias": bias, "color": color}
    except Exception:
        pass
    return data

@st.cache_data(ttl=180)
def fetch_macro_catalysts():
    barometers = {}
    try:
        b_df = yf.download(["^TNX", "CL=F", "DX-Y.NYB", "^VIX"], period="5d", interval="1d", progress=False, group_by="ticker")
        for sym, name in [("^TNX", "10Y Treasury Yield"), ("CL=F", "WTI Crude Oil"), ("DX-Y.NYB", "US Dollar (DXY)"), ("^VIX", "CBOE VIX")]:
            s_df = b_df[sym].dropna() if sym in b_df else pd.DataFrame()
            if not s_df.empty and len(s_df) >= 2:
                last_p = float(s_df['Close'].iloc[-1])
                prev_p = float(s_df['Close'].iloc[-2])
                chg = ((last_p - prev_p) / prev_p) * 100
                barometers[name] = (last_p, chg)
    except Exception:
        pass
    return barometers

@st.cache_data(ttl=180)
def fetch_institutional_profile(symbol):
    try:
        tk = yf.Ticker(symbol)
        hist_daily = tk.history(period="1y")
        if hist_daily.empty or len(hist_daily) < 50:
            return None
            
        hist_hourly = tk.history(period="5d", interval="60m")
        info = tk.info or {}
        
        prior_close = float(hist_daily['Close'].iloc[-2])
        today_reg = float(hist_daily['Close'].iloc[-1])
        
        real_time_now = None
        try:
            hist_live = tk.history(period="1d", interval="1m", prepost=True)
            if not hist_live.empty:
                real_time_now = float(hist_live['Close'].iloc[-1])
        except Exception:
            pass

        if real_time_now is None or real_time_now <= 0:
            try:
                real_time_now = float(tk.fast_info.get("last_price", 0.0))
                if real_time_now <= 0:
                    real_time_now = None
            except Exception:
                pass

        if real_time_now is None:
            post_p = info.get("postMarketPrice")
            pre_p = info.get("preMarketPrice")
            reg_p = info.get("regularMarketPrice")
            cur_cand = post_p or pre_p or reg_p or today_reg
            try:
                real_time_now = float(cur_cand)
            except (ValueError, TypeError):
                real_time_now = today_reg

        spot = real_time_now if real_time_now and real_time_now > 0 else today_reg
        dtn_str = f"${prior_close:.2f} / ${today_reg:.2f} / ${spot:.2f}"
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

        ema20 = float(hist_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(hist_daily['Close'].rolling(window=50).mean().iloc[-1])
        sma200 = float(hist_daily['Close'].rolling(window=200).mean().iloc[-1]) if len(hist_daily) >= 200 else np.nan
        
        if not np.isnan(sma200):
            q_bias = "Bullish" if (spot > sma50 and sma50 > sma200) else ("Bearish" if (spot < sma50 and sma50 < sma200) else "Neutral Consolidation")
        else:
            q_bias = "Bullish" if spot > sma50 else "Neutral"
            
        d_bias = "Strong Bull" if spot > ema20 * 1.015 else ("Bullish Pullback" if spot > ema20 else ("Bearish" if spot < ema20 * 0.985 else "Neutral Compression"))

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
            "Ticker": symbol, "Asset Name": asset_name, "1 D/T/N": dtn_str, "PEG ratio": peg_str,
            "Earnings Date": earnings_date, "Price-to-Earnings (P/E)": pe_str,
            "Quarterly Directional Bias": q_bias, "Daily Directional Bias": d_bias,
            "Market Profile / TPO Structure": tpo_structure, "Current POC / VPOC": f"${vpoc:.2f}",
            "Auction Dynamics": auction_dyn, "Support 1 (S1)": f"${s1:.2f}", "Support 2 (S2)": f"${s2:.2f}",
            "Support 3 (S3 / Macro Support)": f"${s3:.2f}", "Pivot / Fair Value (POC/HVN)": f"${pivot:.2f}",
            "Resistance 1 (R1)": f"${r1:.2f}", "Resistance 2 (R2)": f"${r2:.2f}",
            "Resistance 3 (R3 / Liquidity Target)": f"${r3:.2f}", "RSI (14)": f"{rsi:.1f}",
            "MACD Momentum": macd_str, "Options Volume": f"{opt_vol:,}" if opt_vol > 0 else "N/A",
            "Prior Stock Volume": f"{int(prior_vol):,}", "Put/Call Ratio (PCR)": f"{pcr:.2f}",
            "IV Rank (%)": f"{int(np.clip(ivr, 0, 100))}%", "Expected Move (+/-)": f"+/-${expected_move:.2f}",
            "Bull Trigger & Target": bull_trigger, "Bear Trigger & Target": bear_trigger,
            "30-Day Outlook Target": target_30d, "Raw_Spot": spot, "Raw_S1": s1, "Raw_R1": r1,
            "Raw_Earnings": earnings_date, "Raw_Bias": d_bias, "Raw_HV30": hv30, "Raw_EMA20": ema20,
            "Raw_SMA50": sma50, "Raw_SMA200": sma200, "Raw_RSI": rsi, "Raw_MACD": macd_val, "Raw_VPOC": vpoc
        }
    except Exception:
        return None

# --- OPTIONS WATERFALL SCANNER & GREEKS ENGINE ---
UNIFIED_20_COLS = [
    "Date", "Stock", "Earnings", "Support / Resist", "Strategy", "Expiry", 
    "Strikes Setup", "Premium", "Total Premium", "POP (%)", "Delta (Δ)", "Theta (θ)", 
    "Vol / OI", "Max Profit", "Max Loss", "Sold/Buy Idea", "Why Best Option", "Exit Trigger"
]

FULL_CREDIT_STRATEGIES = [
    "Bull Put Credit Spread ($5, $10, $15 Gap)",
    "Bear Call Credit Spread ($5, $10, $15 Gap)",
    "Iron Condor (POP > 70%)",
    "Iron Butterfly (High-Credit Pin)",
    "Covered Call / Buy-Write",
    "Cash-Secured Put (Target Buy)",
    "Jade Lizard (Zero Upside Risk)",
    "Short Strangle (High IV Seller)",
    "Short Straddle (Maximum Premium)"
]

FULL_DEBIT_STRATEGIES = [
    "Bull Call Debit Spread ($5, $10, $15 Gap)",
    "Bear Put Debit Spread ($5, $10, $15 Gap)",
    "Long Directional Single Call",
    "Long Directional Single Put",
    "Poor Man's Covered Call (PMCC)",
    "Long Call Calendar Spread",
    "Long Put Calendar Spread",
    "Long Straddle (Volatility Expansion)",
    "Long Strangle (Tail Risk Breakout)"
]

@st.cache_data(ttl=120)
def scan_waterfall_options(symbol, raw_spot, s1, r1, earnings_date, stock_prediction, dte_min=7, dte_max=15, hv30=35.0, target_strategy=None, target_book=None):
    tier1_candidates = []
    tier2_candidates = []
    try:
        tk = yf.Ticker(symbol)
        expiries = tk.options
        if not expiries:
            return []
            
        now = datetime.now()
        cur_date_str = now.strftime("%Y-%m-%d")

        target_exps = []
        for e in expiries:
            d = (datetime.strptime(e, "%Y-%m-%d") - now).days
            if dte_min <= d <= dte_max:
                target_exps.append((e, d))
                
        if len(target_exps) < 2:
            target_exps = [(e, (datetime.strptime(e, "%Y-%m-%d") - now).days) for e in expiries if 2 <= (datetime.strptime(e, "%Y-%m-%d") - now).days <= 35][:3]

        if not target_exps and expiries:
            target_exps = [(expiries[0], max((datetime.strptime(expiries[0], "%Y-%m-%d") - now).days, 1))]

        def get_clean_mid(row):
            if row.empty:
                return 0.0, 0, 0
            r = row.iloc[0]
            bid = float(r.get('bid', 0.0) or 0.0)
            ask = float(r.get('ask', 0.0) or 0.0)
            last = float(r.get('lastPrice', 0.0) or 0.0)
            vol = int(r.get('volume', 0) or 0)
            oi = int(r.get('openInterest', 0) or 0)
            mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else (last if last > 0 else 0.50)
            return round(mid, 2), vol, oi

        def get_nearest(df, target_k):
            if df.empty:
                return df
            return df.iloc[(df['strike'] - target_k).abs().argsort()[:1]]

        def approx_delta_theta(strike, spot, is_call, dte, iv):
            t = max(dte / 365.0, 0.01)
            sigma = max(iv / 100.0, 0.15)
            d1 = (math.log(max(spot, 0.01) / max(strike, 0.01)) + 0.5 * sigma**2 * t) / (sigma * math.sqrt(t))
            norm_cdf = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
            delta = norm_cdf if is_call else (norm_cdf - 1.0)
            theta = - (spot * sigma / (2 * math.sqrt(t) * math.sqrt(2 * math.pi))) * math.exp(-0.5 * d1**2) / 365.0
            return round(delta, 2), round(theta, 2)

        def matches_filter(strat_tag):
            if target_book == "Credit" and strat_tag in ["bull_call_debit", "bear_put_debit", "long_call", "long_put", "pmcc", "call_calendar", "put_calendar", "long_straddle", "long_strangle"]:
                return False
            if target_book == "Debit" and strat_tag not in ["bull_call_debit", "bear_put_debit", "long_call", "long_put", "pmcc", "call_calendar", "put_calendar", "long_straddle", "long_strangle"]:
                return False
            if not target_strategy:
                return True
            s = target_strategy.lower()
            tag = strat_tag.lower()
            if "iron condor" in s and tag == "iron_condor": return True
            if "iron butterfly" in s and tag == "iron_butterfly": return True
            if "bull put" in s and tag == "bull_put": return True
            if "bear call" in s and tag == "bear_call": return True
            if "cash-secured put" in s and tag == "cash_secured_put": return True
            if "covered call" in s and tag == "covered_call": return True
            if "jade lizard" in s and tag == "jade_lizard": return True
            if "short strangle" in s and tag == "short_strangle": return True
            if "short straddle" in s and tag == "short_straddle": return True
            if "bull call debit" in s and tag == "bull_call_debit": return True
            if "bear put debit" in s and tag == "bear_put_debit": return True
            if "single call" in s and tag == "long_call": return True
            if "single put" in s and tag == "long_put": return True
            if "poor man" in s and tag == "pmcc": return True
            if "call calendar" in s and tag == "call_calendar": return True
            if "put calendar" in s and tag == "put_calendar": return True
            if "long straddle" in s and tag == "long_straddle": return True
            if "long strangle" in s and tag == "long_strangle": return True
            return False

        for exp, dte in target_exps:
            try:
                chain = tk.option_chain(exp)
            except Exception:
                continue

            gap_list = [5.0, 10.0, 15.0]

            # 1. Bull Put Credit Spread
            if matches_filter("bull_put"):
                sp_row = get_nearest(chain.puts, raw_spot * 0.92)
                if not sp_row.empty:
                    s_k = float(sp_row.iloc[0]['strike'])
                    s_mid, s_vol, s_oi = get_clean_mid(sp_row)
                    s_delta, s_theta = approx_delta_theta(s_k, raw_spot, False, dte, hv30)
                    pop = int((1.0 - abs(s_delta)) * 100)
                    for g in gap_list:
                        lp_cands = chain.puts[chain.puts['strike'] < s_k]
                        if not lp_cands.empty:
                            lp_row = get_nearest(lp_cands, s_k - g)
                            l_k = float(lp_row.iloc[0]['strike'])
                            gap = s_k - l_k
                            if gap <= 0: continue
                            l_mid, _, _ = get_clean_mid(lp_row)
                            net_cr = max(round(s_mid - l_mid, 2), 0.15)
                            tot_cr = net_cr * 100
                            loss = round((gap - net_cr) * 100, 2)
                            rec = {
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                                "Strategy": f"Bull Put Spread (${gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "Strikes Setup": f"Sell ${s_k:.0f}P / Buy ${l_k:.0f}P",
                                "Premium": f"${net_cr:.2f}", "Total Premium": f"${tot_cr:.2f}",
                                "POP (%)": f"{pop}%", "Delta (Δ)": f"{s_delta:+.2f}", "Theta (θ)": f"${abs(s_theta)*100:.2f}/day",
                                "Vol / OI": f"{s_vol:,} / {s_oi:,}", "Max Profit": f"${tot_cr:.2f}", "Max Loss": f"${loss:.2f}",
                                "Sold/Buy Idea": f"Sell Put below S1 support (${s_k:.0f}P)",
                                "Why Best Option": f"Anchor below S1 support (${s1:.2f}). Captures theta decay over {dte} days with {pop}% probability.",
                                "Exit Trigger": f"Close at 50% max profit ($+{tot_cr*0.5:.0f}) or if spot breaches ${s_k:.0f}.",
                                "Raw_Spot": raw_spot, "Short_K": s_k, "Long_K": l_k, "Net_Prem": net_cr, "Spread_Width": gap, "Type": "Bull_Put"
                            }
                            meets_tier1 = (pop >= 80) and ((gap <= 6 and tot_cr > 200) or (gap <= 11 and tot_cr > 350) or (tot_cr > 500))
                            if meets_tier1: tier1_candidates.append({"score": net_cr / gap, "rec": rec})
                            else: tier2_candidates.append({"score": pop * (net_cr / gap), "rec": rec})

            # 2. Bear Call Credit Spread
            if matches_filter("bear_call"):
                sc_row = get_nearest(chain.calls, raw_spot * 1.08)
                if not sc_row.empty:
                    s_k = float(sc_row.iloc[0]['strike'])
                    s_mid, s_vol, s_oi = get_clean_mid(sc_row)
                    s_delta, s_theta = approx_delta_theta(s_k, raw_spot, True, dte, hv30)
                    pop = int((1.0 - abs(s_delta)) * 100)
                    for g in gap_list:
                        lc_cands = chain.calls[chain.calls['strike'] > s_k]
                        if not lc_cands.empty:
                            lc_row = get_nearest(lc_cands, s_k + g)
                            l_k = float(lc_row.iloc[0]['strike'])
                            gap = l_k - s_k
                            if gap <= 0: continue
                            l_mid, _, _ = get_clean_mid(lc_row)
                            net_cr = max(round(s_mid - l_mid, 2), 0.15)
                            tot_cr = net_cr * 100
                            loss = round((gap - net_cr) * 100, 2)
                            rec = {
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                                "Strategy": f"Bear Call Spread (${gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "Strikes Setup": f"Sell ${s_k:.0f}C / Buy ${l_k:.0f}C",
                                "Premium": f"${net_cr:.2f}", "Total Premium": f"${tot_cr:.2f}",
                                "POP (%)": f"{pop}%", "Delta (Δ)": f"{s_delta:+.2f}", "Theta (θ)": f"${abs(s_theta)*100:.2f}/day",
                                "Vol / OI": f"{s_vol:,} / {s_oi:,}", "Max Profit": f"${tot_cr:.2f}", "Max Loss": f"${loss:.2f}",
                                "Sold/Buy Idea": f"Sell Call above R1 resistance (${s_k:.0f}C)",
                                "Why Best Option": f"Anchor above R1 ceiling (${r1:.2f}). Captures theta decay over {dte} days with {pop}% probability.",
                                "Exit Trigger": f"Close at 50% max profit ($+{tot_cr*0.5:.0f}) or if stock reclaims ${s_k:.0f}.",
                                "Raw_Spot": raw_spot, "Short_K": s_k, "Long_K": l_k, "Net_Prem": net_cr, "Spread_Width": gap, "Type": "Bear_Call"
                            }
                            meets_tier1 = (pop >= 80) and ((gap <= 6 and tot_cr > 200) or (gap <= 11 and tot_cr > 350) or (tot_cr > 500))
                            if meets_tier1: tier1_candidates.append({"score": net_cr / gap, "rec": rec})
                            else: tier2_candidates.append({"score": pop * (net_cr / gap), "rec": rec})

            # 3. Iron Condor
            if matches_filter("iron_condor"):
                sp_row = get_nearest(chain.puts, raw_spot * 0.92)
                sc_row = get_nearest(chain.calls, raw_spot * 1.08)
                if not sp_row.empty and not sc_row.empty:
                    s_p = float(sp_row.iloc[0]['strike'])
                    s_c = float(sc_row.iloc[0]['strike'])
                    sp_mid, sp_vol, sp_oi = get_clean_mid(sp_row)
                    sc_mid, sc_vol, sc_oi = get_clean_mid(sc_row)
                    for g in [5.0, 10.0, 15.0]:
                        lp_cands = chain.puts[chain.puts['strike'] < s_p]
                        lc_cands = chain.calls[chain.calls['strike'] > s_c]
                        if not lp_cands.empty and not lc_cands.empty:
                            lp_row = get_nearest(lp_cands, s_p - g)
                            lc_row = get_nearest(lc_cands, s_c + g)
                            l_p = float(lp_row.iloc[0]['strike'])
                            l_c = float(lc_row.iloc[0]['strike'])
                            wing = min(s_p - l_p, l_c - s_c)
                            if wing <= 0: continue
                            lp_mid, _, _ = get_clean_mid(lp_row)
                            lc_mid, _, _ = get_clean_mid(lc_row)
                            cr_p = max(round(sp_mid - lp_mid, 2), 0.10)
                            cr_c = max(round(sc_mid - lc_mid, 2), 0.10)
                            tot_cr = round((cr_p + cr_c) * 100, 2)
                            loss = round((wing * 100) - tot_cr, 2)
                            p_delta, p_theta = approx_delta_theta(s_p, raw_spot, False, dte, hv30)
                            c_delta, c_theta = approx_delta_theta(s_c, raw_spot, True, dte, hv30)
                            pop = max(min(int((1.0 - (abs(p_delta) + abs(c_delta))) * 100), 88), 68)
                            rec = {
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                                "Strategy": f"Iron Condor (${wing:.0f} Wings)", "Expiry": f"{exp} ({dte}d)",
                                "Strikes Setup": f"${l_p:.0f}P / ${s_p:.0f}P || ${s_c:.0f}C / ${l_c:.0f}C",
                                "Premium": f"${(cr_p + cr_c):.2f}", "Total Premium": f"${tot_cr:.2f}",
                                "POP (%)": f"{pop}%", "Delta (Δ)": f"{c_delta + p_delta:+.2f}", "Theta (θ)": f"${abs(p_theta + c_theta)*100:.2f}/day",
                                "Vol / OI": f"{sp_vol + sc_vol:,} / {sp_oi + sc_oi:,}", "Max Profit": f"${tot_cr:.2f}", "Max Loss": f"${loss:.2f}",
                                "Sold/Buy Idea": f"Range-Bound Theta Harvest between ${s_p:.0f} and ${s_c:.0f}",
                                "Why Best Option": f"Stock is boxed inside S1 (${s1:.2f}) and R1 (${r1:.2f}). Both wings harvest theta decay with {pop}% probability.",
                                "Exit Trigger": f"Close at 50% max profit ($+{tot_cr*0.5:.0f}) or 21 DTE.",
                                "Raw_Spot": raw_spot, "Short_P": s_p, "Long_P": l_p, "Short_C": s_c, "Long_C": l_c, "Net_Prem": cr_p + cr_c, "Wing": wing, "Type": "Iron_Condor"
                            }
                            meets_tier1 = (pop >= 70) and ((wing <= 6 and tot_cr > 200) or (wing <= 11 and tot_cr > 350) or (tot_cr > 500))
                            if meets_tier1: tier1_candidates.append({"score": (cr_p + cr_c) / wing, "rec": rec})
                            else: tier2_candidates.append({"score": pop * ((cr_p + cr_c) / wing), "rec": rec})

            # 4. Cash-Secured Put
            if matches_filter("cash_secured_put"):
                csp_row = get_nearest(chain.puts, raw_spot * 0.90)
                if not csp_row.empty:
                    k = float(csp_row.iloc[0]['strike'])
                    mid, vol, oi = get_clean_mid(csp_row)
                    delta, theta = approx_delta_theta(k, raw_spot, False, dte, hv30)
                    pop = int((1.0 - abs(delta)) * 100)
                    tot_p = mid * 100
                    rec = {
                        "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                        "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                        "Strategy": "Cash-Secured Put (Target Buy)", "Expiry": f"{exp} ({dte}d)",
                        "Strikes Setup": f"Sell 1x ${k:.0f} Put",
                        "Premium": f"${mid:.2f}", "Total Premium": f"${tot_p:.2f}",
                        "POP (%)": f"{pop}%", "Delta (Δ)": f"{delta:+.2f}", "Theta (θ)": f"${abs(theta)*100:.2f}/day",
                        "Vol / OI": f"{vol:,} / {oi:,}", "Max Profit": f"${tot_p:.2f}", "Max Loss": f"${round((k - mid)*100, 2):.2f}",
                        "Sold/Buy Idea": f"Acquire high-quality shares at ${k - mid:.2f} effective price",
                        "Why Best Option": f"Discount bid placed below S1 support. High volume/open interest safety buffer.",
                        "Exit Trigger": f"Roll forward if spot approaches ${k:.0f} or take profit at 60% decay.",
                        "Raw_Spot": raw_spot, "Short_K": k, "Net_Prem": mid, "Type": "CSP"
                    }
                    if pop >= 80 and tot_p >= 200: tier1_candidates.append({"score": mid / k, "rec": rec})
                    else: tier2_candidates.append({"score": pop * (mid / k), "rec": rec})

            # 5. Covered Call
            if matches_filter("covered_call"):
                cc_row = get_nearest(chain.calls, raw_spot * 1.06)
                if not cc_row.empty:
                    k = float(cc_row.iloc[0]['strike'])
                    mid, vol, oi = get_clean_mid(cc_row)
                    delta, theta = approx_delta_theta(k, raw_spot, True, dte, hv30)
                    pop = int((1.0 - abs(delta)) * 100)
                    tot_p = mid * 100
                    rec = {
                        "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                        "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                        "Strategy": "Covered Call (Yield Harvest)", "Expiry": f"{exp} ({dte}d)",
                        "Strikes Setup": f"Sell 1x ${k:.0f} Call",
                        "Premium": f"${mid:.2f}", "Total Premium": f"${tot_p:.2f}",
                        "POP (%)": f"{pop}%", "Delta (Δ)": f"{delta:+.2f}", "Theta (θ)": f"${abs(theta)*100:.2f}/day",
                        "Vol / OI": f"{vol:,} / {oi:,}", "Max Profit": f"${round((k - raw_spot + mid)*100, 2):.2f}", 
                        "Max Loss": f"${round((raw_spot - mid)*100, 2):.2f}",
                        "Sold/Buy Idea": f"Yield extraction against 100 shares capped at ${k:.0f}",
                        "Why Best Option": f"Monetizes sideways tape. Capped upside to ${k:.0f} with ${mid:.2f} downside buffer.",
                        "Exit Trigger": f"Let expire if below ${k:.0f} or buy back at 80% profit.",
                        "Raw_Spot": raw_spot, "Short_K": k, "Net_Prem": mid, "Type": "Covered_Call"
                    }
                    if pop >= 80 and tot_p >= 200: tier1_candidates.append({"score": mid / raw_spot, "rec": rec})
                    else: tier2_candidates.append({"score": pop * (mid / raw_spot), "rec": rec})

            # 6. Bull Call Debit Spread
            if matches_filter("bull_call_debit"):
                bcd_row = get_nearest(chain.calls, raw_spot * 1.01)
                if not bcd_row.empty:
                    l_k = float(bcd_row.iloc[0]['strike'])
                    l_mid, l_vol, l_oi = get_clean_mid(bcd_row)
                    for g in [5.0, 10.0, 15.0]:
                        s_cands = chain.calls[chain.calls['strike'] > l_k]
                        if not s_cands.empty:
                            s_row = get_nearest(s_cands, l_k + g)
                            s_k = float(s_row.iloc[0]['strike'])
                            gap = s_k - l_k
                            if gap <= 0: continue
                            s_mid, _, _ = get_clean_mid(s_row)
                            net_deb = max(round(l_mid - s_mid, 2), 0.30)
                            max_p = round((gap - net_deb) * 100, 2)
                            l_delta, l_theta = approx_delta_theta(l_k, raw_spot, True, dte, hv30)
                            pop = int(abs(l_delta) * 100)
                            rec = {
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                                "Strategy": f"Bull Call Debit Spread (${gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "Strikes Setup": f"Buy ${l_k:.0f}C / Sell ${s_k:.0f}C",
                                "Premium": f"${net_deb:.2f}", "Total Premium": f"${net_deb * 100:.2f}",
                                "POP (%)": f"{pop}%", "Delta (Δ)": f"{l_delta:+.2f}", "Theta (θ)": f"-${abs(l_theta)*100:.2f}/day",
                                "Vol / OI": f"{l_vol:,} / {l_oi:,}", "Max Profit": f"${max_p:.2f}", "Max Loss": f"${net_deb * 100:.2f}",
                                "Sold/Buy Idea": f"Bullish Breakout Leverage above ${l_k:.0f}",
                                "Why Best Option": f"Asymmetric 40:60 risk-reward leverage setup. Limited risk targeting +${max_p:.0f} upside.",
                                "Exit Trigger": f"Exit if stock touches ${s_k:.0f} or cut loss if spot drops below S1.",
                                "Raw_Spot": raw_spot, "Long_K": l_k, "Short_K": s_k, "Net_Prem": net_deb, "Spread_Width": gap, "Type": "Bull_Call_Debit"
                            }
                            if max_p >= 200: tier1_candidates.append({"score": max_p / (net_deb * 100), "rec": rec})
                            else: tier2_candidates.append({"score": max_p / (net_deb * 100), "rec": rec})

            # 7. Bear Put Debit Spread
            if matches_filter("bear_put_debit"):
                bpd_row = get_nearest(chain.puts, raw_spot * 0.99)
                if not bpd_row.empty:
                    l_k = float(bpd_row.iloc[0]['strike'])
                    l_mid, l_vol, l_oi = get_clean_mid(bpd_row)
                    for g in [5.0, 10.0, 15.0]:
                        s_cands = chain.puts[chain.puts['strike'] < l_k]
                        if not s_cands.empty:
                            s_row = get_nearest(s_cands, l_k - g)
                            s_k = float(s_row.iloc[0]['strike'])
                            gap = l_k - s_k
                            if gap <= 0: continue
                            s_mid, _, _ = get_clean_mid(s_row)
                            net_deb = max(round(l_mid - s_mid, 2), 0.30)
                            max_p = round((gap - net_deb) * 100, 2)
                            l_delta, l_theta = approx_delta_theta(l_k, raw_spot, False, dte, hv30)
                            pop = int(abs(l_delta) * 100)
                            rec = {
                                "Date": cur_date_str, "Stock": symbol, "Earnings": earnings_date,
                                "Support / Resist": f"S1: ${s1:.2f} | R1: ${r1:.2f}",
                                "Strategy": f"Bear Put Debit Spread (${gap:.0f} Gap)", "Expiry": f"{exp} ({dte}d)",
                                "Strikes Setup": f"Buy ${l_k:.0f}P / Sell ${s_k:.0f}P",
                                "Premium": f"${net_deb:.2f}", "Total Premium": f"${net_deb * 100:.2f}",
                                "POP (%)": f"{pop}%", "Delta (Δ)": f"{l_delta:+.2f}", "Theta (θ)": f"-${abs(l_theta)*100:.2f}/day",
                                "Vol / OI": f"{l_vol:,} / {l_oi:,}", "Max Profit": f"${max_p:.2f}", "Max Loss": f"${net_deb * 100:.2f}",
                                "Sold/Buy Idea": f"Directional Breakdown hedge below S1",
                                "Why Best Option": f"Asymmetric breakdown hedge with capped downside risk (${net_deb * 100:.0f}).",
                                "Exit Trigger": f"Exit if stock hits ${s_k:.0f} or cut loss if spot breaks above R1.",
                                "Raw_Spot": raw_spot, "Long_K": l_k, "Short_K": s_k, "Net_Prem": net_deb, "Spread_Width": gap, "Type": "Bear_Put_Debit"
                            }
                            if max_p >= 200: tier1_candidates.append({"score": max_p / (net_deb * 100), "rec": rec})
                            else: tier2_candidates.append({"score": max_p / (net_deb * 100), "rec": rec})

        tier1_sorted = sorted(tier1_candidates, key=lambda x: x["score"], reverse=True)
        tier2_sorted = sorted(tier2_candidates, key=lambda x: x["score"], reverse=True)

        quota = 5 if target_book else (2 if target_strategy else 5)
        final_picks = [t["rec"] for t in tier1_sorted[:quota]]
        
        needed = quota - len(final_picks)
        if needed > 0:
            for item in tier2_sorted:
                cand = item["rec"]
                if not any(f["Strikes Setup"] == cand["Strikes Setup"] for f in final_picks):
                    cand["Strategy"] = f"[Next Best] {cand['Strategy']}"
                    final_picks.append(cand)
                if len(final_picks) >= quota:
                    break

        return final_picks
    except Exception:
        return []

# --- INTERACTIVE PROFIT CURVE VISUALIZER ---
def render_profit_chart(setup):
    st_type = setup.get("Type", "")
    spot = setup.get("Raw_Spot", 100.0)
    prices = np.linspace(spot * 0.80, spot * 1.20, 100)
    payoff = np.zeros_like(prices)

    if st_type == "Bull_Put":
        s_k = setup["Short_K"]
        l_k = setup["Long_K"]
        cr = setup["Net_Prem"]
        payoff = np.where(prices >= s_k, cr * 100, np.where(prices <= l_k, (cr - (s_k - l_k)) * 100, (cr - (s_k - prices)) * 100))
    elif st_type == "Bear_Call":
        s_k = setup["Short_K"]
        l_k = setup["Long_K"]
        cr = setup["Net_Prem"]
        payoff = np.where(prices <= s_k, cr * 100, np.where(prices >= l_k, (cr - (l_k - s_k)) * 100, (cr - (prices - s_k)) * 100))
    elif st_type == "Iron_Condor":
        s_p = setup["Short_P"]
        l_p = setup["Long_P"]
        s_c = setup["Short_C"]
        l_c = setup["Long_C"]
        cr = setup["Net_Prem"]
        w = setup["Wing"]
        payoff = np.where((prices >= s_p) & (prices <= s_c), cr * 100,
                 np.where(prices <= l_p, (cr - w) * 100,
                 np.where(prices >= l_c, (cr - w) * 100,
                 np.where(prices < s_p, (cr - (s_p - prices)) * 100, (cr - (prices - s_c)) * 100))))
    elif st_type == "CSP":
        k = setup["Short_K"]
        cr = setup["Net_Prem"]
        payoff = np.where(prices >= k, cr * 100, (cr - (k - prices)) * 100)
    elif st_type == "Covered_Call":
        k = setup["Short_K"]
        cr = setup["Net_Prem"]
        payoff = np.where(prices >= k, (k - spot + cr) * 100, (prices - spot + cr) * 100)
    elif st_type == "Bull_Call_Debit":
        l_k = setup["Long_K"]
        s_k = setup["Short_K"]
        deb = setup["Net_Prem"]
        w = setup["Spread_Width"]
        payoff = np.where(prices <= l_k, -deb * 100, np.where(prices >= s_k, (w - deb) * 100, (prices - l_k - deb) * 100))
    elif st_type == "Bear_Put_Debit":
        l_k = setup["Long_K"]
        s_k = setup["Short_K"]
        deb = setup["Net_Prem"]
        w = setup["Spread_Width"]
        payoff = np.where(prices >= l_k, -deb * 100, np.where(prices <= s_k, (w - deb) * 100, (l_k - prices - deb) * 100))
    else:
        payoff = np.where(prices >= spot, 150, -150)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prices, y=payoff, mode='lines', line=dict(color='#00c853', width=2.5), name='Expiration P&L ($)'))
    fig.add_hline(y=0, line_dash="dash", line_color="#718096")
    fig.add_vline(x=spot, line_dash="dot", line_color="#3b82f6", annotation_text=f"Spot: ${spot:.2f}")
    fig.update_layout(
        title=f"Theoretical Expiration Profit/Loss Profile: {setup['Strategy']}",
        xaxis_title="Underlying Price ($)",
        yaxis_title="Profit / Loss ($)",
        template="plotly_dark",
        height=320,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- ADVANCED CANDLESTICK & TECHNICAL STACK SUITE ---
def render_full_technical_suite(symbol, meta):
    tk = yf.Ticker(symbol)
    df = tk.history(period="1y", interval="1d")
    if df.empty or len(df) < 50:
        st.warning(f"Insufficient technical history for {symbol}.")
        return

    # Moving Averages
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()

    # Bollinger Bands
    bb_mid = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = bb_mid + (2 * bb_std)
    df['BB_Lower'] = bb_mid - (2 * bb_std)

    # Momentum Oscillators (RSI & MACD)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    recent_df = df.tail(120)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(f"{symbol} Technical Workspace (EMA20, SMA50, SMA200, Bollinger & S/R)", "RSI (14) & MACD Momentum", "Volume & 20-Day Average")
    )

    # Panel 1: Candlesticks & Overlays
    fig.add_trace(go.Candlestick(
        x=recent_df.index, open=recent_df['Open'], high=recent_df['High'],
        low=recent_df['Low'], close=recent_df['Close'], name="Candlestick",
        increasing_line_color='#00c853', decreasing_line_color='#ff3b30'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['BB_Upper'], line=dict(color='rgba(148, 163, 184, 0.35)', dash='dot'), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['BB_Lower'], line=dict(color='rgba(148, 163, 184, 0.35)', dash='dot'), fill='tonexty', fillcolor='rgba(148, 163, 184, 0.05)', name="BB Lower"), row=1, col=1)

    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['EMA20'], line=dict(color='#00e5ff', width=1.5), name="20 EMA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['SMA50'], line=dict(color='#3b82f6', width=1.5), name="50 SMA"), row=1, col=1)
    if not recent_df['SMA200'].isna().all():
        fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['SMA200'], line=dict(color='#f59e0b', width=1.5), name="200 SMA"), row=1, col=1)

    s1 = meta["Raw_S1"]
    r1 = meta["Raw_R1"]
    vpoc = meta["Raw_VPOC"]
    fig.add_hline(y=s1, line_dash="dash", line_color="#00c853", annotation_text=f"S1: ${s1:.2f}", row=1, col=1)
    fig.add_hline(y=r1, line_dash="dash", line_color="#ff3b30", annotation_text=f"R1: ${r1:.2f}", row=1, col=1)
    fig.add_hline(y=vpoc, line_dash="solid", line_color="#fbbf24", annotation_text=f"VPOC: ${vpoc:.2f}", row=1, col=1)

    # Panel 2: RSI
    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['RSI'], line=dict(color='#a855f7', width=1.5), name="RSI (14)"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#ff3b30", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#00c853", row=2, col=1)

    # Panel 3: Volume
    vol_colors = ['#00c853' if row['Close'] >= row['Open'] else '#ff3b30' for _, row in recent_df.iterrows()]
    fig.add_trace(go.Bar(x=recent_df.index, y=recent_df['Volume'], marker_color=vol_colors, name="Volume"), row=3, col=1)
    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['Vol_SMA20'], line=dict(color='#eab308', width=1.5), name="20-Day Vol MA"), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=680,
        margin=dict(l=20, r=20, t=30, b=20),
        hovermode="x unified"
    )
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot", spikecolor="#94a3b8")
    fig.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot", spikecolor="#94a3b8")

    st.plotly_chart(fig, use_container_width=True)

    # Automated Short-Term vs. Long-Term Directional Engine
    spot = meta["Raw_Spot"]
    ema20 = meta["Raw_EMA20"]
    sma50 = meta["Raw_SMA50"]
    sma200 = meta.get("Raw_SMA200", np.nan)
    rsi_val = meta["Raw_RSI"]
    macd_val = meta["Raw_MACD"]

    if spot > ema20 and rsi_val >= 50 and macd_val > 0:
        st_bias = "🟢 Bullish Expansion"
        st_target = f"${meta['Raw_R1']:.2f}"
        st_stop = f"${meta['Raw_EMA20']:.2f}"
        st_reason = f"Price is riding above rising 20 EMA with positive MACD momentum. Constructive bounce above S1 (${s1:.2f}) targets immediate overhead test at R1."
    elif spot < ema20 and rsi_val < 45:
        st_bias = "🔴 Bearish Breakdown"
        st_target = f"${meta['Raw_S1']:.2f}"
        st_stop = f"${meta['Raw_EMA20']:.2f}"
        st_reason = f"Loss of short-term 20 EMA support and weakening RSI ({rsi_val:.1f}) indicate downside distribution pressure toward S1."
    else:
        st_bias = "🟡 Neutral Consolidation / Squeeze"
        st_target = f"${meta['Raw_VPOC']:.2f}"
        st_stop = f"${meta['Raw_S1']:.2f}"
        st_reason = f"Price is compressing within the Bollinger Band pocket between EMA 20 and VPOC (${vpoc:.2f}). Range-bound theta harvesting favored."

    if not np.isnan(sma200) and spot > sma200 and sma50 > sma200:
        lt_bias = "🟢 Structural Bull Market"
        lt_target = f"${round(spot * 1.15, 2):.2f}"
        lt_support = f"${sma200:.2f} (200 SMA)"
        lt_reason = "Golden cross intact with price well above 200-day moving average. Institutional long-term accumulation cycle remains dominant."
    elif not np.isnan(sma200) and spot < sma200:
        lt_bias = "🔴 Structural Macro Overhead"
        lt_target = f"${meta['Raw_S1']:.2f}"
        lt_support = f"${meta['Raw_S1']:.2f}"
        lt_reason = "Price remains suppressed under the 200 SMA discount hurdle. Broader macro headwinds favor defensive spreads and hedging."
    else:
        lt_bias = "🟡 Multi-Month Transition"
        lt_target = f"${meta['Raw_R1']:.2f}"
        lt_support = f"${meta['Raw_S1']:.2f}"
        lt_reason = "Stock is cycling between medium-term moving average ribbons without macro trend confirmation."

    st.markdown("### 🔮 Algorithmic Trend Forecast & Predictive Intelligence")
    pred_col1, pred_col2 = st.columns(2, gap="large")

    with pred_col1:
        st.markdown(f"""
        <div class="index-card">
            <div style="font-size: 1.1rem; font-weight: 700; color: #60a5fa;">⚡ Short-Term Outlook (1 to 14 Days)</div>
            <div style="font-size: 1.3rem; font-weight: 800; margin: 6px 0;">{st_bias}</div>
            <div><b>Upside Target:</b> {st_target} | <b>Trailing Stop / Pivot:</b> {st_stop}</div>
            <div style="margin-top: 6px; font-size: 0.9rem; color: #cbd5e1;">{st_reason}</div>
        </div>
        """, unsafe_allow_html=True)

    with pred_col2:
        st.markdown(f"""
        <div class="index-card">
            <div style="font-size: 1.1rem; font-weight: 700; color: #f59e0b;">🏛️ Long-Term Outlook (30 to 90+ Days)</div>
            <div style="font-size: 1.3rem; font-weight: 800; margin: 6px 0;">{lt_bias}</div>
            <div><b>Macro Target:</b> {lt_target} | <b>Structural Support:</b> {lt_support}</div>
            <div style="margin-top: 6px; font-size: 0.9rem; color: #cbd5e1;">{lt_reason}</div>
        </div>
        """, unsafe_allow_html=True)

# ========================================================
# LEFT PANEL NAVIGATION MENU (ENTERPRISE LIST STYLE)
# ========================================================
if "current_view" not in st.session_state:
    st.session_state.current_view = "Dashboard Landing"

st.sidebar.markdown("""
<div class="nav-header">
    <span>🧭 Portal Navigation</span>
    <span style="font-size: 0.8rem; background-color: #3b82f6; padding: 2px 8px; border-radius: 10px;">6 Views</span>
</div>
""", unsafe_allow_html=True)

# Left Panel Stacked Navigation Buttons with Count Badges
nav_items = [
    ("Dashboard Landing", "📊 Dashboard Landing", "Live"),
    ("Daily Brief", "📰 Daily Brief", "3"),
    ("Market Brief", "🌐 Market Brief", "4"),
    ("Watchlist & Options", "📋 Watchlist & Options", str(len(st.session_state.watchlist))),
    ("Options Execution Hub", "🎯 Options Execution Hub", "18"),
    ("Watchlist Manager", "⚙️ Watchlist Manager", "Config")
]

for key_name, display_label, badge_val in nav_items:
    btn_text = f"{display_label}  ({badge_val})"
    if st.sidebar.button(btn_text, key=f"nav_btn_{key_name}", use_container_width=True):
        st.session_state.current_view = key_name
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("⚡ Institutional Terminal | Multi-Asset Options Engine")

# ========================================================
# VIEW 1: DASHBOARD LANDING
# ========================================================
if st.session_state.current_view == "Dashboard Landing":
    st.title("⚡ Institutional Derivatives Cockpit & Market Control")
    st.caption(f"Quantitative Intelligence Framework | Live Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Top Benchmark Barometers
    index_data = fetch_top_indices()
    if index_data:
        idx_cols = st.columns(len(index_data))
        for i, sym in enumerate(["SPY", "QQQ", "DIA", "IWM", "^VIX", "GLD", "TLT"]):
            if sym in index_data:
                m = index_data[sym]
                with idx_cols[i]:
                    st.metric(label=f"{sym} ({m['bias']})", value=f"${m['price']:.2f}", delta=f"{m['chg']:+.2f}%")

    st.markdown("---")

    # Middle Ticker Search
    s_col1, s_col2 = st.columns([3, 1])
    with s_col1:
        searched_sym = st.text_input("🔍 Quick Ticker Search", value="AMD", placeholder="Enter Ticker Symbol (e.g., AMD, NVDA, APP, NOW)...", key="dash_sym_input").strip().upper()
    with s_col2:
        st.write("")
        st.write("")
        run_search = st.button("Analyze Ticker", use_container_width=True, key="dash_sym_btn")

    if searched_sym:
        meta = fetch_institutional_profile(searched_sym)
        if meta:
            st.markdown(f"### 📈 Institutional Profile: `{meta['Ticker']}` ({meta['Asset Name']})")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("1 D / T / N Spot Resolution", meta["1 D/T/N"])
            c2.metric("Short-Term Trend", meta["Daily Directional Bias"], f"20 EMA: ${meta['Raw_EMA20']:.2f}")
            c3.metric("Macro Trend (SMA 200)", meta["Quarterly Directional Bias"], f"50 SMA: ${meta['Raw_SMA50']:.2f}")
            c4.metric("Implied Volatility Rank", meta["IV Rank (%)"], f"Expected Move: {meta['Expected Move (+/-)']}")

            # 3-Subplot Candlestick Suite
            render_full_technical_suite(searched_sym, meta)
        else:
            st.error(f"Unable to retrieve technical market profile for '{searched_sym}'. Please verify ticker.")

# ========================================================
# VIEW 2: DAILY BRIEF (EDITOR-IN-CHIEF WIDGET DESK)
# ========================================================
elif st.session_state.current_view == "Daily Brief":
    st.title("📰 Daily Executive News Desk")
    st.caption("Chief Editor's Review: High-level world summaries with click-to-open investigative dispatches.")

    w1_col, w2_col, w3_col = st.columns(3, gap="medium")

    with w1_col:
        st.markdown(f"""
        <div class="index-card">
            <h3>🏛️ World & Geopolitics</h3>
            <p>Diplomatic talks navigate critical security corridors across the Middle East and Red Sea trade routes. 
            Escalating shipping insurance costs directly impact international crude logistics and manufacturing supply chains. 
            Western defense coalitions continue prioritizing long-range infrastructure defense and energy grid security. 
            Legislative leadership in major capitals reviews fiscal defense appropriations ahead of upcoming summits.</p>
        </div>
        """, unsafe_allow_html=True)
        open_geo = st.button("📖 Read World Dispatch", key="btn_geo", use_container_width=True)

    with w2_col:
        st.markdown(f"""
        <div class="index-card">
            <h3>🏆 Global Sports Pulse</h3>
            <p>Major professional franchises enter decisive championship qualification periods with high stakes. 
            Multi-billion-dollar sports media rights packages accelerate direct-to-consumer digital broadcast transitions. 
            Regulatory athletic bodies update governance protocols regarding institutional capital ownership in major leagues. 
            Global sports tourism metrics reflect sustained double-digit growth heading into international tournaments.</p>
        </div>
        """, unsafe_allow_html=True)
        open_sport = st.button("📖 Read Sports Dispatch", key="btn_sport", use_container_width=True)

    with w3_col:
        st.markdown(f"""
        <div class="index-card">
            <h3>🎬 Culture & Entertainment</h3>
            <p>Major Hollywood studios and global streaming platforms recalibrate production capital toward established intellectual property. 
            Creative unions and production houses operationalize new workflow frameworks regarding enterprise AI in post-production. 
            Global cinema box office receipts demonstrate stability, supported by international co-productions and premium formats. 
            Film festival circuits highlight independent international narratives competing for annual award season nominations.</p>
        </div>
        """, unsafe_allow_html=True)
        open_ent = st.button("📖 Read Entertainment Dispatch", key="btn_ent", use_container_width=True)

    # In-Depth Dispatches
    if open_geo:
        st.markdown("""
        <div class="dispatch-box">
            <h4>📑 In-Depth Dispatch: Geopolitics, Supply Lines & Defense Logistics</h4>
            <p><b>Strategic Assessment:</b> Global naval coalitions continue coordinating commercial convoy protection operations through the Bab-el-Mandeb and Red Sea transit lanes. The prolonged rerouting of ultra-large container vessels around the Cape of Good Hope has permanently added 10 to 14 days to standard Asian-European maritime transit times, solidifying a structural floor underneath international freight rates and marine bunker fuel consumption.</p>
            <p><b>Macroeconomic Spillovers:</b> Insurance underwriters in London have maintained elevated war-risk premiums for tankers traversing the Persian Gulf. In response, energy importing economies in the Indo-Pacific have expanded strategic petroleum reserves while accelerating bilateral pipeline arrangements across Central Asia.</p>
            <p><b>Diplomatic Horizon:</b> G20 diplomatic envoys meeting ahead of upcoming trade ministerial sessions are navigating complex tariff debates, with Western leadership emphasizing trade derisking while emerging manufacturing hubs advocate for multilateral tariff pauses.</p>
        </div>
        """, unsafe_allow_html=True)

    if open_sport:
        st.markdown("""
        <div class="dispatch-box">
            <h4>📑 In-Depth Dispatch: Franchise Valuations & Media Rights Transition</h4>
            <p><b>Commercial Landscape:</b> The economics of global athletic franchises are undergoing rapid transformation as institutional private equity capital enters top-flight football, basketball, and racing organizations. Broadcast networks are transitioning high-margin live sporting events into proprietary subscription streaming tiers, driving record customer acquisition while increasing consumer cord-cutting velocities.</p>
            <p><b>Roster Dynamics:</b> Labor associations across major North American leagues are finalizing salary cap adjustments linked to expanding international broadcast revenue. As team valuations cross multi-billion-dollar milestones, front offices are prioritizing data-driven player analytics and biomechanical monitoring systems to optimize player longevity.</p>
        </div>
        """, unsafe_allow_html=True)

    if open_ent:
        st.markdown("""
        <div class="dispatch-box">
            <h4>📑 In-Depth Dispatch: The Entertainment Industry Capital Realignment</h4>
            <p><b>Studio Strategy:</b> Following years of aggressive capital expenditure dedicated to subscriber expansion, media conglomerates have pivoted toward operating profit margins and disciplined content expenditure. Major theatrical studios are relying on established cinematic universes and IMAX releases, which continue capturing a disproportionate share of global box office revenue.</p>
            <p><b>Technology & Licensing:</b> Creative guilds and production houses have established formal governance frameworks regarding generative visual workflows. Visual effects houses are deploying neural rendering and computer vision tools for background compositing while strictly maintaining copyright provenance on all character assets.</p>
        </div>
        """, unsafe_allow_html=True)

# ========================================================
# VIEW 3: MARKET BRIEF (MACRO DRIVERS)
# ========================================================
elif st.session_state.current_view == "Market Brief":
    st.title("🌐 World Market Drivers & Catalysts")
    st.caption("Systemic macroeconomic outlook: What is impacting the US equity tape today.")

    barometers = fetch_macro_catalysts()
    if barometers:
        b_cols = st.columns(len(barometers))
        for i, (name, (val, chg)) in enumerate(barometers.items()):
            prefix = "$" if "Crude" in name else ""
            suffix = "%" if "Yield" in name else ""
            with b_cols[i]:
                st.metric(label=name, value=f"{prefix}{val:.2f}{suffix}", delta=f"{chg:+.2f}%")

    st.markdown("---")
    m_left, m_right = st.columns([1, 1], gap="large")

    with m_left:
        st.subheader("🏛️ Core Catalysts to Watch Today")
        st.markdown("""
        * **Federal Reserve Monetary Posture:** Regional Fed leadership pushes back against rapid rate reductions. **Impact:** Caps valuation multiples on high-beta growth equities.
        * **10-Year Treasury Yield Pressures:** Benchmark yields hovering near key hurdles directly raise corporate equity borrowing costs and discount rates.
        * **Energy & Fuel Input Overhead:** Crude oil supply resilience tests headline inflation metrics and logistics expenses worldwide.
        * **US Dollar Index (DXY) Strength:** Currency valuation resilience acts as an earnings translation headwind for multinational blue chips.
        * **Enterprise Datacenter Capex Scrutiny:** Institutional scrutiny over whether hardware investments convert into immediate operating margins across mega-cap guidance.
        """)

    with m_right:
        st.subheader("📅 High-Impact Macro Schedule")
        catalysts = [
            {"Event": "September CPI Inflation Print", "Schedule": "8:30 AM EDT", "Context": "Headline CPI MoM", "Market Impact": "Cooler = Tech relief rally; Hotter = Equity sell-off."},
            {"Event": "Federal Reserve Beige Book", "Schedule": "2:00 PM EDT", "Context": "Regional Economic Readout", "Market Impact": "Wage cooling confirms pause; stickiness reignites rate worries."},
            {"Event": "US Retail Sales Data", "Schedule": "8:30 AM EDT", "Context": "Consumer Resilience", "Market Impact": "High read confirms soft landing; low read sparks recession fears."},
            {"Event": "FOMC Interest Rate Decision", "Schedule": "2:00 PM EDT", "Context": "Target Rate & Press Conference", "Market Impact": "Establishes year-end institutional liquidity trajectory."}
        ]
        st.dataframe(pd.DataFrame(catalysts), use_container_width=True, hide_index=True)

# ========================================================
# VIEW 4: WATCHLIST & DYNAMIC OPTION ANALYZER
# ========================================================
elif st.session_state.current_view == "Watchlist & Options":
    st.title("📋 Master Watchlist & Options Analyzer")
    st.caption("Institutional Review Matrix with Dynamic Top 5 Credit & Top 5 Debit Setup Extractors.")

    with st.spinner("Compiling institutional review matrix across active watchlist..."):
        review_rows = []
        for sym in st.session_state.watchlist:
            d = fetch_institutional_profile(sym)
            if d: review_rows.append(d)

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

        selected_ticker = st.selectbox("🎯 Select Stock to Drill Down Top 10 Options:", options=sorted(list(display_df["Ticker"].unique())), key="w_ticker_sel")
        
        filtered_master_df = filter_dataframe(display_df, key_prefix="w_matrix")
        st.dataframe(filtered_master_df, use_container_width=True, hide_index=True)

        if selected_ticker:
            target_meta = next((r for r in review_rows if r["Ticker"] == selected_ticker), None)
            if target_meta:
                st.markdown("---")
                st.subheader(f"🎯 Top 10 Optimal Strategy Setups for `{selected_ticker}` (7–15 DTE)")
                st.caption("Evaluates Greeks (Δ, θ), POP, and S1/R1 Buffers. 5 Credit & 5 Debit Setups with Click-to-Inspect Profit Curves.")

                c_setups = scan_waterfall_options(
                    selected_ticker, target_meta["Raw_Spot"], target_meta["Raw_S1"], target_meta["Raw_R1"],
                    target_meta["Raw_Earnings"], target_meta["Raw_Bias"], dte_min=7, dte_max=15, hv30=target_meta["Raw_HV30"], target_book="Credit"
                )
                d_setups = scan_waterfall_options(
                    selected_ticker, target_meta["Raw_Spot"], target_meta["Raw_S1"], target_meta["Raw_R1"],
                    target_meta["Raw_Earnings"], target_meta["Raw_Bias"], dte_min=7, dte_max=15, hv30=target_meta["Raw_HV30"], target_book="Debit"
                )

                all_10 = c_setups + d_setups
                if all_10:
                    t10_df = pd.DataFrame(all_10)[UNIFIED_20_COLS]
                    st.dataframe(t10_df, use_container_width=True, hide_index=True)

                    st.markdown("#### 🔬 Inspect Strategy Profit Curve & Execution Rationale")
                    inspect_names = [f"#{i+1}: {s['Strategy']} | {s['Strikes Setup']} ({s['Expiry']})" for i, s in enumerate(all_10)]
                    sel_inspect = st.selectbox("Choose Setup to Analyze Profit Chart:", options=inspect_names, key="w_inspect_sel")
                    idx = inspect_names.index(sel_inspect)
                    chosen_setup = all_10[idx]

                    p_left, p_right = st.columns([1, 1])
                    with p_left:
                        st.markdown(f"**Strategy Architecture:** `{chosen_setup['Strategy']}`")
                        st.write(f"**Why This Strategy Works:** {chosen_setup['Why Best Option']}")
                        st.write(f"**Exit Trigger:** {chosen_setup['Exit Trigger']}")
                        st.write(f"**Probability of Profit:** {chosen_setup['POP (%)']} | **Delta:** {chosen_setup['Delta (Δ)']} | **Theta:** {chosen_setup['Theta (θ)']}")
                    with p_right:
                        render_profit_chart(chosen_setup)

# ========================================================
# VIEW 5: FULL OPTIONS EXECUTION HUB (18 STRATEGIES)
# ========================================================
elif st.session_state.current_view == "Options Execution Hub":
    st.title("🎯 Institutional Options Execution Hub (15 to 45 DTE)")
    st.caption("Complete 18-Strategy Screener with Option Greeks, Probability Analytics, and Expiration Profit Diagrams.")

    with st.spinner("Syncing watchlist parameters..."):
        review_rows = []
        for sym in st.session_state.watchlist:
            d = fetch_institutional_profile(sym)
            if d: review_rows.append(d)

    h_col1, h_col2 = st.columns(2, gap="large")

    with h_col1:
        st.markdown("#### 🟢 Credit Strategies (Net Sellers / Theta Positive)")
        sel_credit = st.selectbox("Credit Strategy Selector", FULL_CREDIT_STRATEGIES, key="hub_credit_sel")
        go_credit = st.button("🚀 Screen Credit Book", use_container_width=True, key="hub_credit_btn")

    with h_col2:
        st.markdown("#### 🔵 Debit Strategies (Net Buyers / Volatility Expansion)")
        sel_debit = st.selectbox("Debit Strategy Selector", FULL_DEBIT_STRATEGIES, key="hub_debit_sel")
        go_debit = st.button("🚀 Screen Debit Book", use_container_width=True, key="hub_debit_btn")

    if "hub_results" not in st.session_state:
        st.session_state.hub_results = []
    if "hub_label" not in st.session_state:
        st.session_state.hub_label = ""

    if go_credit:
        st.session_state.hub_label = f"Credit Book: {sel_credit}"
        found = []
        with st.spinner(f"Screening credit options for '{sel_credit}' across watchlist..."):
            for row in review_rows:
                if row["Ticker"] not in ["SPY", "QQQ"]:
                    s = scan_waterfall_options(
                        row["Ticker"], row["Raw_Spot"], row["Raw_S1"], row["Raw_R1"],
                        row["Raw_Earnings"], row["Raw_Bias"], dte_min=15, dte_max=45, hv30=row["Raw_HV30"], target_strategy=sel_credit
                    )
                    if s: found.extend(s)
        st.session_state.hub_results = found

    if go_debit:
        st.session_state.hub_label = f"Debit Book: {sel_debit}"
        found = []
        with st.spinner(f"Screening debit options for '{sel_debit}' across watchlist..."):
            for row in review_rows:
                if row["Ticker"] not in ["SPY", "QQQ"]:
                    s = scan_waterfall_options(
                        row["Ticker"], row["Raw_Spot"], row["Raw_S1"], row["Raw_R1"],
                        row["Raw_Earnings"], row["Raw_Bias"], dte_min=15, dte_max=45, hv30=row["Raw_HV30"], target_strategy=sel_debit
                    )
                    if s: found.extend(s)
        st.session_state.hub_results = found

    if st.session_state.hub_results:
        st.markdown(f"**Active Results Matrix:** `{st.session_state.hub_label}`")
        h_df = pd.DataFrame(st.session_state.hub_results)[UNIFIED_20_COLS]
        filtered_h = filter_dataframe(h_df, key_prefix="hub_table")
        st.dataframe(filtered_h, use_container_width=True, hide_index=True)

        st.markdown("#### 🔬 Inspect Setup Profit/Loss Profile")
        hub_opts = [f"#{i+1}: {s['Stock']} - {s['Strategy']} | {s['Strikes Setup']} ({s['Expiry']})" for i, s in enumerate(st.session_state.hub_results)]
        hub_sel = st.selectbox("Select Setup to Render Expiration Chart:", options=hub_opts, key="hub_inspect_sel")
        idx = hub_opts.index(hub_sel)
        chosen = st.session_state.hub_results[idx]

        h_left, h_right = st.columns([1, 1])
        with h_left:
            st.markdown(f"**Rationale:** {chosen['Why Best Option']}")
            st.write(f"**Exit Rule:** {chosen['Exit Trigger']}")
            st.write(f"**Risk Metrics:** Delta: {chosen['Delta (Δ)']} | Theta: {chosen['Theta (θ)']} | POP: {chosen['POP (%)']}")
        with h_right:
            render_profit_chart(chosen)

# ========================================================
# VIEW 6: WATCHLIST MANAGER
# ========================================================
elif st.session_state.current_view == "Watchlist Manager":
    st.title("⚙️ Persistent Watchlist Manager")
    st.caption("Add, remove, and manage ticker symbols. Configuration is automatically saved to `watchlist.json`.")

    w_col1, w_col2 = st.columns([2, 1])

    with w_col1:
        st.subheader("Active Watchlist Universe")
        st.dataframe(pd.DataFrame({"Ticker": st.session_state.watchlist, "Status": "Active Screened"}), use_container_width=True, hide_index=True)

    with w_col2:
        st.subheader("Manage Symbols")
        add_sym = st.text_input("Add New Ticker Symbol", placeholder="e.g. COIN", key="mgr_add_sym").strip().upper()
        if st.button("➕ Add Ticker", use_container_width=True, key="mgr_add_btn"):
            if add_sym and add_sym not in st.session_state.watchlist:
                st.session_state.watchlist.append(add_sym)
                save_watchlist(st.session_state.watchlist)
                st.success(f"Added {add_sym} to watchlist.")
                st.rerun()

        st.markdown("---")
        del_syms = st.multiselect("Select Ticker(s) to Remove", options=st.session_state.watchlist, key="mgr_del_syms")
        if st.button("🗑️ Remove Selected", use_container_width=True, key="mgr_del_btn"):
            if del_syms:
                st.session_state.watchlist = [t for t in st.session_state.watchlist if t not in del_syms]
                save_watchlist(st.session_state.watchlist)
                st.success("Removed selected symbols.")
                st.rerun()

        if st.button("🔄 Reset to Default 24 Master Tickers", use_container_width=True, key="mgr_reset_btn"):
            st.session_state.watchlist = DEFAULT_TICKERS.copy()
            save_watchlist(st.session_state.watchlist)
            st.rerun()
