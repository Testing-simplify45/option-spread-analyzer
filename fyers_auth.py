"""
fyers_auth.py
=============
Handles Fyers API authentication and token management.
Provides a simple login flow inside the Streamlit app.
"""

import streamlit as st
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import urllib.parse
from datetime import datetime, date
import os


def get_fyers_credentials():
    """Get Fyers credentials from Streamlit secrets."""
    try:
        client_id = st.secrets["fyers"]["client_id"]
        secret_key = st.secrets["fyers"]["secret_key"]
        redirect_url = st.secrets["fyers"]["redirect_url"]
        return client_id, secret_key, redirect_url
    except Exception:
        st.error("❌ Fyers credentials not found in Streamlit secrets! Please add them in Settings → Secrets.")
        return None, None, None


def generate_auth_url():
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
            st.error(f"Token generation failed: {response}")
            return None
    except Exception as e:
        st.error(f"Error generating token: {e}")
        return None


def get_fyers_client():
    """
    Get an authenticated Fyers client.
    Returns None if not authenticated.
    """
    # Check if token exists in session state
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
    """Check if user is authenticated with Fyers."""
    return "fyers_access_token" in st.session_state and st.session_state["fyers_access_token"] is not None


def render_login_page():
    """
    Render the Fyers login UI.
    Call this at the top of your app if not authenticated.
    """
    st.markdown("""
    <div style="
        max-width: 480px;
        margin: 60px auto;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
    ">
        <div style="font-size: 3rem; margin-bottom: 16px">📈</div>
        <h2 style="color: #e6edf3; margin-bottom: 8px; font-family: JetBrains Mono, monospace;">
            Option Spread Analyzer
        </h2>
        <p style="color: #8b949e; margin-bottom: 32px; font-size: 0.9rem;">
            Connect your Fyers account to access live market data
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Check if we have an auth code in URL params
    params = st.query_params
    auth_code = params.get("auth_code", None)

    if auth_code:
        with st.spinner("🔐 Generating access token..."):
            token = generate_access_token(auth_code)
            if token:
                st.session_state["fyers_access_token"] = token
                st.session_state["token_date"] = date.today().isoformat()
                # Clear URL params
                st.query_params.clear()
                st.success("✅ Successfully connected to Fyers!")
                st.rerun()
            else:
                st.error("❌ Failed to generate token. Please try again.")

    else:
        # Show login button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            auth_url = generate_auth_url()
            if auth_url:
                st.markdown(f"""
                <a href="{auth_url}" target="_self" style="
                    display: block;
                    background: #58a6ff;
                    color: #0d1117;
                    padding: 14px 28px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 700;
                    font-size: 1rem;
                    text-align: center;
                    margin: 20px auto;
                ">
                    🔐 Login with Fyers
                </a>
                """, unsafe_allow_html=True)

                st.markdown("""
                <p style="color: #8b949e; font-size: 0.78rem; text-align: center; margin-top: 16px;">
                    You'll be redirected to Fyers login page.<br>
                    After login, you'll be brought back here automatically.
                </p>
                """, unsafe_allow_html=True)


def check_token_expiry():
    """Check if token is from a previous day and clear it."""
    if "token_date" in st.session_state:
        token_date = st.session_state["token_date"]
        if token_date != date.today().isoformat():
            # Token expired - clear it
            st.session_state.pop("fyers_access_token", None)
            st.session_state.pop("token_date", None)
            st.warning("⚠️ Your Fyers session has expired. Please login again.")
            st.rerun()
