import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer
from utils.auth import require_role, render_user_badge_sidebar, current_user
from utils.db import (
    init_db, ROLES, create_user, list_users, update_user_active,
    update_user_role, reset_user_password, delete_user, can_manage_role,
    log_action, get_audit_log, delete_all_sessions_for_user,
)
from utils.permissions import PERMISSIONS, PERMISSION_LABELS, ALL_ROLES, get_role_permissions

st.set_page_config(page_title="Manajemen User", layout="wide")
inject_theme_css()

# Halaman ini butuh role admin atau superadmin (staff tidak bisa akses).
# users.manage_staff (admin) / users.manage_all (superadmin) — enforced
# per-baris di bawah lewat can_manage_role(), bukan cuma gate halaman.
user = require_role("superadmin", "admin")
render_user_badge_sidebar()
init_db()

st.markdown("# :material/admin_panel_settings: Manajemen User & Audit Log")
st.caption(f"Masuk sebagai **{user['full_name']}** (`{user['role']}`)")

tab_users, tab_create, tab_audit, tab_rbac = st.tabs([
    ":material/group: Daftar User", ":material/person_add: Tambah User",
    ":material/history: Audit Log", ":material/security: Permission Matrix"
])

# ─────────────────────────────────────────────────────────────
with tab_users:
    st.markdown("### Daftar User")
    users = list_users()

    if not users:
        st.info("Belum ada user.")
    else:
        for u in users:
            manageable = can_manage_role(user["role"], u["role"]) or u["username"] == user["username"]
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                with c1:
                    st.markdown(f"**{u['full_name']}**  \n`{u['username']}`")
                with c2:
                    st.markdown(f"Role: **{u['role']}**")
                    st.caption(f"Dibuat oleh: {u['created_by'] or '-'}")
                with c3:
                    status = ":material/check_circle: Aktif" if u["active"] else ":material/cancel: Nonaktif"
                    st.markdown(status)
                    st.caption(f"Login terakhir: {u['last_login_at'] or 'Belum pernah'}")
                with c4:
                    if not can_manage_role(user["role"], u["role"]):
                        st.caption(":material/lock: Anda tidak berwenang mengelola akun ini.")
                    elif u["username"] == user["username"]:
                        st.caption(":material/info: Ini akun Anda sendiri.")
                    else:
                        bcol1, bcol2, bcol3 = st.columns(3)
                        with bcol1:
                            toggle_label = "Nonaktifkan" if u["active"] else "Aktifkan"
                            if st.button(toggle_label, key=f"toggle_{u['id']}", use_container_width=True):
                                update_user_active(u["id"], not u["active"])
                                if u["active"]:  # baru dinonaktifkan -> putus sesi login yg mungkin masih aktif
                                    delete_all_sessions_for_user(u["id"])
                                log_action(user["username"], user["role"], "toggle_user_active", f"{toggle_label} akun {u['username']}")
                                st.rerun()
                        with bcol2:
                            new_role = st.selectbox(
                                "Role", ROLES, index=ROLES.index(u["role"]),
                                key=f"role_{u['id']}", label_visibility="collapsed",
                            )
                            if new_role != u["role"] and can_manage_role(user["role"], new_role):
                                if st.button("Simpan Role", key=f"save_role_{u['id']}", use_container_width=True):
                                    update_user_role(u["id"], new_role)
                                    log_action(user["username"], user["role"], "update_user_role", f"{u['username']}: {u['role']} -> {new_role}")
                                    st.rerun()
                        with bcol3:
                            if st.button("Hapus", key=f"delete_{u['id']}", use_container_width=True):
                                st.session_state[f"confirm_delete_{u['id']}"] = True

                            if st.session_state.get(f"confirm_delete_{u['id']}"):
                                st.warning(f"Yakin hapus akun **{u['username']}**? Tindakan ini permanen.")
                                cc1, cc2 = st.columns(2)
                                with cc1:
                                    if st.button("Ya, Hapus", key=f"confirm_yes_{u['id']}", type="primary"):
                                        delete_user(u["id"])
                                        log_action(user["username"], user["role"], "delete_user", f"Hapus akun {u['username']}")
                                        st.session_state.pop(f"confirm_delete_{u['id']}", None)
                                        st.rerun()
                                with cc2:
                                    if st.button("Batal", key=f"confirm_no_{u['id']}"):
                                        st.session_state.pop(f"confirm_delete_{u['id']}", None)
                                        st.rerun()

                    if manageable and u["username"] != user["username"]:
                        with st.expander(":material/key: Reset Password"):
                            new_pw = st.text_input("Password baru", type="password", key=f"newpw_{u['id']}")
                            if st.button("Reset", key=f"resetpw_{u['id']}"):
                                if len(new_pw) < 8:
                                    st.error("Password minimal 8 karakter.")
                                else:
                                    reset_user_password(u["id"], new_pw)
                                    delete_all_sessions_for_user(u["id"])  # force-logout sesi lama
                                    log_action(user["username"], user["role"], "reset_password", f"Reset password {u['username']}")
                                    st.success("Password berhasil direset. Sesi login lama akun ini otomatis di-invalidate.")

# ─────────────────────────────────────────────────────────────
with tab_create:
    st.markdown("### Tambah User Baru")

    allowed_roles_to_create = sorted(
        [r for r in ROLES if can_manage_role(user["role"], r)],
        key=lambda r: ROLES.index(r),
    )

    if not allowed_roles_to_create:
        st.info("Role Anda tidak berwenang membuat akun baru.")
    else:
        with st.form("create_user_form"):
            new_username = st.text_input("Username")
            new_full_name = st.text_input("Nama Lengkap")
            new_password = st.text_input("Password", type="password", help="Minimal 8 karakter.")
            new_role = st.selectbox("Role", allowed_roles_to_create)

            submitted = st.form_submit_button(":material/person_add: Buat Akun", type="primary")
            if submitted:
                if not new_username or not new_full_name or not new_password:
                    st.error("Semua field wajib diisi.")
                elif len(new_password) < 8:
                    st.error("Password minimal 8 karakter.")
                else:
                    try:
                        create_user(new_username, new_password, new_full_name, new_role, created_by=user["username"])
                        log_action(user["username"], user["role"], "create_user", f"Buat akun {new_username} ({new_role})")
                        st.success(f"Akun '{new_username}' ({new_role}) berhasil dibuat!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal membuat akun: {e}")

# ─────────────────────────────────────────────────────────────
with tab_audit:
    st.markdown("### Audit Log (Jejak Aktivitas)")
    st.caption("Mencatat login, logout, dan perubahan data penting di seluruh aplikasi.")

    filter_user = st.text_input("Filter berdasarkan username (kosongkan untuk semua)", key="audit_filter")
    limit = st.slider("Jumlah entri ditampilkan", 20, 500, 100, key="audit_limit")

    logs = get_audit_log(limit=limit, username_filter=filter_user or None)
    if not logs:
        st.info("Belum ada aktivitas tercatat.")
    else:
        log_df = pd.DataFrame(logs)[["timestamp", "username", "role", "action", "detail"]]
        st.dataframe(log_df, use_container_width=True, height=500)

        csv_bytes = log_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(":material/download: Unduh Audit Log (CSV)", data=csv_bytes, file_name="audit_log.csv", mime="text/csv")

# ─────────────────────────────────────────────────────────────
with tab_rbac:
    st.markdown("### Permission Matrix (RBAC)")
    st.caption(
        "Sumber kebenaran untuk 'siapa boleh apa' di seluruh Analista Tools. "
        "superadmin memiliki semua izin secara permanen (wildcard) — tidak bisa diubah, "
        "sebagai jaminan agar superadmin tidak pernah terkunci keluar dari sistemnya sendiri."
    )

    if user["role"] != "superadmin":
        st.info(
            ":material/visibility: Anda melihat matrix ini sebagai **read-only** "
            "(hanya superadmin yang bisa mengubah izin role)."
        )

    from utils.db import set_role_permission, reset_role_permissions_to_default
    from utils.permissions import EDITABLE_PERMISSIONS, EDITABLE_ROLES

    current_matrix = get_role_permissions  # alias biar jelas
    all_permissions = sorted(PERMISSION_LABELS.keys())

    if user["role"] == "superadmin":
        st.caption(":material/edit: Centang/hapus centang untuk mengubah izin. Perubahan langsung tersimpan ke database.")

        header_cols = st.columns([3, 1, 1])
        header_cols[0].markdown("**Izin**")
        header_cols[1].markdown("**admin**")
        header_cols[2].markdown("**staff**")

        for perm in EDITABLE_PERMISSIONS:
            row_cols = st.columns([3, 1, 1])
            row_cols[0].markdown(f"{PERMISSION_LABELS[perm]}  \n`{perm}`")
            for i, role in enumerate(EDITABLE_ROLES):
                col = row_cols[i + 1]
                with col:
                    checked = perm in get_role_permissions(role)
                    new_val = st.checkbox(
                        "izin", value=checked, key=f"perm_{role}_{perm}", label_visibility="collapsed"
                    )
                    if new_val != checked:
                        set_role_permission(role, perm, new_val)
                        log_action(
                            user["username"], user["role"], "update_role_permission",
                            f"{role}.{perm} -> {'granted' if new_val else 'revoked'}",
                        )
                        st.rerun()

        # Baris khusus: users.manage_all & superadmin — selalu tampil, tidak bisa diedit
        st.markdown("---")
        st.caption(f"🔒 `users.manage_all` — {PERMISSION_LABELS['users.manage_all']}: **hanya superadmin**, tidak bisa diubah.")
        st.caption("🔒 Role `superadmin` selalu memiliki SEMUA izin (wildcard permanen), tidak muncul di tabel edit di atas.")

        st.markdown("---")
        if st.button(":material/restart_alt: Reset Semua Izin ke Default", key="reset_rbac_btn"):
            reset_role_permissions_to_default()
            log_action(user["username"], user["role"], "reset_role_permissions", "Reset RBAC ke default bawaan aplikasi")
            st.success("Permission matrix berhasil direset ke default!")
            st.rerun()

    else:
        # Tampilan read-only untuk admin
        matrix_rows = []
        for perm in all_permissions:
            row = {"Izin": PERMISSION_LABELS[perm], "Kode": perm}
            for role in ALL_ROLES:
                granted = perm in get_role_permissions(role)
                row[role] = "✅ Ya" if granted else "❌ Tidak"
            matrix_rows.append(row)
        matrix_rows.append({
            "Izin": PERMISSION_LABELS["users.manage_all"],
            "Kode": "users.manage_all",
            "superadmin": "✅ Ya",
            "admin": "❌ Tidak",
            "staff": "❌ Tidak",
        })
        matrix_df = pd.DataFrame(matrix_rows)
        st.dataframe(matrix_df, use_container_width=True, height=450, hide_index=True)

    st.markdown("---")
    st.markdown("#### Ringkasan Hierarki Role")
    st.markdown("""
- **:material/shield_person: superadmin** — akses penuh ke semua fitur & semua akun (termasuk kelola sesama admin/superadmin), lihat semua audit log. Izinnya PERMANEN, tidak bisa dikurangi lewat matrix ini.
- **:material/admin_panel_settings: admin** — izin diatur bebas oleh superadmin lewat matrix di atas (default: dataset, analisis, assign tugas, kelola akun staff, audit log).
- **:material/person: staff** — izin diatur bebas oleh superadmin lewat matrix di atas (default: kerjakan dataset & tugas milik sendiri).
    """)

render_sidebar_footer()
render_page_footer()
