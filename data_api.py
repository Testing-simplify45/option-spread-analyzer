"""
data_api.py
===========
Data layer — fetches live option data from Fyers API.
Falls back to mock data if not authenticated.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st

# ── Instrument master ────────────────────────────────────────────────────────
EXCHANGES = ["NSE", "BSE"]

UNDERLYINGS = {
    "NSE": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
    "BSE": ["SENSEX", "BANKEX"],
}

# Fyers symbol prefixes
_FYERS_EXCHANGE = {
    "NSE": "NSE",
    "BSE": "BSE",
}

_FYERS_UNDERLYING = {
    "NIFTY":      "NIFTY",
    "BANKNIFTY":  "BANKNIFTY",
    "FINNIFTY":   "FINNIFTY",
    "MIDCPNIFTY": "MIDCPNIFTY",
    "SENSEX":     "SENSEX",
    "BANKEX":     "BANKEX",
}

# Approximate ATM levels
_ATM_APPROX = {
    "NIFTY":      23300,
    "BANKNIFTY":  52000,
    "FINNIFTY":   23500,
    "MIDCPNIFTY": 11500,
    "SENSEX":     77000,
    "BANKEX":     59000,
}

_STRIKE_GAP = {
    "NIFTY":      50,
    "BANKNIFTY":  100,
    "FINNIFTY":   50,
    "MIDCPNIFTY": 25,
    "SENSEX":     100,
    "BANKEX":     100,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def round_to_nearest(value: float, multiple: int) -> int:
    return int(round(value / multiple) * multiple)


def round_to_nearest_50(value: float) -> int:
    return round_to_nearest(value, 50)


def get_atm(underlying: str) -> int:
    base = _ATM_APPROX.get(underlying, 25000)
    gap = _STRIKE_GAP.get(underlying, 50)
    return round_to_nearest(base, gap)


def _build_fyers_symbol(exchange: str, underlying: str, expiry: str, strike: int, option_type: str) -> str:
    """
    Build Fyers option symbol.
    Format: NSE:NIFTY25JAN23400CE
    """
    exp_date = datetime.strptime(expiry, "%Y-%m-%d")
    # Weekly format: DDMMMYY  e.g. 23JAN25
    exp_str = exp_date.strftime("%d%b%y").upper()
    return f"{exchange}:{underlying}{exp_str}{strike}{option_type}"


def _get_fyers():
    """Get authenticated Fyers client from session."""
    try:
        from fyers_auth import get_fyers_client
        return get_fyers_client()
    except Exception:
        return None


# ── Expiries ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def get_expiries(exchange: str, underlying: str) -> list[str]:
    """Return available expiry dates as YYYY-MM-DD strings."""
    fyers = _get_fyers()

    if fyers is None:
        # Mock expiries
        today = date.today()
        expiries = []
        d = today
        for _ in range(12):
            days_ahead = 3 - d.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            d = d + timedelta(days=days_ahead)
            expiries.append(d.isoformat())
        return expiries

    try:
        # Fetch from Fyers option chain
        symbol_map = {"NIFTY": "NSE:NIFTY50-INDEX", "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
                      "SENSEX": "BSE:SENSEX-INDEX", "BANKEX": "BSE:BANKEX-INDEX",
                      "FINNIFTY": "NSE:FINNIFTY-INDEX", "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX"}
        idx_symbol = symbol_map.get(underlying, f"{exchange}:{underlying}-INDEX")

        data = {"symbol": idx_symbol, "strikecount": 1, "timestamp": ""}
        response = fyers.optionchain(data=data)

        if response.get("s") == "ok":
            expiry_list = response["data"]["expiryData"]
            dates = []
            for e in expiry_list:
                ts = e.get("expiry", 0)
                d = datetime.fromtimestamp(ts).date()
                dates.append(d.isoformat())
            return sorted(dates)
    except Exception as e:
        pass

    # Fallback to mock
    today = date.today()
    expiries = []
    d = today
    for _ in range(12):
        days_ahead = 3 - d.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        d = d + timedelta(days=days_ahead)
        expiries.append(d.isoformat())
    return expiries


@lru_cache(maxsize=None)
def get_strikes(exchange: str, underlying: str, expiry: str) -> list[int]:
    """Return sorted list of available strikes."""
    fyers = _get_fyers()

    if fyers is None:
        atm = get_atm(underlying)
        gap = _STRIKE_GAP.get(underlying, 50)
        return [atm + (i - 10) * gap for i in range(21)]

    try:
        symbol_map = {"NIFTY": "NSE:NIFTY50-INDEX", "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
                      "SENSEX": "BSE:SENSEX-INDEX", "BANKEX": "BSE:BANKEX-INDEX",
                      "FINNIFTY": "NSE:FINNIFTY-INDEX", "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX"}
        idx_symbol = symbol_map.get(underlying, f"{exchange}:{underlying}-INDEX")

        exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        exp_ts = int(exp_date.timestamp())

        data = {"symbol": idx_symbol, "strikecount": 20, "timestamp": str(exp_ts)}
        response = fyers.optionchain(data=data)

        if response.get("s") == "ok":
            options = response["data"]["optionsChain"]
            strikes = sorted(set(int(o["strikePrice"]) for o in options))
            return strikes
    except Exception:
        pass

    atm = get_atm(underlying)
    gap = _STRIKE_GAP.get(underlying, 50)
    return [atm + (i - 10) * gap for i in range(21)]


# ── Live Price ────────────────────────────────────────────────────────────────

def get_ltp(exchange: str, underlying: str, expiry: str, strike: int, option_type: str) -> Optional[float]:
    """Return the last traded price for a single option contract."""
    fyers = _get_fyers()

    if fyers is None:
        # Mock price
        atm = _ATM_APPROX.get(underlying, 25000)
        dist = abs(atm - strike) / atm
        raw = atm * 0.01 * max(0.05, 1 - dist * 3)
        noise = raw * 0.02 * (random.random() - 0.5)
        return round(max(0.05, raw + noise), 2)

    try:
        symbol = _build_fyers_symbol(exchange, underlying, expiry, strike, option_type)
        data = {"symbols": symbol}
        response = fyers.quotes(data=data)

        if response.get("s") == "ok":
            ltp = response["d"][0]["v"]["lp"]
            return float(ltp)
    except Exception:
        pass

    return None


# ── Historical Data ───────────────────────────────────────────────────────────

def get_spread_history(
    exchange1, underlying1, expiry1, strike1, type1,
    exchange2, underlying2, expiry2, strike2, type2,
    trade_date: date,
    ratio: float = 1.0,
) -> pd.DataFrame:
    """Return tick-by-tick spread data for the given date."""
    fyers = _get_fyers()

    if fyers is None:
        return _mock_spread_history(trade_date, ratio)

    try:
        sym1 = _build_fyers_symbol(exchange1, underlying1, expiry1, strike1, type1)
        sym2 = _build_fyers_symbol(exchange2, underlying2, expiry2, strike2, type2)

        date_str = trade_date.strftime("%Y-%m-%d")

        def fetch_candles(symbol):
            data = {
                "symbol": symbol,
                "resolution": "1",   # 1 minute candles
                "date_format": "1",
                "range_from": date_str,
                "range_to": date_str,
                "cont_flag": "1",
            }
            resp = fyers.history(data=data)
            if resp.get("s") == "ok":
                candles = resp["candles"]
                df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df = df.set_index("timestamp")
                return df["close"]
            return pd.Series(dtype=float)

        leg1 = fetch_candles(sym1)
        leg2 = fetch_candles(sym2)

        if leg1.empty or leg2.empty:
            return _mock_spread_history(trade_date, ratio)

        combined = pd.DataFrame({"leg1_price": leg1, "leg2_price": leg2}).dropna()
        combined["spread"] = combined["leg1_price"] - combined["leg2_price"] * ratio
        combined = combined.reset_index()
        combined.columns = ["timestamp", "leg1_price", "leg2_price", "spread"]
        return combined

    except Exception as e:
        return _mock_spread_history(trade_date, ratio)


def _mock_spread_history(trade_date: date, ratio: float = 1.0) -> pd.DataFrame:
    """Generate realistic intraday spread ticks using a correlated random walk."""
    open_time = datetime.combine(trade_date, datetime.strptime("09:15", "%H:%M").time())
    close_time = datetime.combine(trade_date, datetime.strptime("15:30", "%H:%M").time())

    timestamps = []
    t = open_time
    while t <= close_time:
        timestamps.append(t)
        t += timedelta(seconds=60)

    n = len(timestamps)
    seed = int(trade_date.strftime("%Y%m%d"))
    rng = np.random.default_rng(seed)

    leg1_start = 80 + rng.uniform(-20, 40)
    leg1_vol = 0.003
    leg1_prices = [leg1_start]
    for _ in range(n - 1):
        leg1_prices.append(max(0.5, leg1_prices[-1] * (1 + rng.normal(0, leg1_vol))))

    leg2_start = 25 + rng.uniform(-5, 15)
    leg2_vol = 0.004
    leg2_prices = [leg2_start]
    for i in range(n - 1):
        corr = 0.65 * (leg1_prices[i] / leg1_prices[i - 1] - 1) if i > 0 else 0
        leg2_prices.append(max(0.5, leg2_prices[-1] * (1 + rng.normal(corr * 0.5, leg2_vol))))

    leg1 = np.array(leg1_prices)
    leg2 = np.array(leg2_prices)
    spread = leg1 - (leg2 * ratio)

    return pd.DataFrame({
        "timestamp": timestamps,
        "leg1_price": np.round(leg1, 2),
        "leg2_price": np.round(leg2, 2),
        "spread": np.round(spread, 2),
    })


# ── Resampling & Stats ────────────────────────────────────────────────────────

def resample_spread(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
    if df.empty:
        return df

    if resolution == "Tick":
        return df[["timestamp", "spread"]].copy()

    freq_map = {
        "30 Seconds": "30s",
        "1 Minute":   "1min",
        "5 Minutes":  "5min",
        "15 Minutes": "15min",
    }
    freq = freq_map.get(resolution, "1min")

    df2 = df.set_index("timestamp")
    ohlc = df2["spread"].resample(freq).agg(["first", "max", "min", "last"])
    ohlc.columns = ["open", "high", "low", "close"]
    ohlc = ohlc.dropna().reset_index()
    return ohlc


def compute_day_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"open": None, "high": None, "low": None, "current": None,
                "high_time": None, "low_time": None}

    series = df["spread"]
    return {
        "open":      round(float(series.iloc[0]), 2),
        "high":      round(float(series.max()), 2),
        "low":       round(float(series.min()), 2),
        "current":   round(float(series.iloc[-1]), 2),
        "high_time": df.loc[series.idxmax(), "timestamp"],
        "low_time":  df.loc[series.idxmin(), "timestamp"],
    }
