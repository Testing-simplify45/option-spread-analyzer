"""
data_api.py - Fixed using working dashboard.py as reference
Key fixes:
1. Symbol format matches working app (monthly=YYMON, weekly=YYM(no-zero)DD)
2. Candle fetch with IST timezone conversion
3. Expiry codes from optionchain (not timestamps for strikes)
4. Strikes from mock/manual input (no optionchain for strikes)
"""
from __future__ import annotations
import random
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np
import streamlit as st

EXCHANGES = ["NSE", "BSE"]
UNDERLYINGS = {
    "NSE": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
    "BSE": ["SENSEX", "BANKEX"],
}

_INDEX_SYMBOL = {
    "NIFTY":      "NSE:NIFTY50-INDEX",
    "BANKNIFTY":  "NSE:NIFTYBANK-INDEX",
    "FINNIFTY":   "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX":     "BSE:SENSEX-INDEX",
    "BANKEX":     "BSE:BANKEX-INDEX",
}

_ATM_APPROX = {
    "NIFTY": 23300, "BANKNIFTY": 52000, "FINNIFTY": 23500,
    "MIDCPNIFTY": 11500, "SENSEX": 77000, "BANKEX": 59000,
}
_STRIKE_GAP = {
    "NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50,
    "MIDCPNIFTY": 25, "SENSEX": 100, "BANKEX": 100,
}

_MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN",
           "JUL","AUG","SEP","OCT","NOV","DEC"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def round_to_nearest(value: float, multiple: int) -> int:
    return int(round(value / multiple) * multiple)

def round_to_nearest_50(value: float) -> int:
    return round_to_nearest(value, 50)

def get_atm(underlying: str) -> int:
    base = _ATM_APPROX.get(underlying, 25000)
    gap  = _STRIKE_GAP.get(underlying, 50)
    return round_to_nearest(base, gap)

def _get_fyers():
    try:
        from fyers_auth import get_fyers_client
        return get_fyers_client()
    except Exception:
        return None


# ── Symbol builder (copied from working dashboard.py) ─────────────────────────

def _build_fyers_symbol(exchange: str, underlying: str, expiry_code: str,
                         strike: int, option_type: str) -> str:
    """
    expiry_code is a Fyers expiry code:
      Monthly : "26AUG"  → BSE:SENSEX26AUG77000CE
      Weekly  : "260806" → BSE:SENSEX2680677000CE  (YYMMDD → YYM(no-zero)DD)
    """
    ot = "CE" if option_type.upper() in ("C", "CE") else "PE"
    code = expiry_code.strip().upper()

    # Monthly: contains letters
    if any(c.isalpha() for c in code):
        return f"{exchange}:{underlying}{code}{strike}{ot}"

    # Weekly numeric YYMMDD (6 chars)
    yy = code[0:2]
    mm = str(int(code[2:4]))   # remove leading zero from month
    dd = code[4:6]
    return f"{exchange}:{underlying}{yy}{mm}{dd}{strike}{ot}"


# ── Expiries ──────────────────────────────────────────────────────────────────

def get_expiries(exchange: str, underlying: str) -> list[str]:
    """
    Returns list of expiry DISPLAY strings.
    Also stores a mapping in session_state for symbol building.
    """
    fyers = _get_fyers()
    if fyers is None:
        return _mock_expiry_labels(underlying)

    try:
        sym = _INDEX_SYMBOL.get(underlying)
        if not sym:
            return _mock_expiry_labels(underlying)

        resp = fyers.optionchain(data={"symbol": sym, "strikecount": 1, "timestamp": ""})
        if not (resp and resp.get("s") == "ok"):
            st.warning(f"Expiry fetch failed: {resp.get('message', resp)}")
            return _mock_expiry_labels(underlying)

        raw = resp.get("data", {}).get("expiryData", [])

        from collections import defaultdict
        parsed = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            d = entry.get("date", "")
            try:
                dd, mm, yyyy = d.split("-")
                dd, mm, yyyy = int(dd), int(mm), int(yyyy)
            except Exception:
                continue
            yy  = yyyy % 100
            mon = _MONTHS[mm - 1]
            parsed.append((yy, mm, dd, mon))

        # Find last Thursday of each month → monthly expiry
        by_month = defaultdict(list)
        for yy, mm, dd, mon in parsed:
            by_month[(yy, mm)].append(dd)
        last_of_month = {k: max(v) for k, v in by_month.items()}

        labels  = []
        code_map = {}  # label → fyers_code
        for yy, mm, dd, mon in parsed:
            is_monthly = (dd == last_of_month[(yy, mm)])
            if is_monthly:
                code  = f"{yy:02d}{mon}"          # e.g. "26AUG"
                label = f"{dd:02d} {mon} {yy:02d} (M)"
            else:
                code  = f"{yy:02d}{mm:02d}{dd:02d}"  # e.g. "260806"
                label = f"{dd:02d} {mon} {yy:02d} (W)"
            labels.append(label)
            code_map[label] = code

        # Store mapping so we can look up the code when building symbols
        key = f"expiry_codes_{underlying}"
        st.session_state[key] = code_map

        return labels

    except Exception as ex:
        st.warning(f"Expiry error: {ex}")
        return _mock_expiry_labels(underlying)


def get_expiry_code(underlying: str, label: str) -> str:
    """Convert display label back to Fyers expiry code."""
    key = f"expiry_codes_{underlying}"
    code_map = st.session_state.get(key, {})
    return code_map.get(label, label)


def _mock_expiry_labels(underlying: str) -> list[str]:
    today = date.today()
    labels = []
    d = today
    for _ in range(12):
        days_ahead = 3 - d.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        d = d + timedelta(days=days_ahead)
        # Use YYMMDD format for mock codes
        label = d.strftime("%d %b %y") + " (W)"
        labels.append(label)
        code = d.strftime("%y%m%d")
        key = f"expiry_codes_{underlying}"
        if key not in st.session_state:
            st.session_state[key] = {}
        st.session_state[key][label] = code
    return labels


# ── Strikes ───────────────────────────────────────────────────────────────────
# Working app does NOT fetch strikes from API — uses manual number input
# We provide a default list around ATM for the dropdown

def get_strikes(exchange: str, underlying: str, expiry: str) -> list[int]:
    atm = get_atm(underlying)
    gap = _STRIKE_GAP.get(underlying, 50)
    return [atm + (i - 15) * gap for i in range(31)]


# ── Live LTP ──────────────────────────────────────────────────────────────────

def get_ltp(exchange, underlying, expiry_label, strike, option_type) -> Optional[float]:
    fyers = _get_fyers()
    if fyers is None:
        return _mock_ltp(underlying, strike)
    try:
        code   = get_expiry_code(underlying, expiry_label)
        symbol = _build_fyers_symbol(exchange, underlying, code, strike, option_type)
        resp   = fyers.quotes(data={"symbols": symbol})
        if resp.get("s") == "ok":
            v   = resp["d"][0].get("v", {})
            ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
            if ltp:
                return float(ltp)
        st.warning(f"LTP failed {symbol}: {resp.get('message','')}")
    except Exception as ex:
        st.warning(f"LTP error: {ex}")
    return None


def _mock_ltp(underlying, strike):
    atm  = _ATM_APPROX.get(underlying, 25000)
    dist = abs(atm - strike) / atm
    raw  = atm * 0.01 * max(0.05, 1 - dist * 3)
    return round(max(0.05, raw + raw * 0.02 * (random.random() - 0.5)), 2)


# ── Batch LTP ────────────────────────────────────────────────────────────────

def get_ltp_batch_symbols(symbols: list[str]) -> dict[str, float]:
    """Fetch LTP for pre-built symbol strings in one batch call."""
    fyers = _get_fyers()
    if fyers is None:
        return {}
    results = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i+50]
        try:
            resp = fyers.quotes(data={"symbols": ",".join(batch)})
            if resp.get("s") == "ok":
                for item in resp["d"]:
                    sym = item.get("n", "")
                    v   = item.get("v", {})
                    ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
                    if ltp and sym:
                        results[sym] = float(ltp)
        except Exception as ex:
            st.warning(f"Batch LTP error: {ex}")
    return results


# ── Candle fetch (from working dashboard.py) ──────────────────────────────────

def _fetch_candles(fyers, symbol: str, trade_date: date,
                   resolution: str = "1") -> pd.DataFrame:
    """
    Fetch OHLCV candles. Returns DataFrame indexed by IST datetime.
    Columns: open, high, low, close, volume
    """
    date_str = trade_date.strftime("%Y-%m-%d")
    try:
        resp = fyers.history(data={
            "symbol":     symbol,
            "resolution": str(resolution),
            "date_format":"1",
            "range_from": date_str,
            "range_to":   date_str,
            "cont_flag":  "1",
        })
        if resp.get("s") == "ok" and resp.get("candles"):
            df = pd.DataFrame(
                resp["candles"],
                columns=["timestamp","open","high","low","close","volume"]
            )
            # Convert to IST (same as working app)
            df["datetime"] = (
                pd.to_datetime(df["timestamp"], unit="s")
                .dt.tz_localize("UTC")
                .dt.tz_convert("Asia/Kolkata")
                .dt.tz_localize(None)
            )
            return df.drop(columns=["timestamp"]).set_index("datetime")

        # Show message so we know what failed
        st.warning(f"Candle fetch: {symbol} → {resp.get('message', resp)}")

    except Exception as ex:
        st.warning(f"Candle error {symbol}: {ex}")

    return pd.DataFrame()


# ── Spread history ────────────────────────────────────────────────────────────

def get_spread_history(
    exchange1, underlying1, expiry_label1, strike1, type1,
    exchange2, underlying2, expiry_label2, strike2, type2,
    trade_date: date,
    ratio: float = 1.0,
) -> pd.DataFrame:
    """
    Fetch 1-min spread data for a given date.
    Spread = leg1_close - (leg2_close × ratio)
    High/Low derived from candle H/L of each leg.
    """
    fyers = _get_fyers()
    if fyers is None:
        return _mock_spread_history(trade_date, ratio)

    try:
        code1  = get_expiry_code(underlying1, expiry_label1)
        code2  = get_expiry_code(underlying2, expiry_label2)
        sym1   = _build_fyers_symbol(exchange1, underlying1, code1, strike1, type1)
        sym2   = _build_fyers_symbol(exchange2, underlying2, code2, strike2, type2)

        df1 = _fetch_candles(fyers, sym1, trade_date)
        df2 = _fetch_candles(fyers, sym2, trade_date)

        if df1.empty or df2.empty:
            return _mock_spread_history(trade_date, ratio)

        # Remove duplicate timestamps
        df1 = df1[~df1.index.duplicated(keep="last")]
        df2 = df2[~df2.index.duplicated(keep="last")]

        # Common timestamps
        common = df1.index.intersection(df2.index)
        if common.empty:
            return _mock_spread_history(trade_date, ratio)

        combined = pd.DataFrame({
            "leg1_price":  df1.loc[common, "close"],
            "leg2_price":  df2.loc[common, "close"],
            # Spread high: leg1 high - (leg2 low × ratio)
            "spread_high": df1.loc[common, "high"] - df2.loc[common, "low"]  * ratio,
            # Spread low:  leg1 low  - (leg2 high × ratio)
            "spread_low":  df1.loc[common, "low"]  - df2.loc[common, "high"] * ratio,
        })
        combined["spread"] = combined["leg1_price"] - combined["leg2_price"] * ratio
        combined = combined.dropna().reset_index()
        combined.rename(columns={"datetime": "timestamp"}, inplace=True)
        return combined

    except Exception as ex:
        st.warning(f"History error: {ex}")
        return _mock_spread_history(trade_date, ratio)


# ── Mock data ─────────────────────────────────────────────────────────────────

def _mock_spread_history(trade_date: date, ratio: float = 1.0) -> pd.DataFrame:
    open_time  = datetime.combine(trade_date, datetime.strptime("09:15","%H:%M").time())
    close_time = datetime.combine(trade_date, datetime.strptime("15:30","%H:%M").time())
    timestamps = []
    t = open_time
    while t <= close_time:
        timestamps.append(t)
        t += timedelta(minutes=1)
    n   = len(timestamps)
    rng = np.random.default_rng(int(trade_date.strftime("%Y%m%d")))
    leg1 = [80 + rng.uniform(-20,40)]
    for _ in range(n-1):
        leg1.append(max(0.5, leg1[-1]*(1+rng.normal(0,0.003))))
    leg2 = [25 + rng.uniform(-5,15)]
    for i in range(n-1):
        corr = 0.65*(leg1[i]/leg1[i-1]-1) if i>0 else 0
        leg2.append(max(0.5, leg2[-1]*(1+rng.normal(corr*0.5,0.004))))
    leg1 = np.array(leg1)
    leg2 = np.array(leg2)
    spread = leg1 - leg2*ratio
    return pd.DataFrame({
        "timestamp":   timestamps,
        "leg1_price":  np.round(leg1,2),
        "leg2_price":  np.round(leg2,2),
        "spread":      np.round(spread,2),
        "spread_high": np.round(spread*1.002,2),
        "spread_low":  np.round(spread*0.998,2),
    })


# ── Stats ─────────────────────────────────────────────────────────────────────

def resample_spread(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
    if df.empty:
        return df
    if resolution == "Tick":
        return df[["timestamp","spread"]].copy()
    freq_map = {"30 Seconds":"30s","1 Minute":"1min",
                "5 Minutes":"5min","15 Minutes":"15min"}
    freq = freq_map.get(resolution,"1min")
    ohlc = df.set_index("timestamp")["spread"].resample(freq).agg(
        ["first","max","min","last"])
    ohlc.columns = ["open","high","low","close"]
    return ohlc.dropna().reset_index()


def compute_day_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"open":None,"high":None,"low":None,
                "current":None,"high_time":None,"low_time":None}
    s = df["spread"]
    # Use spread_high/low columns if available for accurate H/L
    h_series = df.get("spread_high", s)
    l_series = df.get("spread_low",  s)
    return {
        "open":      round(float(s.iloc[0]),2),
        "high":      round(float(h_series.max()),2),
        "low":       round(float(l_series.min()),2),
        "current":   round(float(s.iloc[-1]),2),
        "high_time": df.loc[h_series.idxmax(), "timestamp"],
        "low_time":  df.loc[l_series.idxmin(), "timestamp"],
    }
