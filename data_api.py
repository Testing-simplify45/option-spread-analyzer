"""
data_api.py - Optimized with batch API calls
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
_OPTION_EXCHANGE = {"NSE": "NSE", "BSE": "BSE"}
_OPTION_UNDERLYING = {
    "NIFTY": "NIFTY", "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY", "MIDCPNIFTY": "MIDCPNIFTY",
    "SENSEX": "SENSEX", "BANKEX": "BANKEX",
}
_ATM_APPROX = {
    "NIFTY": 23300, "BANKNIFTY": 52000, "FINNIFTY": 23500,
    "MIDCPNIFTY": 11500, "SENSEX": 77000, "BANKEX": 59000,
}
_STRIKE_GAP = {
    "NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50,
    "MIDCPNIFTY": 25, "SENSEX": 100, "BANKEX": 100,
}


def round_to_nearest(value: float, multiple: int) -> int:
    return int(round(value / multiple) * multiple)

def round_to_nearest_50(value: float) -> int:
    return round_to_nearest(value, 50)

def get_atm(underlying: str) -> int:
    base = _ATM_APPROX.get(underlying, 25000)
    gap = _STRIKE_GAP.get(underlying, 50)
    return round_to_nearest(base, gap)

def _build_fyers_symbol(exchange, underlying, expiry, strike, option_type):
    exp_date = datetime.strptime(expiry, "%Y-%m-%d")
    yy  = exp_date.strftime("%y")
    mm  = str(exp_date.month)
    dd  = exp_date.strftime("%d")
    ex  = _OPTION_EXCHANGE.get(exchange, exchange)
    und = _OPTION_UNDERLYING.get(underlying, underlying)
    return f"{ex}:{und}{yy}{mm}{dd}{strike}{option_type}"

def _get_fyers():
    try:
        from fyers_auth import get_fyers_client
        return get_fyers_client()
    except Exception:
        return None

def _mock_ltp(underlying, strike):
    atm = _ATM_APPROX.get(underlying, 25000)
    dist = abs(atm - strike) / atm
    raw = atm * 0.01 * max(0.05, 1 - dist * 3)
    return round(max(0.05, raw + raw * 0.02 * (random.random() - 0.5)), 2)


# ── Expiries ──────────────────────────────────────────────────────────────────

def get_expiries(exchange: str, underlying: str) -> list[str]:
    fyers = _get_fyers()
    if fyers is None:
        return _mock_expiries()
    try:
        idx_symbol = _INDEX_SYMBOL.get(underlying)
        if not idx_symbol:
            return _mock_expiries()
        response = fyers.optionchain(data={"symbol": idx_symbol, "strikecount": 1, "timestamp": ""})
        if response.get("s") == "ok":
            return sorted([
                datetime.fromtimestamp(int(e["expiry"])).date().isoformat()
                for e in response["data"]["expiryData"]
            ])
    except Exception as ex:
        st.warning(f"Expiry error: {ex}")
    return _mock_expiries()

def _mock_expiries():
    today = date.today()
    expiries, d = [], today
    for _ in range(12):
        days_ahead = 3 - d.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        d = d + timedelta(days=days_ahead)
        expiries.append(d.isoformat())
    return expiries


# ── Strikes ───────────────────────────────────────────────────────────────────

def get_strikes(exchange: str, underlying: str, expiry: str) -> list[int]:
    fyers = _get_fyers()
    if fyers is None:
        return _mock_strikes(underlying)
    try:
        idx_symbol = _INDEX_SYMBOL.get(underlying)
        exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        exp_ts = int(datetime(exp_date.year, exp_date.month, exp_date.day, 15, 30, 0).timestamp())

        # Try 1: integer timestamp
        r = fyers.optionchain(data={"symbol": idx_symbol, "strikecount": 20, "timestamp": exp_ts})
        if r.get("s") == "ok":
            return sorted(set(int(o["strikePrice"]) for o in r["data"]["optionsChain"]))

        # Try 2: string timestamp
        r2 = fyers.optionchain(data={"symbol": idx_symbol, "strikecount": 20, "timestamp": str(exp_ts)})
        if r2.get("s") == "ok":
            return sorted(set(int(o["strikePrice"]) for o in r2["data"]["optionsChain"]))

        # Try 3: empty timestamp (nearest expiry)
        r3 = fyers.optionchain(data={"symbol": idx_symbol, "strikecount": 20, "timestamp": ""})
        if r3.get("s") == "ok":
            return sorted(set(int(o["strikePrice"]) for o in r3["data"]["optionsChain"]))

        st.warning(f"Strike fetch failed | symbol={idx_symbol} | ts={exp_ts} | msg={r.get('message')}")

    except Exception as ex:
        st.warning(f"Strike error: {ex}")
    return _mock_strikes(underlying)

def _mock_strikes(underlying):
    atm = get_atm(underlying)
    gap = _STRIKE_GAP.get(underlying, 50)
    return [atm + (i - 10) * gap for i in range(21)]


# ── Batch LTP (single API call for multiple symbols) ──────────────────────────

def get_ltp_batch(symbols: list[str]) -> dict[str, float]:
    """
    Fetch LTP for multiple symbols in ONE API call.
    Returns dict: {symbol: ltp}
    Fyers allows up to 50 symbols per batch call.
    """
    fyers = _get_fyers()
    if fyers is None:
        return {}

    results = {}
    # Fyers batch limit is 50 symbols
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            symbols_str = ",".join(batch)
            response = fyers.quotes(data={"symbols": symbols_str})
            if response.get("s") == "ok":
                for item in response["d"]:
                    sym = item.get("n", "")
                    v = item.get("v", {})
                    ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
                    if ltp and sym:
                        results[sym] = float(ltp)
        except Exception as ex:
            st.warning(f"Batch LTP error: {ex}")
    return results


def get_ltp(exchange, underlying, expiry, strike, option_type) -> Optional[float]:
    """Single LTP fetch — use get_ltp_batch for multiple symbols."""
    fyers = _get_fyers()
    if fyers is None:
        return _mock_ltp(underlying, strike)
    try:
        symbol = _build_fyers_symbol(exchange, underlying, expiry, strike, option_type)
        response = fyers.quotes(data={"symbols": symbol})
        if response.get("s") == "ok":
            v = response["d"][0].get("v", {})
            ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
            if ltp:
                return float(ltp)
        st.warning(f"LTP failed for {symbol}: {response.get('message', '')}")
    except Exception as ex:
        st.warning(f"LTP error: {ex}")
    return None


# ── History (used only when View Chart is clicked) ────────────────────────────

def get_spread_history(
    exchange1, underlying1, expiry1, strike1, type1,
    exchange2, underlying2, expiry2, strike2, type2,
    trade_date: date,
    ratio: float = 1.0,
) -> pd.DataFrame:
    """
    Fetch spread history for a single day.
    Only called when user clicks View Chart.
    """
    fyers = _get_fyers()
    if fyers is None:
        return _mock_spread_history(trade_date, ratio)

    try:
        sym1 = _build_fyers_symbol(exchange1, underlying1, expiry1, strike1, type1)
        sym2 = _build_fyers_symbol(exchange2, underlying2, expiry2, strike2, type2)

        leg1 = _fetch_history(fyers, sym1, trade_date)
        leg2 = _fetch_history(fyers, sym2, trade_date)

        if leg1.empty or leg2.empty:
            return _mock_spread_history(trade_date, ratio)

        # Align timestamps
        combined = pd.DataFrame({"leg1_price": leg1, "leg2_price": leg2})
        combined = combined.resample("1min").last().ffill().dropna()
        combined["spread"] = combined["leg1_price"] - combined["leg2_price"] * ratio
        combined = combined.reset_index()
        combined.columns = ["timestamp", "leg1_price", "leg2_price", "spread"]
        return combined

    except Exception as ex:
        st.warning(f"History error: {ex}")
        return _mock_spread_history(trade_date, ratio)


def _fetch_history(fyers, symbol: str, trade_date: date) -> pd.Series:
    """Try multiple resolutions to get price history."""
    date_str = trade_date.strftime("%Y-%m-%d")
    for res in ["1", "2", "5", "15"]:
        try:
            resp = fyers.history(data={
                "symbol": symbol,
                "resolution": res,
                "date_format": "1",
                "range_from": date_str,
                "range_to": date_str,
                "cont_flag": "1",
            })
            if resp.get("s") == "ok" and resp.get("candles"):
                df = pd.DataFrame(
                    resp["candles"],
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                return df.set_index("timestamp")["close"]
        except Exception:
            continue
    return pd.Series(dtype=float)


def get_multi_day_history(
    exchange1, underlying1, expiry1, strike1, type1,
    exchange2, underlying2, expiry2, strike2, type2,
    days: int = 1,
    ratio: float = 1.0,
) -> pd.DataFrame:
    today = date.today()
    frames = []
    d = today
    collected = 0
    while collected < days:
        if d.weekday() < 5:
            df = get_spread_history(
                exchange1, underlying1, expiry1, strike1, type1,
                exchange2, underlying2, expiry2, strike2, type2,
                d, ratio=ratio,
            )
            if not df.empty:
                frames.append(df)
            collected += 1
        d -= timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames[::-1], ignore_index=True)


# ── Mock data ─────────────────────────────────────────────────────────────────

def _mock_spread_history(trade_date: date, ratio: float = 1.0) -> pd.DataFrame:
    open_time  = datetime.combine(trade_date, datetime.strptime("09:15", "%H:%M").time())
    close_time = datetime.combine(trade_date, datetime.strptime("15:30", "%H:%M").time())
    timestamps = []
    t = open_time
    while t <= close_time:
        timestamps.append(t)
        t += timedelta(minutes=1)
    n = len(timestamps)
    rng = np.random.default_rng(int(trade_date.strftime("%Y%m%d")))
    leg1 = [80 + rng.uniform(-20, 40)]
    for _ in range(n - 1):
        leg1.append(max(0.5, leg1[-1] * (1 + rng.normal(0, 0.003))))
    leg2 = [25 + rng.uniform(-5, 15)]
    for i in range(n - 1):
        corr = 0.65 * (leg1[i] / leg1[i-1] - 1) if i > 0 else 0
        leg2.append(max(0.5, leg2[-1] * (1 + rng.normal(corr * 0.5, 0.004))))
    leg1 = np.array(leg1)
    leg2 = np.array(leg2)
    return pd.DataFrame({
        "timestamp": timestamps,
        "leg1_price": np.round(leg1, 2),
        "leg2_price": np.round(leg2, 2),
        "spread": np.round(leg1 - leg2 * ratio, 2),
    })


# ── Stats ─────────────────────────────────────────────────────────────────────

def resample_spread(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
    if df.empty:
        return df
    if resolution == "Tick":
        return df[["timestamp", "spread"]].copy()
    freq_map = {"30 Seconds": "30s", "1 Minute": "1min", "5 Minutes": "5min", "15 Minutes": "15min"}
    freq = freq_map.get(resolution, "1min")
    ohlc = df.set_index("timestamp")["spread"].resample(freq).agg(["first","max","min","last"])
    ohlc.columns = ["open","high","low","close"]
    return ohlc.dropna().reset_index()

def compute_day_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"open": None, "high": None, "low": None, "current": None, "high_time": None, "low_time": None}
    s = df["spread"]
    return {
        "open":      round(float(s.iloc[0]), 2),
        "high":      round(float(s.max()), 2),
        "low":       round(float(s.min()), 2),
        "current":   round(float(s.iloc[-1]), 2),
        "high_time": df.loc[s.idxmax(), "timestamp"],
        "low_time":  df.loc[s.idxmin(), "timestamp"],
    }
