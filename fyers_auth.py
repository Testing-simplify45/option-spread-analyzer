"""
fyers_auth.py
=============
Handles Fyers API authentication using manual auth code entry.
This approach is more reliable with Streamlit Cloud.
"""

import streamlit as st
from fyers_apiv3 import fyersModel
from datetime import date


def get_fyers_credentials():
    """Get Fyers credentials from Streamlit secrets."""
    try:
        client_id = st.secrets["fyers"]["client_id"]
        secret_key = st.secrets["fyers"]["secret_key"]
        redirect_url = st.secrets["fyers"]["redirect_url"]
        return client_id, secret_key, redirect_url
    except Exception:
        st.error("❌ Fyers credentials not found in Streamlit secrets!")
        return None, None, None


def generate_auth_url() -> str | None:
    """Generate the Fyers login URL."""
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
    """Exchange auth code for access token."""
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
            return response["access_token"]
        else:
            st.error(f"❌ Token error: {response.get('message', response)}")
            return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None


def get_fyers_client():
    """Get authenticated Fyers client from session."""
    if "fyers_access_token" not in st.session_state:
        return None

    token = st.session_state["fyers_access_token"]
    client_id, _, _ = get_fyers_credentials()

    if not client_id or not token:
        return None

    fyers = fyersModel.FyersModel(
        client_id=client_id,
        token=token,
        log_path="",
    )
    return fyers


def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return (
        "fyers_access_token" in st.session_state
        and st.session_state["fyers_access_token"] is not None
    )


def check_token_expiry():
    """Clear token if it's from a previous day."""
    if "token_date" in st.session_state:
        if st.session_state["token_date"] != date.today().isoformat():
            st.session_state.pop("fyers_access_token", None)
            st.session_state.pop("token_date", None)
            st.warning("⚠️ Session expired. Please login again.")
            st.rerun()


def render_login_page():
    """
    Render Fyers login UI using manual auth code entry.

    HOW IT WORKS:
    1. User clicks the login link → goes to Fyers login page
    2. After login, Fyers redirects to redirect_url with ?auth_code=XXXX in the URL
    3. User copies that auth_code from the URL bar and pastes it here
    4. We exchange it for an access token
    """

    st.markdown("""
    <div style="max-width:520px;margin:40px auto;background:#161b22;
                border:1px solid #30363d;border-radius:16px;padding:36px;">
        <div style="text-align:center;font-size:2.5rem;margin-bottom:12px">📈</div>
        <h2 style="color:#e6edf3;text-align:center;font-family:JetBrains Mono,monospace;
                   margin-bottom:6px">Option Spread Analyzer</h2>
        <p style="color:#8b949e;text-align:center;font-size:0.88rem;margin-bottom:28px">
            Connect your Fyers account for live market data
        </p>
    </div>
    """, unsafe_allow_html=True)

    auth_url = generate_auth_url()

    if not auth_url:
        return

    # Step 1 — Open login URL
    st.markdown("### Step 1 — Login to Fyers")
    st.markdown(f"""
    <a href="{auth_url}" target="_blank" style="
        display:inline-block;
        background:#58a6ff;color:#0d1117;
        padding:12px 28px;border-radius:8px;
        text-decoration:none;font-weight:700;font-size:0.95rem;
    ">🔐 Open Fyers Login Page</a>
    """, unsafe_allow_html=True)

    st.markdown("""
    <p style="color:#8b949e;font-size:0.82rem;margin-top:10px">
        ☝️ Click the button above. Login with your Fyers credentials.<br>
        After login you will be redirected to a page — <b style="color:#e6edf3">
        look at the URL in your browser's address bar.</b>
    </p>
    """, unsafe_allow_html=True)

    # Step 2 — Copy auth code from URL
    st.markdown("### Step 2 — Copy the Auth Code")
    st.markdown("""
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
                padding:14px;font-family:JetBrains Mono,monospace;font-size:0.82rem;
                color:#8b949e;margin-bottom:8px">
        After login, your browser URL will look like:<br><br>
        <span style="color:#58a6ff">https://option-spread-analyzer-test.streamlit.app</span>
        <span style="color:#f85149">?auth_code=</span>
        <span style="color:#3fb950">ey.XXXXXXXXXXXXXXXXXX</span>
        <span style="color:#8b949e">&state=...</span><br><br>
        Copy everything after <span style="color:#f85149">auth_code=</span> 
        up to the <span style="color:#d29922">&</span> symbol.
    </div>
    """, unsafe_allow_html=True)

    # Step 3 — Paste and submit
    st.markdown("### Step 3 — Paste Auth Code Below")
    auth_code = st.text_input(
        "Paste your auth code here",
        placeholder="ey.XXXXXXXXXXXXXXXXXX...",
        key="auth_code_input",
    )

    if st.button("✅ Connect to Fyers", key="connect_btn"):
        if not auth_code or len(auth_code) < 10:
            st.error("❌ Please paste a valid auth code!")
        else:
            with st.spinner("Connecting to Fyers..."):
                token = generate_access_token(auth_code.strip())
                if token:
                    st.session_state["fyers_access_token"] = token
                    st.session_state["token_date"] = date.today().isoformat()
                    st.success("✅ Connected! Loading your app...")
                    st.rerun()
