"""
fyers_auth.py - Login flow rebuilt with native Streamlit widgets.

Why this version is different:
Streamlit renders custom HTML (via components.html) inside a locked-down
"sandboxed" iframe. Browsers block sandboxed content from redirecting the
real browser tab, no matter what JavaScript is used (target="_top",
window.top.location, etc). That's why the old HTML/JS-based buttons looked
correct but silently did nothing on click.

This version avoids the problem entirely by using Streamlit's own native
widgets (st.link_button, st.text_input, st.button) for anything that needs
to navigate or send data back to Python. Custom HTML/CSS is only used for
pure decoration.
"""

import streamlit as st
from fyers_apiv3 import fyersModel
from datetime import date
from urllib.parse import urlparse, parse_qs
import json
import os

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
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump({"token": token, "date": date.today().isoformat()}, f)
    except Exception:
        pass


def _load_token() -> str | None:
    try:
        if not os.path.exists(_TOKEN_FILE):
            return None
        with open(_TOKEN_FILE) as f:
            data = json.load(f)
        if data.get("date") == date.today().isoformat():
            return data.get("token")
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


def _extract_auth_code(raw_url: str) -> str | None:
    """Pull the auth_code query param out of a pasted redirect URL."""
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return None
    try:
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        if "auth_code" in qs and qs["auth_code"]:
            return qs["auth_code"][0]
    except Exception:
        pass
    # Fallback: maybe they pasted just the raw code itself (Fyers auth codes
    # are long JWT-like strings that start with "ey").
    if raw_url.startswith("ey") and len(raw_url) > 20:
        return raw_url
    return None


_LOGIN_CSS = """
<style>
.block-container{padding:2rem 1rem 2rem!important;max-width:100%!important}
header[data-testid="stHeader"]{display:none!important}
[data-testid="stToolbar"]{display:none!important}
footer{display:none!important}
html,body,.stApp{background:#06080f!important}

.login-card-title{
  font-family:'JetBrains Mono',monospace;font-size:1.4rem;font-weight:700;
  color:#f1f3f9;text-align:center;margin-bottom:.2rem;
}
.login-card-sub{
  text-align:center;color:#8b92a8;font-size:.85rem;margin-bottom:1.5rem;
}
.login-divider{
  text-align:center;color:#8b92a8;font-size:.7rem;letter-spacing:2px;
  text-transform:uppercase;margin:1rem 0;
}

/* Style Streamlit's native buttons/inputs to fit the dark theme */
div[data-testid="stTextInput"] input{
  background:rgba(22,27,44,.6)!important;border:1px solid #1e263d!important;
  color:#f1f3f9!important;border-radius:10px!important;
}
.stButton>button, .stLinkButton>a{
  border-radius:10px!important;font-weight:600!important;
}
</style>
"""


def render_login_page():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    page = st.session_state.get("auth_page", "login")

    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        if page == "generate":
            _render_generate_view()
        else:
            _render_login_view()


def _render_login_view():
    st.markdown('<div class="login-card-title">📈 Option Spread Analyzer</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-card-sub">Connect your Fyers account to continue</div>', unsafe_allow_html=True)

    auth_url = generate_auth_url()
    if auth_url:
        st.link_button("🔗  Login with Fyers", auth_url, use_container_width=True)
    else:
        st.warning("Couldn't generate the Fyers login link — check your Streamlit secrets.")

    st.markdown('<div class="login-divider">then paste your auth code below</div>', unsafe_allow_html=True)

    code = st.text_input(
        "Auth code",
        type="password",
        placeholder="Paste your auth code here",
        label_visibility="collapsed",
        key="auth_code_input",
    )

    if st.button("Login", type="primary", use_container_width=True):
        if not code or len(code.strip()) < 10:
            st.warning("Please paste a valid auth code first.")
        else:
            with st.spinner("🔐 Connecting to Fyers..."):
                token = generate_access_token(code.strip())
            if token:
                st.session_state["fyers_access_token"] = token
                st.session_state["token_date"] = date.today().isoformat()
                st.session_state.pop("auth_page", None)
                st.session_state.pop("_extracted_code", None)
                st.rerun()

    if st.button("🛡️  Generate Authentication Code", use_container_width=True):
        st.session_state["auth_page"] = "generate"
        st.rerun()


def _render_generate_view():
    st.markdown('<div class="login-card-title">Generate Authentication Code</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-card-sub">Paste the full redirect URL you landed on after logging into Fyers.</div>',
        unsafe_allow_html=True,
    )

    raw_url = st.text_input(
        "Redirect URL",
        placeholder="Paste your redirect URL here...",
        key="redirect_url_input",
    )

    if st.button("Generate Code", type="primary", use_container_width=True):
        if not raw_url:
            st.warning("Please paste your redirect URL first.")
            st.session_state["_extracted_code"] = None
        else:
            extracted = _extract_auth_code(raw_url)
            if extracted:
                st.session_state["_extracted_code"] = extracted
            else:
                st.session_state["_extracted_code"] = None
                st.error("❌ Could not find an auth_code in that URL. Paste the full redirect link.")

    extracted = st.session_state.get("_extracted_code")
    if extracted:
        st.success("Your authentication code:")
        st.code(extracted, language=None)
        st.caption("Copy this and paste it into the auth code field on the login page.")

    if st.button("← Back to Login", use_container_width=True):
        st.session_state.pop("auth_page", None)
        st.session_state.pop("_extracted_code", None)
        st.rerun()
