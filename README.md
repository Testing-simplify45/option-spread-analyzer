# Option Spread Analyzer

A real-time option spread analysis web app built with Streamlit.

## Features

### Tab 1 — Spread Analysis
- Manually select any two NSE/BSE option contracts
- Live spread = Leg 1 LTP − Leg 2 LTP
- Historical chart with selectable date and time resolution (Tick / 30s / 1m / 5m / 15m)
- OHLC stats: Open, High (with timestamp), Low (with timestamp), Current
- Interactive Plotly chart with zoom, pan, hover

### Tab 2 — NFO-BFO Spread Analysis
- Auto-generated strike ladder (7 CE + 7 PE + 7 CE + 7 PE = 28 rows)
- Configurable: Exchange, Index, Ratio, Multiplier, Add-on, Date, Expiry
- Second-leg strike = `RoundToNearest50(First Strike / Multiplier)`
- Spread = `First Leg Premium − (Second Leg Premium × Ratio)`
- Each row shows: First Strike, Second Strike, Current Spread, Day High, Day Low
- "View Chart" button per row reveals inline historical chart with OHLC stats
- Positive spreads in green, negative in red
- Refresh button clears cache and re-fetches live prices

## Setup

### Local development
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Streamlit Cloud
1. Push this repository to GitHub
2. Go to share.streamlit.io → New app
3. Select your repo and set `app.py` as the main file

## Connecting your live data API

All data access is in `data_api.py`. Set `USE_MOCK = False` and fill in:

```python
API_BASE_URL = "https://your-api-endpoint.com"
API_KEY      = "your-api-key-here"
```

Then implement the API calls in each function:

| Function | Purpose |
|---|---|
| `get_expiries(exchange, underlying)` | List of available expiry dates |
| `get_strikes(exchange, underlying, expiry)` | List of strikes for a contract |
| `get_ltp(exchange, underlying, expiry, strike, option_type)` | Current last traded price |
| `get_spread_history(...)` | Tick-by-tick spread dataframe for a date |

The mock implementations produce realistic random-walk data for UI development.

## File structure

```
app.py                  ← Entry point, tab routing, global CSS
data_api.py             ← All data fetching (mock + real)
chart_utils.py          ← Plotly chart builder
tabs/
  tab_spread_analysis.py ← Tab 1 implementation
  tab_nfo_bfo.py         ← Tab 2 implementation
.streamlit/
  config.toml           ← Dark theme, wide layout
requirements.txt
```

## Spread Formulas

**Tab 1:**
```
Spread = Leg1 LTP − Leg2 LTP
```

**Tab 2:**
```
Second Strike  = RoundToNearest50(First Strike / Multiplier)
Spread         = First Leg Premium − (Second Leg Premium × Ratio)
```

## Performance notes

- Historical data is cached via `@st.cache_data(ttl=30)` — live spread cells refresh every 30 seconds automatically on re-run
- Instrument metadata (expiries, strikes) is cached with `lru_cache` in `data_api.py`
- Only the specific option contracts in the visible rows are fetched — no bulk download
- "View Chart" renders charts lazily (only on click), keeping initial page load fast
