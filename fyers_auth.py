"""
fyers_auth.py
=============
Fyers authentication with:
- Beautiful login page matching design spec
- Generate Auth Code page
- Persistent token storage (survives tab close, valid all day)
"""

import streamlit as st
from fyers_apiv3 import fyersModel
from datetime import date
import json
import os

# Token stored in a temp file so it survives browser tab closes
_TOKEN_FILE = "/tmp/fyers_token.json"


def get_fyers_credentials():
    try:
        client_id = st.secrets["fyers"]["client_id"]
        secret_key = st.secrets["fyers"]["secret_key"]
        redirect_url = st.secrets["fyers"]["redirect_url"]
        return client_id, secret_key, redirect_url
    except Exception:
        st.error("❌ Fyers credentials not found in Streamlit secrets!")
        return None, None, None


def generate_auth_url() -> str | None:
    client_id, secret_key, redirect_url = get_fyers_credentials()
    if not client_id:
        return None
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_url,
        response_type="code",
        grant_type="authorization_code",
    )
    return session.generate_authcode()


def generate_access_token(auth_code: str) -> str | None:
    client_id, secret_key, redirect_url = get_fyers_credentials()
    if not client_id:
        return None
    try:
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key,
            redirect_uri=redirect_url,
            response_type="code",
            grant_type="authorization_code",
        )
        session.set_token(auth_code)
        response = session.generate_token()
        if response.get("s") == "ok":
            token = response["access_token"]
            _save_token(token)
            return token
        else:
            st.error(f"❌ {response.get('message', 'Token generation failed')}")
            return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None


def _save_token(token: str):
    """Save token to file with today's date."""
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump({"token": token, "date": date.today().isoformat()}, f)
    except Exception:
        pass


def _load_token() -> str | None:
    """Load token from file if it's from today."""
    try:
        if not os.path.exists(_TOKEN_FILE):
            return None
        with open(_TOKEN_FILE) as f:
            data = json.load(f)
        if data.get("date") == date.today().isoformat():
            return data.get("token")
        # Token is from a previous day - delete it
        os.remove(_TOKEN_FILE)
        return None
    except Exception:
        return None


def get_fyers_client():
    token = st.session_state.get("fyers_access_token") or _load_token()
    if not token:
        return None
    client_id, _, _ = get_fyers_credentials()
    if not client_id:
        return None
    return fyersModel.FyersModel(client_id=client_id, token=token, log_path="")


def is_authenticated() -> bool:
    # Check session first, then fall back to saved file
    if st.session_state.get("fyers_access_token"):
        return True
    token = _load_token()
    if token:
        st.session_state["fyers_access_token"] = token
        st.session_state["token_date"] = date.today().isoformat()
        return True
    return False


def check_token_expiry():
    if "token_date" in st.session_state:
        if st.session_state["token_date"] != date.today().isoformat():
            st.session_state.pop("fyers_access_token", None)
            st.session_state.pop("token_date", None)
            try:
                os.remove(_TOKEN_FILE)
            except Exception:
                pass
            st.rerun()


# ── Shared CSS & background ──────────────────────────────────────────────────

_BASE_STYLES = """
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .block-container { padding: 0 !important; max-width: 100% !important; }
  header[data-testid="stHeader"] { display: none !important; }
  [data-testid="stToolbar"] { display: none !important; }
  footer { display: none !important; }
  html, body, .stApp {
    background-color: #06080f !important;
    background-image:
      radial-gradient(circle at 50% 0%, rgba(27,117,255,.07) 0%, transparent 55%),
      linear-gradient(rgba(30,38,61,.12) 1px, transparent 1px),
      linear-gradient(90deg, rgba(30,38,61,.12) 1px, transparent 1px) !important;
    background-size: 100% 100%, 30px 30px, 30px 30px !important;
  }
  * { box-sizing: border-box; }
  .page-wrap {
    font-family: 'Plus Jakarta Sans', sans-serif;
    min-height: 100vh;
    display: flex; flex-direction: column;
    position: relative; overflow: hidden; color: #f1f3f9;
  }
  .bg-svg {
    position: fixed; inset: 0; width: 100%; height: 100%;
    pointer-events: none; opacity: 0.08; z-index: 0;
  }
  .badge {
    position: fixed; top: 16px; right: 20px;
    display: flex; align-items: center; gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: #00c676; z-index: 100;
  }
  @keyframes ping {
    0%,100% { transform: scale(1); opacity: 0.75; }
    50% { transform: scale(2); opacity: 0; }
  }
  .ping-wrap { position: relative; width: 8px; height: 8px; display: inline-block; }
  .ping-anim { animation: ping 1.5s ease-in-out infinite; position: absolute; inset: 0; border-radius: 50%; background: #00c676; display: block; }
  .ping-solid { position: absolute; inset: 0; border-radius: 50%; background: #00c676; display: block; }
  .page-center {
    flex: 1; display: flex; align-items: center; justify-content: center;
    padding: 40px 16px; position: relative; z-index: 20;
  }
  .card {
    background: rgba(14,18,32,.85); backdrop-filter: blur(16px);
    border: 1px solid #1e263d; border-radius: 20px;
    padding: 32px; box-shadow: 0 25px 60px rgba(0,0,0,.5);
  }
  .page-footer {
    position: relative; z-index: 20; padding: 16px 24px;
    display: flex; align-items: center; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #8b92a8;
  }
  .footer-links { display: flex; gap: 20px; }
  .footer-links a { color: #8b92a8; text-decoration: none; }
  .footer-links a:hover { color: #f1f3f9; }
  /* Shared input */
  .inp-wrap {
    display: flex; align-items: center;
    background: rgba(22,27,44,.6); border: 1px solid #1e263d;
    border-radius: 12px; padding: 14px 16px; margin-bottom: 16px;
    transition: border-color 0.2s;
  }
  .inp-wrap:focus-within { border-color: #00cbd6; box-shadow: 0 0 0 1px rgba(0,203,214,.15); }
  .inp-field {
    flex: 1; background: transparent; border: none; outline: none;
    color: #f1f3f9; font-family: 'JetBrains Mono', monospace;
    font-size: 13px; letter-spacing: 0.5px;
  }
  .inp-field::placeholder { color: #4b5470; }
  /* Buttons */
  .btn-blue {
    display: flex; align-items: center; justify-content: center; gap: 10px;
    width: 100%; padding: 14px; border-radius: 12px;
    background: #1b75ff; color: white; font-weight: 600; font-size: 15px;
    text-decoration: none; border: none; cursor: pointer;
    transition: background 0.2s, box-shadow 0.2s; margin-bottom: 16px;
  }
  .btn-blue:hover { background: #1560d4; box-shadow: 0 0 20px rgba(27,117,255,.35); color: white; text-decoration: none; }
  .btn-cyan {
    width: 100%; padding: 14px; border-radius: 12px;
    background: #00cbd6; color: #06080f; font-weight: 700; font-size: 15px;
    border: none; cursor: pointer; transition: box-shadow 0.2s, background 0.2s;
    margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn-cyan:hover { box-shadow: 0 0 20px rgba(0,203,214,.4); background: #00b8c2; }
  .btn-outline-cyan {
    width: 100%; padding: 13px; border-radius: 12px;
    background: rgba(0,203,214,.05); border: 1px solid rgba(0,203,214,.3);
    color: #00cbd6; font-weight: 500; font-size: 14px; cursor: pointer;
    transition: background 0.2s, border-color 0.2s;
    display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn-outline-cyan:hover { background: rgba(0,203,214,.1); border-color: rgba(0,203,214,.5); }
  .eye-btn { background: none; border: none; cursor: pointer; color: #8b92a8; padding: 0 0 0 8px; transition: color 0.2s; }
  .eye-btn:hover { color: #f1f3f9; }
</style>
"""

_BG_SVG = """
<svg class="bg-svg" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
  <polyline points="120,680 520,680 720,220 1320,220" fill="none" stroke="#00c676" stroke-width="3"/>
  <polyline points="120,680 520,680" fill="none" stroke="#ff5252" stroke-width="3"/>
  <line x1="520" y1="120" x2="520" y2="780" stroke="#1e263d" stroke-width="1" stroke-dasharray="6 6"/>
  <line x1="720" y1="120" x2="720" y2="780" stroke="#1e263d" stroke-width="1" stroke-dasharray="6 6"/>
  <text x="520" y="810" text-anchor="middle" fill="#8b92a8" font-size="11" font-family="JetBrains Mono">K₁</text>
  <text x="720" y="810" text-anchor="middle" fill="#8b92a8" font-size="11" font-family="JetBrains Mono">K₂</text>
</svg>
"""

_BADGE = lambda label: f"""
<div class="badge">
  <div class="ping-wrap"><span class="ping-anim"></span><span class="ping-solid"></span></div>
  {label}
</div>
"""

_FOOTER = """
<div class="page-footer">
  <span>© 2025 Option Spread Analyzer</span>
  <div class="footer-links">
    <a href="#">Privacy</a><a href="#">Terms</a><a href="#">Help Center</a>
  </div>
</div>
"""


# ── Login Page ───────────────────────────────────────────────────────────────

def render_login_page():
    st.markdown("""<style>
      .block-container { padding: 0 !important; max-width: 100% !important; }
      header[data-testid="stHeader"] { display: none !important; }
      [data-testid="stToolbar"] { display: none !important; }
      footer { display: none !important; }
      html, body, .stApp {
        background-color: #06080f !important;
        background-image:
          radial-gradient(circle at 50% 0%, rgba(27,117,255,.07) 0%, transparent 55%),
          linear-gradient(rgba(30,38,61,.12) 1px, transparent 1px),
          linear-gradient(90deg, rgba(30,38,61,.12) 1px, transparent 1px) !important;
        background-size: 100% 100%, 30px 30px, 30px 30px !important;
      }
    </style>""", unsafe_allow_html=True)

    auth_url = generate_auth_url() or "#"

    # Check which page to show
    page = st.session_state.get("auth_page", "login")

    if page == "generate":
        render_generate_page(auth_url)
        return

    st.markdown(_BASE_STYLES + f"""
    <div class="page-wrap">
      {_BG_SVG}
      {_BADGE("API Gateway: Online")}

      <div class="page-center">
        <div class="card" style="width:100%;max-width:440px">

          <!-- Header -->
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:28px">
            <div style="width:40px;height:40px;border-radius:10px;background:#161b2c;
                        border:1px solid #1e263d;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M4 16L10 8L16 14L20 6" stroke="#00cbd6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M4 16L10 8L16 14L20 6" stroke="#1b75ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" transform="translate(2,-2)" opacity=".5"/>
              </svg>
            </div>
            <span style="font-size:20px;font-weight:600;letter-spacing:-0.3px;color:#f1f3f9">Option Spread Analyzer</span>
          </div>

          <!-- Fyers button -->
          <a href="{auth_url}" target="_blank" class="btn-blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="opacity:.85">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor"/>
              <circle cx="12" cy="12" r="5" fill="currentColor"/>
            </svg>
            Fyers
          </a>

          <!-- Auth code input -->
          <div class="inp-wrap">
            <input class="inp-field" id="authInput" type="password" placeholder="Enter your auth code"/>
            <button class="eye-btn" onclick="toggleEye()" type="button">
              <svg id="eyeIcon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>

          <button class="btn-cyan" onclick="doLogin()" type="button">Login</button>

          <button class="btn-outline-cyan" onclick="goGenerate()" type="button">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <polyline points="9 12 11 14 15 10"/>
            </svg>
            Generate Authentication Code
          </button>

        </div>
      </div>
      {_FOOTER}
    </div>

    <script>
      function toggleEye() {{
        const inp = document.getElementById('authInput');
        const icon = document.getElementById('eyeIcon');
        if (inp.type === 'password') {{
          inp.type = 'text';
          icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
        }} else {{
          inp.type = 'password';
          icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
        }}
      }}
      function doLogin() {{
        const code = document.getElementById('authInput').value.trim();
        if (!code || code.length < 10) {{ alert('Please paste your auth code first!'); return; }}
        const url = new URL(window.location.href);
        url.searchParams.set('auth_code', code);
        window.location.href = url.toString();
      }}
      function goGenerate() {{
        const url = new URL(window.location.href);
        url.searchParams.set('auth_page', 'generate');
        window.location.href = url.toString();
      }}
    </script>
    """, unsafe_allow_html=True)

    # Handle URL params
    params = st.query_params
    if params.get("auth_page") == "generate":
        st.session_state["auth_page"] = "generate"
        st.query_params.clear()
        st.rerun()

    auth_code = params.get("auth_code")
    if auth_code and len(auth_code) > 10:
        with st.spinner("🔐 Connecting to Fyers..."):
            token = generate_access_token(auth_code.strip())
            if token:
                st.session_state["fyers_access_token"] = token
                st.session_state["token_date"] = date.today().isoformat()
                st.session_state.pop("auth_page", None)
                st.query_params.clear()
                st.rerun()


# ── Generate Auth Code Page ──────────────────────────────────────────────────

def render_generate_page(auth_url: str):
    st.markdown(_BASE_STYLES + f"""
    <div class="page-wrap">
      {_BG_SVG}
      {_BADGE("Security Module: Active")}

      <div class="page-center">
        <div class="card" style="width:100%;max-width:480px">

          <!-- Back button -->
          <button onclick="goBack()" style="
            display:flex;align-items:center;gap:8px;
            background:none;border:none;cursor:pointer;
            color:#8b92a8;font-family:'JetBrains Mono',monospace;
            font-size:11px;letter-spacing:1px;text-transform:uppercase;
            margin-bottom:24px;transition:color 0.2s;padding:0;
          " onmouseover="this.style.color='#f1f3f9'" onmouseout="this.style.color='#8b92a8'">
            ← BACK TO LOGIN
          </button>

          <!-- Title -->
          <h1 style="font-size:22px;font-weight:600;color:#f1f3f9;margin-bottom:6px">Generate Authentication Code</h1>
          <p style="font-size:12px;color:#8b92a8;margin-bottom:28px">Enter your validation link to generate a secure session token.</p>

          <!-- URL input -->
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;
                      color:#8b92a8;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">
            Redirect / Validation Link
          </div>
          <div class="inp-wrap" style="margin-bottom:12px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b92a8" stroke-width="2" style="margin-right:10px;flex-shrink:0">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            <input class="inp-field" id="urlInput" type="text" placeholder="Paste your redirect URL here..."/>
          </div>

          <button class="btn-cyan" onclick="extractCode()" type="button" style="margin-bottom:24px">
            Generate Code
          </button>

          <!-- Divider -->
          <div style="position:relative;margin-bottom:20px">
            <div style="border-top:1px solid #1e263d"></div>
            <div style="position:absolute;top:-9px;left:50%;transform:translateX(-50%);
                        background:#0e1220;padding:0 12px;
                        font-family:'JetBrains Mono',monospace;font-size:10px;
                        letter-spacing:2px;color:#8b92a8">OUTPUT</div>
          </div>

          <!-- Output label -->
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;
                      color:#8b92a8;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">
            Your Authentication Code
          </div>

          <!-- Output box -->
          <div style="background:rgba(6,8,15,.6);border:1px dashed rgba(139,146,168,.3);
                      border-radius:12px;padding:16px;min-height:100px;
                      display:flex;flex-direction:column;justify-content:space-between;
                      margin-bottom:8px">
            <p id="outputCode" style="font-family:'JetBrains Mono',monospace;font-size:13px;
                                       color:#00cbd6;word-break:break-all;line-height:1.6;
                                       min-height:40px">
              —
            </p>
            <div style="display:flex;justify-content:flex-end;margin-top:12px">
              <button id="copyBtn" onclick="copyCode()" style="
                display:flex;align-items:center;gap:6px;
                padding:6px 14px;border-radius:8px;
                background:#161b2c;border:1px solid #1e263d;
                font-size:12px;color:#8b92a8;cursor:pointer;
                transition:all 0.2s;
              " onmouseover="this.style.color='#f1f3f9';this.style.borderColor='#8b92a8'"
                onmouseout="this.style.color='#8b92a8';this.style.borderColor='#1e263d'">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy to Clipboard
              </button>
            </div>
          </div>
          <p style="font-size:10px;color:#8b92a8;font-family:'JetBrains Mono',monospace;
                    font-style:italic;opacity:0.6;margin-top:4px">
            * Copy this code and paste it into the password field on the login page.
          </p>

        </div>
      </div>
      {_FOOTER}
    </div>

    <script>
      function extractCode() {{
        const raw = document.getElementById('urlInput').value.trim();
        if (!raw) {{ alert('Please paste your redirect URL first!'); return; }}

        let code = null;

        // Try to extract auth_code from URL
        try {{
          const url = new URL(raw);
          code = url.searchParams.get('auth_code');
        }} catch(e) {{
          // Maybe they pasted just the code directly
          if (raw.startsWith('ey') && raw.length > 20) {{
            code = raw;
          }}
        }}

        const out = document.getElementById('outputCode');
        if (code) {{
          out.textContent = code;
          out.style.color = '#00cbd6';
        }} else {{
          out.textContent = '❌ Could not extract auth code. Make sure you paste the full redirect URL.';
          out.style.color = '#ff5252';
        }}
      }}

      function copyCode() {{
        const code = document.getElementById('outputCode').textContent;
        if (code === '—' || code.startsWith('❌')) {{ alert('Generate a code first!'); return; }}
        navigator.clipboard.writeText(code).then(() => {{
          const btn = document.getElementById('copyBtn');
          btn.textContent = '✓ Copied!';
          btn.style.color = '#00c676';
          setTimeout(() => {{
            btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy to Clipboard';
            btn.style.color = '#8b92a8';
          }}, 2000);
        }});
      }}

      function goBack() {{
        const url = new URL(window.location.href);
        url.searchParams.delete('auth_page');
        window.location.href = url.toString();
      }}
    </script>
    """, unsafe_allow_html=True)

    # Handle back navigation
    params = st.query_params
    if not params.get("auth_page"):
        st.session_state.pop("auth_page", None)
        st.rerun()
