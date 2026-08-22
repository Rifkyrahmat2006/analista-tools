"""
Auth Middleware untuk Streamlit
==================================
Login form, session-state guard, dan helper role-check.
Dipanggil di awal SETIAP halaman (app.py + semua pages/*.py) supaya
akses ke seluruh aplikasi terkontrol.

PERSISTENSI LOGIN LINTAS REFRESH:
st.session_state Streamlit hidup per-koneksi WebSocket di server dan
HILANG setiap kali browser refresh (WS baru dianggap "sesi" baru oleh
Streamlit) — ini BUKAN bug, itu cara kerja normal Streamlit. Supaya
user tidak ke-logout tiap refresh, token sesi acak disimpan di COOKIE
BROWSER (lewat streamlit-cookies-controller) dan divalidasi balik ke
tabel `sessions` di database pada awal tiap render halaman.
"""

import streamlit as st
from streamlit_cookies_controller import CookieController

from utils.db import (
    authenticate, log_action, init_db, ROLES,
    create_session_token, get_user_by_session_token, delete_session_token,
)

SESSION_KEYS = ["auth_user", "auth_role", "auth_username", "auth_full_name"]
COOKIE_NAME = "analista_session_token"


def _get_cookie_controller() -> CookieController:
    # PENTING: CookieController TIDAK boleh dibungkus @st.cache_resource —
    # secara internal dia memanggil custom Streamlit component (mirip
    # widget), dan cache_resource/cache_data melarang widget command di
    # dalamnya (CachedWidgetWarning -> exception di Streamlit versi baru).
    # Component call itu murah & idempotent (dikenali lewat `key`), jadi
    # aman dibuat ulang tiap rerun — tidak perlu di-cache sama sekali.
    return CookieController(key="analista_cookie_controller")


def _restore_session_from_cookie() -> bool:
    """
    Kalau session_state kosong (mis. abis refresh) tapi ada cookie token
    valid, restore login dari situ. Return True kalau berhasil restore.
    """
    if st.session_state.get("auth_user"):
        return True  # sudah login di session_state, tidak perlu restore

    controller = _get_cookie_controller()
    token = controller.get(COOKIE_NAME)
    if not token:
        return False

    user = get_user_by_session_token(token)
    if not user:
        return False

    st.session_state["auth_user"] = True
    st.session_state["auth_user_id"] = user["id"]
    st.session_state["auth_username"] = user["username"]
    st.session_state["auth_full_name"] = user["full_name"]
    st.session_state["auth_role"] = user["role"]
    st.session_state["auth_session_token"] = token
    return True


def is_logged_in() -> bool:
    if st.session_state.get("auth_user") is not None:
        return True
    return _restore_session_from_cookie()


def current_user() -> dict:
    """Return dict user aktif, atau {} kalau belum login."""
    if not is_logged_in():
        return {}
    return {
        "id": st.session_state.get("auth_user_id"),
        "username": st.session_state.get("auth_username"),
        "full_name": st.session_state.get("auth_full_name"),
        "role": st.session_state.get("auth_role"),
    }


def _do_login(username: str, password: str) -> bool:
    user = authenticate(username, password)
    if not user:
        return False

    token = create_session_token(user["id"])

    st.session_state["auth_user"] = True
    st.session_state["auth_user_id"] = user["id"]
    st.session_state["auth_username"] = user["username"]
    st.session_state["auth_full_name"] = user["full_name"]
    st.session_state["auth_role"] = user["role"]
    st.session_state["auth_session_token"] = token

    controller = _get_cookie_controller()
    controller.set(COOKIE_NAME, token)

    log_action(user["username"], user["role"], "login", "Login berhasil")
    return True


def logout() -> None:
    user = current_user()
    if user:
        log_action(user["username"], user["role"], "logout", "Logout")

    token = st.session_state.get("auth_session_token")
    if token:
        delete_session_token(token)

    controller = _get_cookie_controller()
    controller.remove(COOKIE_NAME)

    for key in SESSION_KEYS + ["auth_user_id", "auth_session_token"]:
        st.session_state.pop(key, None)


def render_login_form() -> None:
    """Tampilkan form login full-page. Panggil lalu st.stop() kalau belum login."""
    init_db()

    # Sembunyikan total sidebar (termasuk daftar navigasi halaman) selama
    # user belum login — jangan bocorkan struktur menu aplikasi sebelum auth.
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 0 1rem 0;">
            <h2>🔒 Login — Analista Tools</h2>
            <p style="color: #888;">Masuk untuk mengakses dataset dan fitur analisis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True, type="primary", icon=":material/login:")

            if submitted:
                if not username or not password:
                    st.error("Username dan password wajib diisi.")
                elif _do_login(username, password):
                    st.rerun()
                else:
                    st.error("Username/password salah, atau akun tidak aktif.")


def require_login() -> dict:
    """
    Panggil di awal tiap halaman. Kalau belum login, tampilkan form login
    dan st.stop() (halaman berhenti render). Return dict user kalau sudah login.
    """
    if not is_logged_in():
        render_login_form()
        st.stop()
    return current_user()


def require_role(*allowed_roles: str) -> dict:
    """
    Panggil setelah require_login() untuk halaman yang butuh role tertentu.
    Kalau role user tidak diizinkan, tampilkan error dan st.stop().
    """
    user = require_login()
    if user["role"] not in allowed_roles:
        st.error(
            f":material/block: Akses ditolak. Halaman ini membutuhkan role: "
            f"{', '.join(allowed_roles)}. Role Anda: {user['role']}."
        )
        st.stop()
    return user


def render_user_badge_sidebar() -> None:
    """Tampilkan info user + tombol logout di sidebar. Panggil di semua halaman."""
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown("---")
        role_emoji = {"superadmin": ":material/shield_person:", "admin": ":material/admin_panel_settings:", "staff": ":material/person:"}
        st.caption(f"{role_emoji.get(user['role'], '')} **{user['full_name']}**  \n`{user['role']}`")
        if st.button(":material/logout: Logout", use_container_width=True, key="sidebar_logout_btn"):
            logout()
            st.rerun()
