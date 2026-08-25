import base64

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer
from utils.auth import require_login, render_user_badge_sidebar, refresh_session_token
from utils.db import (
    init_db, change_own_password, update_avatar, remove_avatar, get_avatar,
    log_action, delete_all_sessions_for_user,
)
from utils.avatar import process_avatar_upload, get_initials

st.set_page_config(page_title="Profil Saya", layout="wide")
inject_theme_css()

# Halaman ini TIDAK butuh permission khusus — setiap user yang sudah
# login (apapun role-nya) boleh mengelola profilnya sendiri (password +
# foto). Cukup require_login(), bukan require_permission()/require_role().
user = require_login()
render_user_badge_sidebar()
init_db()

st.markdown("# :material/manage_accounts: Profil Saya")
st.caption(f"Kelola akun **{user['full_name']}** (`{user['username']}`) — password dan foto profil Anda sendiri.")

role_emoji = {"superadmin": ":material/shield_person:", "admin": ":material/admin_panel_settings:", "staff": ":material/person:"}
st.info(f"{role_emoji.get(user['role'], '')} Role Anda saat ini: **{user['role']}**. Untuk ganti role, hubungi admin/superadmin.")

tab_photo, tab_password = st.tabs([
    ":material/photo_camera: Foto Profil", ":material/lock_reset: Ganti Password",
])

# ─────────────────────────────────────────────────────────────
# TAB 1: FOTO PROFIL
# ─────────────────────────────────────────────────────────────
with tab_photo:
    st.markdown("### Foto Profil")
    st.caption("Foto akan di-crop persegi otomatis dan ditampilkan di sidebar. Format: JPG, PNG, atau WEBP (maks 5MB).")

    col_current, col_upload = st.columns([1, 2])

    with col_current:
        st.markdown("**Foto saat ini**")
        avatar = get_avatar(user["id"])
        if avatar:
            img_bytes, mime = avatar
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            st.markdown(
                f'<img src="data:{mime};base64,{b64_img}" '
                f'style="width:160px;height:160px;border-radius:50%;object-fit:cover;border:3px solid rgba(124,143,247,0.3);">',
                unsafe_allow_html=True,
            )
        else:
            initials = get_initials(user["full_name"])
            st.markdown(
                f'<div style="width:160px;height:160px;border-radius:50%;'
                f'background:linear-gradient(135deg,#7c8ff7,#a78bfa);display:flex;'
                f'align-items:center;justify-content:center;color:white;font-weight:700;'
                f'font-size:3rem;border:3px solid rgba(124,143,247,0.3);">{initials}</div>',
                unsafe_allow_html=True,
            )
            st.caption("Belum ada foto — memakai inisial nama.")

        if avatar:
            if st.button(":material/delete: Hapus Foto", key="remove_avatar_btn"):
                remove_avatar(user["id"])
                st.session_state.pop(f"_avatar_cache_{user['id']}", None)
                log_action(user["username"], user["role"], "remove_avatar", "Menghapus foto profil sendiri")
                st.success("Foto profil dihapus.")
                st.rerun()

    with col_upload:
        st.markdown("**Upload foto baru**")
        uploaded_file = st.file_uploader(
            "Pilih gambar", type=["jpg", "jpeg", "png", "webp"], key="avatar_uploader",
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            raw_bytes = uploaded_file.getvalue()
            try:
                processed_bytes = process_avatar_upload(raw_bytes)
                st.markdown("**Preview (setelah di-crop & di-resize):**")
                b64_preview = base64.b64encode(processed_bytes).decode("utf-8")
                st.markdown(
                    f'<img src="data:image/jpeg;base64,{b64_preview}" '
                    f'style="width:160px;height:160px;border-radius:50%;object-fit:cover;border:3px solid #10b981;">',
                    unsafe_allow_html=True,
                )
                if st.button(":material/save: Simpan Foto Ini", type="primary", key="save_avatar_btn"):
                    update_avatar(user["id"], processed_bytes, "image/jpeg")
                    st.session_state.pop(f"_avatar_cache_{user['id']}", None)
                    log_action(user["username"], user["role"], "update_avatar", "Mengganti foto profil sendiri")
                    st.success("Foto profil berhasil disimpan!")
                    st.rerun()
            except ValueError as e:
                st.error(f":material/error: {e}")

# ─────────────────────────────────────────────────────────────
# TAB 2: GANTI PASSWORD
# ─────────────────────────────────────────────────────────────
with tab_password:
    st.markdown("### Ganti Password")
    st.caption("Password lama wajib diisi benar untuk verifikasi. Setelah berhasil, semua sesi login lain (perangkat/browser lain) akan otomatis logout demi keamanan.")

    with st.form("change_password_form", clear_on_submit=True):
        old_password = st.text_input("Password Lama", type="password")
        new_password = st.text_input("Password Baru", type="password", help="Minimal 6 karakter.")
        confirm_password = st.text_input("Konfirmasi Password Baru", type="password")
        submitted = st.form_submit_button(":material/lock_reset: Ganti Password", type="primary")

        if submitted:
            if not old_password or not new_password or not confirm_password:
                st.error("Semua kolom wajib diisi.")
            elif new_password != confirm_password:
                st.error("Konfirmasi password baru tidak cocok.")
            elif old_password == new_password:
                st.error("Password baru tidak boleh sama dengan password lama.")
            else:
                success, error_msg = change_own_password(user["id"], old_password, new_password)
                if success:
                    # Force-logout SEMUA sesi lain (device/browser lain yang
                    # masih login pakai password lama) — praktik keamanan
                    # standar setelah ganti password: kalau ada yang lain
                    # sedang pakai akun ini tanpa sepengetahuan pemilik,
                    # sesi itu langsung terputus begitu password diganti.
                    delete_all_sessions_for_user(user["id"])
                    # PENTING: delete_all_sessions_for_user() di atas ikut
                    # menghapus token sesi browser YANG SEDANG DIPAKAI user
                    # ini sendiri untuk mengganti password (bukan cuma
                    # device/browser lain) — kalau dibiarkan, user akan
                    # ke-logout juga di tab yang sama begitu dia refresh.
                    # refresh_session_token() membuat token baru + tulis
                    # ulang cookie-nya supaya sesi SAAT INI tetap login.
                    refresh_session_token()
                    log_action(user["username"], user["role"], "change_own_password", "Mengganti password sendiri")
                    st.success(":material/check_circle: Password berhasil diganti! Sesi login di perangkat/browser lain telah di-logout otomatis.")
                else:
                    st.error(f":material/error: {error_msg}")

render_sidebar_footer()
render_page_footer()
