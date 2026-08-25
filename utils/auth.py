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
from datetime import timedelta
from streamlit_cookies_controller import CookieController

from utils.db import (
    authenticate, log_action, init_db, ROLES,
    create_session_token, get_user_by_session_token, delete_session_token,
)

SESSION_KEYS = ["auth_user", "auth_role", "auth_username", "auth_full_name"]
COOKIE_NAME = "analista_session_token"
COOKIE_TTL_DAYS = 7  # samakan dgn SESSION_TTL_DAYS di utils/db.py


_COOKIE_CONTROLLER_STATE_KEY = "_cookie_controller_singleton"


def _get_cookie_controller() -> CookieController:
    # PENTING: CookieController TIDAK boleh dibungkus @st.cache_resource —
    # secara internal dia memanggil custom Streamlit component (mirip
    # widget), dan cache_resource/cache_data melarang widget command di
    # dalamnya (CachedWidgetWarning -> exception di Streamlit versi baru).
    #
    # TAPI dia juga TIDAK boleh diinstansiasi lebih dari SEKALI dalam SATU
    # script run yang sama. Lihat source streamlit_cookies_controller:
    # __init__ menulis st.session_state[key] SETIAP kali dipanggil —
    # termasuk saat cabang "sudah ada di session_state" (baris
    # `st.session_state[key] = self.__cookies`, sekadar nulis ulang nilai
    # yang sama). Streamlit versi ini melarang MENULIS ke session_state
    # milik widget yang sudah "difinalisasi" di run yang sama -> pemanggilan
    # KEDUA dalam satu run yang sama SELALU crash StreamlitAPIException,
    # walau nilainya sama persis. BUG NYATA DI PRODUKSI (ditemukan lewat
    # testing browser sungguhan): logout() -> rerun -> require_login() jalan
    # lagi -> _restore_session_from_cookie() panggil controller (call #1) ->
    # belum login -> render_login_form() panggil controller LAGI (call #2)
    # -> crash.
    #
    # PENTING JUGA: memoisasi ini TIDAK BOLEH bertahan LINTAS rerun. Custom
    # component ini resolve nilai cookie browser secara ASINKRON lalu
    # Streamlit otomatis men-trigger rerun BARU (session_state tetap
    # sama/persist) begitu nilainya berubah — st.session_state[key]
    # (dikelola FRAMEWORK, bukan variabel kita) baru berisi nilai cookie
    # yang SUNGGUHAN setelah rerun itu. Kalau instance di-cache lintas
    # rerun (mis. disimpan permanen di session_state), kita akan terus
    # memakai instance LAMA yang dibuat sebelum nilai resolve, dan
    # __cookies di dalamnya tidak akan pernah ter-update -> user terlihat
    # "tidak pernah login" selamanya walau cookie browser valid (REGRESI
    # YANG SEMPAT TERJADI saat fix pertama kali ditulis, ditemukan lewat
    # testing ulang browser sungguhan sebelum di-deploy).
    #
    # Solusi: cache dibersihkan (di-reset) di AWAL setiap kali require_login()
    # dipanggil — require_login() adalah satu-satunya entry point yang
    # dipanggil TEPAT SEKALI di awal tiap halaman/tiap run (lihat app.py &
    # utils/permissions.py). Jadi within satu run boleh dipakai ulang
    # (dedupe crash), tapi tiap run baru selalu mulai dari cache kosong
    # (fresh read, tangkap nilai cookie ter-update).
    if _COOKIE_CONTROLLER_STATE_KEY not in st.session_state:
        st.session_state[_COOKIE_CONTROLLER_STATE_KEY] = CookieController(key="analista_cookie_controller")
    return st.session_state[_COOKIE_CONTROLLER_STATE_KEY]


def _reset_cookie_controller_run_cache() -> None:
    """Panggil SEKALI di awal tiap script run (lihat require_login()) supaya
    _get_cookie_controller() dedupe HANYA dalam run ini, bukan lintas rerun."""
    st.session_state.pop(_COOKIE_CONTROLLER_STATE_KEY, None)


def _safe_get_all_cookies(controller: CookieController):
    """
    Wrapper defensif di sekitar controller.getAll().

    BUG YANG DITEMUKAN DI PRODUKSI: streamlit-cookies-controller kadang
    mengembalikan None (bukan dict kosong {}) dari komponen browser-nya —
    entah karena race condition komponen belum resolve, atau kegagalan
    JS di sisi browser. Kode library sendiri (`get()`) langsung melakukan
    `name not in self.__cookies` tanpa cek None dulu, jadi crash
    TypeError kalau itu terjadi. Kita tidak bisa/boleh edit file di
    site-packages (hilang tiap rebuild), jadi dibungkus aman di sini.

    Return (cookies_dict_or_None, is_definitely_resolved: bool)
    """
    try:
        all_cookies = controller.getAll()
    except Exception:
        return None, False

    if not isinstance(all_cookies, dict):
        # None, atau tipe aneh lain — anggap belum "resolve" beneran
        return None, False

    return all_cookies, True


def _restore_session_from_cookie() -> bool:
    """
    Kalau session_state kosong (mis. abis refresh) tapi ada cookie token
    valid, restore login dari situ. Return True kalau berhasil restore.
    """
    if st.session_state.get("auth_user"):
        return True  # sudah login di session_state, tidak perlu restore

    # PENTING soal timing: CookieController jalan lewat custom component
    # (iframe kecil di browser yang baca document.cookie lalu lapor balik
    # ke Python lewat WebSocket). Pada render PERTAMA sebuah sesi WS baru
    # (mis. abis browser refresh), Python BELUM PUNYA jawaban asli dari
    # browser, dan bahkan setelah "resolve" library ini kadang balikin
    # None bukan dict (lihat _safe_get_all_cookies). Solusinya adalah
    # MEMBEDAKAN kondisi "belum dapat jawaban valid" vs "sudah dapat
    # jawaban, memang tidak ada cookie", lalu tampilkan status netral
    # (bukan form login) selama masih menunggu — TAPI dibatasi jumlah
    # percobaan supaya tidak nyangkut selamanya kalau memang error.
    MAX_PENDING_ATTEMPTS = 6

    controller = _get_cookie_controller()
    all_cookies, resolved = _safe_get_all_cookies(controller)

    if not resolved:
        attempts = st.session_state.get("_cookie_check_attempts", 0) + 1
        st.session_state["_cookie_check_attempts"] = attempts
        if attempts <= MAX_PENDING_ATTEMPTS:
            st.session_state["_cookie_check_pending"] = True
            return False
        # Sudah dicoba berkali-kali dan tetap gagal resolve — daripada
        # macet permanen di layar "Memeriksa sesi...", anggap saja belum
        # login dan tampilkan form (user tinggal login manual).
        st.session_state["_cookie_check_pending"] = False
        return False

    st.session_state["_cookie_check_pending"] = False
    st.session_state["_cookie_check_attempts"] = 0

    token = all_cookies.get(COOKIE_NAME)
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
    controller.set(COOKIE_NAME, token, max_age=COOKIE_TTL_DAYS * 24 * 60 * 60)

    # PENTING — root cause bug "refresh = logout" yang sebenarnya:
    # CookieController.set() memanggil custom Streamlit component (iframe)
    # yang mengirim postMessage ke browser untuk EKSEKUSI document.cookie=...
    # di sana. Ini panggilan asinkron/"fire-and-forget" dari sisi Python —
    # tidak ada mekanisme built-in utk menunggu browser benar-benar selesai
    # menjalankannya. Kalau st.rerun() dipanggil LANGSUNG setelah set(),
    # Streamlit langsung membongkar komponen (iframe) itu dari DOM sebelum
    # browser sempat memuat+menjalankan JS-nya (load pertama component
    # ini butuh ~9 DETIK di jaringan produksi, diverifikasi via network
    # trace) — jadi cookie-nya TIDAK PERNAH benar-benar tertulis, meski
    # login di server sukses. User keliatannya "berhasil login" sesaat,
    # tapi begitu refresh, cookie kosong -> ke-logout.
    #
    # Fix: beri jeda supaya browser sempat proses postMessage-nya SEBELUM
    # rerun membongkar komponennya. Component sudah "dihangatkan" duluan
    # di render_login_form() (dipanggil saat halaman login pertama kali
    # ditampilkan, jauh sebelum user selesai isi form), jadi saat sampai
    # di titik ini JS-nya harusnya sudah ter-cache di browser dan proses
    # set() jauh lebih cepat (~150-270ms berdasarkan observasi network,
    # dibanding ~9000ms untuk cold-load pertama).
    import time
    time.sleep(0.8)

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
    try:
        controller.remove(COOKIE_NAME)
    except (KeyError, AttributeError):
        # BUG NYATA YANG TERJADI DI PRODUKSI (ditemukan lewat testing
        # browser sungguhan): library streamlit-cookies-controller
        # internalnya nyimpan cookie di dict; kalau cookie itu sudah
        # tidak ada di dict (KeyError dari .pop()) atau dict-nya belum
        # resolve sama sekali / None (AttributeError: 'NoneType' object
        # has no attribute 'pop'), remove() crash. Efeknya nyata: logout
        # gagal DI TENGAH JALAN sebelum session_state sempat dibersihkan,
        # DAN cookie stale (token yang sudah dihapus dari DB) tertinggal
        # selamanya di browser. Tujuan remove() cuma "pastikan cookie
        # hilang" — kalau memang sudah tidak ada, itu sudah tercapai,
        # aman diabaikan (session di server-side sudah pasti terhapus
        # lewat delete_session_token() di atas, itu yang jadi source of
        # truth keamanan, bukan cookie ini).
        pass

    # PENTING — root cause KEDUA yang ditemukan (sama persis pola bug
    # "cookie tidak pernah tertulis" di _do_login(), ternyata berlaku juga
    # untuk PENGHAPUSAN cookie): controller.remove() di atas cuma
    # mengirim postMessage FIRE-AND-FORGET ke browser untuk eksekusi
    # `document.cookie = ...expires di masa lalu...` di sana — TIDAK ada
    # mekanisme built-in untuk menunggu browser benar-benar selesai
    # menjalankannya. Kalau caller (render_user_badge_sidebar) langsung
    # panggil st.rerun() setelah logout(), Streamlit membongkar komponen
    # (iframe) itu dari DOM SEBELUM browser sempat proses postMessage-nya
    # — cookie TIDAK PERNAH benar-benar terhapus dari browser, meski
    # token-nya sudah aman dihapus dari DB server. VERIFIED lewat browser
    # sungguhan: tanpa delay ini, refresh setelah logout tetap menunjukkan
    # cookie analista_session_token (nilai lama) masih ada di
    # document.cookie. Component sudah "hangat" (sudah pernah dipakai di
    # run ini), jadi delay bisa lebih pendek dari cold-load _do_login().
    import time
    time.sleep(0.5)

    for key in SESSION_KEYS + ["auth_user_id", "auth_session_token", "_cookie_bootstrap_done", _COOKIE_CONTROLLER_STATE_KEY]:
        st.session_state.pop(key, None)


def render_login_form() -> None:
    """Tampilkan form login full-page. Panggil lalu st.stop() kalau belum login."""
    init_db()

    # "Hangatkan" komponen cookie controller SEDINI mungkin — begitu
    # halaman login pertama kali dirender, jauh sebelum user selesai isi
    # username/password & klik submit. Ini memberi waktu jaringan yg jauh
    # lebih longgar utk komponen (iframe React, ~340KB) selesai dimuat &
    # ter-cache oleh browser, dibanding kalau baru dipanggil pas _do_login()
    # (lihat penjelasan lengkap timing di _do_login).
    _get_cookie_controller()

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
    # WAJIB dipanggil di awal SETIAP script run (lihat penjelasan lengkap di
    # _get_cookie_controller) — supaya cache instance CookieController fresh
    # tiap run baru (termasuk auto-rerun internal saat komponen cookie
    # selesai resolve), tapi tetap dedupe DALAM run yang sama untuk
    # menghindari crash StreamlitAPIException.
    _reset_cookie_controller_run_cache()

    if not is_logged_in():
        if st.session_state.get("_cookie_check_pending"):
            # Masih menunggu jawaban pertama dari komponen cookie browser
            # (lihat penjelasan di _restore_session_from_cookie). Tampilkan
            # status netral, BUKAN form login — supaya user yang sebenarnya
            # masih login tidak melihat "logout" sekilas tiap refresh.
            st.markdown(
                """
                <style>
                    [data-testid="stSidebar"] { display: none !important; }
                    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
                </style>
                <div style="text-align:center; padding: 4rem 0;">
                    <p style="color: #888;">Memeriksa sesi login…</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
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

    # Sembunyikan link halaman "Manajemen User" dari daftar navigasi
    # sidebar kalau role user adalah staff (tidak punya izin mengelola
    # user). Ini hanya menyembunyikan TAMPILAN — proteksi sesungguhnya
    # tetap ada di require_role("superadmin","admin") di dalam halaman
    # itu sendiri, jadi akses langsung lewat URL tetap diblokir.
    if user["role"] == "staff":
        st.markdown(
            """
            <style>
                [data-testid="stSidebarNav"] a[href*="admin_users"] {
                    display: none !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

    with st.sidebar:
        st.markdown("---")
        role_emoji = {"superadmin": ":material/shield_person:", "admin": ":material/admin_panel_settings:", "staff": ":material/person:"}
        st.caption(f"{role_emoji.get(user['role'], '')} **{user['full_name']}**  \n`{user['role']}`")
        if st.button(":material/logout: Logout", use_container_width=True, key="sidebar_logout_btn"):
            logout()
            st.rerun()
