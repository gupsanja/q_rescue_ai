import streamlit as st
from auth import (
    is_logged_in,
    log_in,
    render_sidebar_nav,
    validate_login,
)
from ui_theme import apply_global_style

# Configure the Streamlit page — title, icon, and wide layout
st.set_page_config(
    page_title="Q-Rescue AI",
    page_icon=":ambulance:",
    layout="wide",
)

# Apply the shared dark emergency-control-centre theme
apply_global_style()

# Inject page-specific CSS for the login and home title layouts
st.markdown(
    """
    <style>
        .login-title {
            text-align: center;
            margin: 3.5rem auto 1.5rem auto;
        }

        .login-title-mark,
        .home-title-mark {
            width: 76px;
            height: 76px;
            margin: 0 auto 1rem auto;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            background: #005eb8;
            color: #ffffff;
            font-size: 1.35rem;
            font-weight: 950;
            box-shadow: 0 18px 38px rgba(0, 94, 184, 0.28);
        }

        .login-title h1,
        .home-title h1 {
            color: #212b32 !important;
            font-size: 3.4rem;
            line-height: 1;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0;
        }

        .login-title p {
            color: #4c6272 !important;
            margin-top: 0.8rem;
            font-weight: 700;
        }

        .home-title {
            min-height: 70vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .home-title h1 {
            font-size: 4rem;
            text-shadow: 0 8px 32px rgba(0, 61, 120, 0.14);
        }

        .home-red-line {
            width: 150px;
            height: 7px;
            margin-top: 1.3rem;
            border-radius: 999px;
            background: #00a499;
            box-shadow: 0 10px 24px rgba(0, 164, 153, 0.25);
        }

        @media (max-width: 700px) {
            .login-title h1,
            .home-title h1 {
                font-size: 2.35rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Show the login screen if the user is not authenticated
if not is_logged_in():
    # Render the Q-Rescue branding above the login form
    st.markdown(
        """
        <div class="login-title">
            <div class="login-title-mark">QR</div>
            <h1>Q-Rescue AI</h1>
            <p>Sheffield Emergency Response Control Centre</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Centre the login form using three columns
    left, login_col, right = st.columns([1.2, 1, 1.2])
    with login_col:
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Log In", use_container_width=True)

        # Validate credentials and start the session on success
        if submitted:
            if validate_login(username, password):
                log_in(username)
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    # Hide the sidebar until the user is logged in
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Render the sidebar navigation for authenticated users
render_sidebar_nav()

# Show the home landing page with Q-Rescue branding
st.markdown(
    """
    <div class="home-title">
        <div class="home-title-mark">QR</div>
        <h1>Q-Rescue Sheffield Control Centre</h1>
        <div class="home-red-line"></div>
    </div>
    """,
    unsafe_allow_html=True,
)
