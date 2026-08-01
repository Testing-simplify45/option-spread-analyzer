"""
data_api.py
===========
Single abstraction layer between the UI and the tick data API.

Replace the body of each function with your actual API calls.
The mock implementations return realistic synthetic data so the
UI can be developed and tested without a live feed.
"""

from __future__ import annotations

import random
import math
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

import pandas as pd
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────
# Set USE_MOCK = False and fill in API_BASE_URL / API_KEY to use live data.
USE_MOCK = True
API_BASE_URL = "https://your-api-endpoint.com"
API_KEY = "your-api-key-here"

# ── Instrument master ────────────────────────────────────────────────────────
EXCHANGES = ["NSE", "BSE"]

UNDERLYINGS = {
    "NSE": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
    "BSE": ["SENSEX", "BANKEX"],
}

# Approximate ATM levels (used for mock strike generation)
_ATM_APPROX = {
    "NIFTY": 23300,
    "BANKNIFTY": 52000,
    "FINNIFTY": 23500,
    "MIDCPNIFTY": 11500,
    "SENSEX": 77000,
    "BANKEX": 59000,
}

_STRIKE_GAP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "MIDCPNIFTY": 25,
    "SENSEX": 100,
    "BANKEX": 100,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def round_to_nearest(value: float, multiple: int) -> int:
    return int(round(value / multiple) * multiple)


def round_to_nearest_50(value: float) -> int:
    return round_to_nearest(value, 50)


def get_atm(underlying: str) -> int:
    base = _ATM_APPROX.get(underlying, 25000)
    gap = _STRIKE_GAP.get(underlying, 50)
    return round_to_nearest(base, gap)


# ─────────────────────────────────────────────────────────────────────────────
# Instrument data
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def get_expiries(exchange: str, underlying: str) -> list[str]:
    """Return available expiry dates as YYYY-MM-DD strings."""
    if USE_MOCK:
        today = date.today()
        expiries = []
        d = today
        for _ in range(12):
            # Next Thursday
            days_ahead = 3 - d.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            d = d + timedelta(days=days_ahead)
            expiries.append(d.isoformat())
        return expiries
    else:
        import requests
        r = requests.get(
            f"{API_BASE_URL}/instruments/expiries",
            params={"exchange": exchange, "underlying": underlying},
            headers={"x-api-key": API_KEY},
            timeout=5,
        )
        return r.json()["expiries"]


@lru_cache(maxsize=None)
def get_strikes(exchange: str, underlying: str, expiry: str) -> list[int]:
    """Return sorted list of available strikes."""
    if USE_MOCK:
        atm = get_atm(underlying)
        gap = _STRIKE_GAP.get(underlying, 50)
        return [atm + (i - 10) * gap for i in range(21)]
    else:
        import requests
        r = requests.get(
            f"{API_BASE_URL}/instruments/strikes",
            params={"exchange": exchange, "underlying": underlying, "expiry": expiry},
            headers={"x-api-key": API_KEY},
            timeout=5,
        )
        return sorted(r.json()["strikes"])


# ─────────────────────────────────────────────────────────────────────────────
# Live price
# ─────────────────────────────────────────────────────────────────────────────

def get_ltp(
    exchange: str,
    underlying: str,
    expiry: str,
    strike: int,
    option_type: str,
) -> Optional[float]:
    """
    Return the last traded price for a single option contract.
    Returns None if the contract is not found or the market is closed.
    """
    if USE_MOCK:
        # Simulate a Black-Scholes-like price based on moneyness
        atm = _ATM_APPROX.get(underlying, 25000)
        iv = 0.15
        T = 0.02  # ~5 trading days
        dist = (atm - strike) / atm
        if option_type == "CE":
            raw = atm * 0.01 * max(0.05, 1 - abs(dist) * 3)
        else:
            raw = atm * 0.01 * max(0.05, 1 - abs(dist) * 3)
        noise = raw * 0.02 * (random.random() - 0.5)
        return round(max(0.05, raw + noise), 2)
    else:
        import requests
        r = requests.get(
            f"{API_BASE_URL}/ltp",
            params={
                "exchange": exchange,
                "underlying": underlying,
                "expiry": expiry,
                "strike": strike,
                "option_type": option_type,
            },
            headers={"x-api-key": API_KEY},
            timeout=3,
        )
        data = r.json()
        return data.get("ltp")


# ─────────────────────────────────────────────────────────────────────────────
# Historical tick data
# ─────────────────────────────────────────────────────────────────────────────

def get_spread_history(
    exchange1: str, underlying1: str, expiry1: str, strike1: int, type1: str,
    exchange2: str, underlying2: str, expiry2: str, strike2: int, type2: str,
    trade_date: date,
    ratio: float = 1.0,
) -> pd.DataFrame:
    """
    Return tick-by-tick spread data for the given date.

    Columns: timestamp (datetime), leg1_price, leg2_price, spread
    spread = leg1_price - (leg2_price * ratio)
    """
    if USE_MOCK:
        return _mock_spread_history(trade_date, ratio)
    else:
        import requests
        r = requests.get(
            f"{API_BASE_URL}/spread/history",
            params={
                "exchange1": exchange1, "underlying1": underlying1,
                "expiry1": expiry1, "strike1": strike1, "type1": type1,
                "exchange2": exchange2, "underlying2": underlying2,
                "expiry2": expiry2, "strike2": strike2, "type2": type2,
                "date": trade_date.isoformat(),
                "ratio": ratio,
            },
            headers={"x-api-key": API_KEY},
            timeout=10,
        )
        rows = r.json()["ticks"]
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df


def _mock_spread_history(trade_date: date, ratio: float = 1.0) -> pd.DataFrame:
    """Generate realistic intraday spread ticks using a correlated random walk."""
    open_time = datetime.combine(trade_date, datetime.strptime("09:15", "%H:%M").time())
    close_time = datetime.combine(trade_date, datetime.strptime("15:30", "%H:%M").time())

    # Generate 1-second ticks
    timestamps = []
    t = open_time
    while t <= close_time:
        timestamps.append(t)
        t += timedelta(seconds=1)

    n = len(timestamps)
    seed = int(trade_date.strftime("%Y%m%d"))
    rng = np.random.default_rng(seed)

    # Leg 1 price random walk
    leg1_start = 80 + rng.uniform(-20, 40)
    leg1_vol = 0.003
    leg1_prices = [leg1_start]
    for _ in range(n - 1):
        leg1_prices.append(max(0.5, leg1_prices[-1] * (1 + rng.normal(0, leg1_vol))))

    # Leg 2 correlated
    leg2_start = 25 + rng.uniform(-5, 15)
    leg2_vol = 0.004
    leg2_prices = [leg2_start]
    for i in range(n - 1):
        corr = 0.65 * (leg1_prices[i] / leg1_prices[i - 1] - 1) if i > 0 else 0
        leg2_prices.append(max(0.5, leg2_prices[-1] * (1 + rng.normal(corr * 0.5, leg2_vol))))

    leg1 = np.array(leg1_prices)
    leg2 = np.array(leg2_prices)
    spread = leg1 - (leg2 * ratio)

    df = pd.DataFrame({
        "timestamp": timestamps,
        "leg1_price": np.round(leg1, 2),
        "leg2_price": np.round(leg2, 2),
        "spread": np.round(spread, 2),
    })
    return df


# ─────────────────────────────────────────────────────────────────────────────
# OHLC helpers
# ─────────────────────────────────────────────────────────────────────────────

def resample_spread(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
    """
    Resample tick data to the desired time resolution.
    resolution: 'Tick' | '30s' | '1min' | '5min' | '15min'
    """
    if df.empty:
        return df

    if resolution == "Tick":
        return df[["timestamp", "spread"]].copy()

    freq_map = {
        "30 Seconds": "30s",
        "1 Minute": "1min",
        "5 Minutes": "5min",
        "15 Minutes": "15min",
    }
    freq = freq_map.get(resolution, "1min")

    df2 = df.set_index("timestamp")
    ohlc = df2["spread"].resample(freq).agg(["first", "max", "min", "last"])
    ohlc.columns = ["open", "high", "low", "close"]
    ohlc = ohlc.dropna().reset_index()
    ohlc.rename(columns={"timestamp": "timestamp"}, inplace=True)
    return ohlc


def compute_day_stats(df: pd.DataFrame) -> dict:
    """Return open, high, low, current (last) spread and their timestamps."""
    if df.empty:
        return {"open": None, "high": None, "low": None, "current": None,
                "high_time": None, "low_time": None}

    series = df["spread"]
    return {
        "open": round(float(series.iloc[0]), 2),
        "high": round(float(series.max()), 2),
        "low": round(float(series.min()), 2),
        "current": round(float(series.iloc[-1]), 2),
        "high_time": df.loc[series.idxmax(), "timestamp"],
        "low_time": df.loc[series.idxmin(), "timestamp"],
    }
