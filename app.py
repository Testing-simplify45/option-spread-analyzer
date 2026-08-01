import streamlit as st

st.set_page_config(
    page_title="Option Spread Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Palette ── */
  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --accent:   #58a6ff;
    --green:    #3fb950;
    --red:      #f85149;
    --muted:    #8b949e;
    --text:     #e6edf3;
    --warning:  #d29922;
  }

  /* Reset Streamlit chrome */
  html, body, .stApp { background-color: var(--bg) !important; color: var(--text); }
  .block-container { padding: 1.2rem 2rem 2rem; max-width: 1600px; }
  header[data-testid="stHeader"] { background: var(--bg); border-bottom: 1px solid var(--border); }

  /* ── Typography ── */
  h1, h2, h3, h4 { font-family: 'JetBrains Mono', monospace; letter-spacing: -0.5px; color: var(--text); }
  p, label, div { font-family: 'Inter', sans-serif; }

  /* ── Tab bar ── */
  .stTabs [role="tablist"] {
    background: var(--surface);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    border: 1px solid var(--border);
  }
  .stTabs [role="tab"] {
    border-radius: 7px;
    color: var(--muted);
    font-weight: 600;
    font-size: 0.9rem;
    padding: 8px 20px;
    transition: all 0.15s;
  }
  .stTabs [aria-selected="true"] {
    background: var(--accent) !important;
    color: #0d1117 !important;
  }

  /* ── Metric cards ── */
  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .metric-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .metric-value { font-size: 1.6rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  .metric-value.pos { color: var(--green); }
  .metric-value.neg { color: var(--red); }
  .metric-value.neutral { color: var(--text); }

  /* ── Spread table ── */
  .spread-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
    font-family: 'JetBrains Mono', monospace;
  }
  .spread-table thead tr {
    background: var(--surface);
    color: var(--muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    position: sticky;
    top: 0;
    z-index: 1;
  }
  .spread-table th, .spread-table td {
    padding: 10px 14px;
    text-align: right;
    border-bottom: 1px solid var(--border);
  }
  .spread-table th:first-child, .spread-table td:first-child { text-align: left; }
  .spread-table tbody tr:hover { background: rgba(88,166,255,0.04); }
  .spread-pos { color: var(--green); font-weight: 600; }
  .spread-neg { color: var(--red);   font-weight: 600; }
  .spread-zero { color: var(--muted); }

  /* ── Inputs ── */
  .stSelectbox > div > div, .stNumberInput > div > div > input,
  .stDateInput > div > div > input, .stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
  }
  div[data-baseweb="select"] > div { background: var(--surface) !important; border-color: var(--border) !important; }

  /* ── Buttons ── */
  .stButton > button {
    background: var(--surface);
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 4px 14px;
    transition: all 0.15s;
  }
  .stButton > button:hover { background: var(--accent); color: var(--bg); }

  /* ── Section headers ── */
  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 1.2rem 0 0.6rem;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  .section-header h3 { margin: 0; font-size: 0.9rem; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; }
  .section-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }

  /* ── Live badge ── */
  .live-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(63,185,80,0.12); border: 1px solid rgba(63,185,80,0.3);
    border-radius: 20px; padding: 3px 10px;
    font-size: 0.72rem; font-weight: 700; color: var(--green); letter-spacing: 1px;
  }
  .live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green);
              animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  /* ── Dividers ── */
  .leg-divider { border: none; border-top: 1px dashed var(--border); margin: 1rem 0; }

  /* ── Chart container ── */
  .chart-meta {
    display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px;
  }
  .chart-meta-item {
    font-size: 0.78rem; font-family: 'JetBrains Mono', monospace;
    color: var(--muted);
  }
  .chart-meta-item span { color: var(--text); font-weight: 600; margin-left: 4px; }
</style>
""", unsafe_allow_html=True)

# ── App Header ──────────────────────────────────────────────────────────────
col_title, col_badge = st.columns([6, 1])
with col_title:
    st.markdown("## 📈 Option Spread Analyzer")
with col_badge:
    st.markdown('<div class="live-badge"><div class="live-dot"></div>LIVE</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊  Spread Analysis", "⚡  NFO-BFO Spread"])

with tab1:
    from tabs.tab_spread_analysis import render_tab
    render_tab()

with tab2:
    from tabs.tab_nfo_bfo import render_tab as render_tab2
    render_tab2()
