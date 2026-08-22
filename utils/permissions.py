"""
RBAC (Role-Based Access Control) — Permission Matrix Dinamis
=================================================================
Sumber kebenaran "siapa boleh apa" sekarang di DATABASE (tabel
role_permissions), bukan hardcode Python — supaya superadmin bisa
mengatur ulang izin tiap role langsung lewat UI (halaman Manajemen
User > tab Permission Matrix), tanpa perlu edit kode / redeploy.

DEFAULT_PERMISSIONS di file ini hanya dipakai sebagai:
1. Seed awal saat tabel role_permissions masih kosong (first run)
2. Fallback "Reset ke Default" di UI

CARA PAKAI:
    from utils.permissions import require_permission, has_permission

    # Di awal halaman, setelah require_login():
    user = require_permission("dataset.upload")

    # Untuk kondisi tampilan (show/hide tombol dsb), tanpa memblokir halaman:
    if has_permission(user["role"], "tasks.assign"):
        st.button("Assign ke anggota tim")

PRINSIP:
- superadmin: SELALU wildcard penuh, TIDAK PERNAH dibatasi lewat tabel
  role_permissions — ini safety net supaya superadmin tidak bisa
  mengunci diri sendiri keluar dari sistem lewat kesalahan konfigurasi.
- admin & staff: izinnya diatur bebas oleh superadmin lewat UI,
  disimpan di database, dan langsung berlaku (tidak perlu redeploy).
"""

import streamlit as st

from utils.auth import require_login

# ─────────────────────────────────────────────────────────────
# DEFAULT PERMISSION MATRIX (seed awal + fallback reset)
# ─────────────────────────────────────────────────────────────
DEFAULT_PERMISSIONS = {
    "superadmin": {"*"},
    "admin": {
        "dataset.upload",
        "dataset.view",
        "dataset.clean",
        "analysis.run",
        "visualization.view",
        "visualization.export",
        "tasks.view",
        "tasks.assign",
        "tasks.manage_own",
        "users.manage_staff",
        "audit.view",
    },
    "staff": {
        "dataset.upload",
        "dataset.view",
        "dataset.clean",
        "analysis.run",
        "visualization.view",
        "visualization.export",
        "tasks.view",
        "tasks.manage_own",
    },
}

# Deskripsi manusiawi tiap permission — dipakai untuk render matrix di UI admin.
PERMISSION_LABELS = {
    "dataset.upload": "Upload dataset baru",
    "dataset.view": "Lihat dataset aktif",
    "dataset.clean": "Bersihkan / standarisasi data",
    "analysis.run": "Jalankan analisis (clustering, dsb)",
    "visualization.view": "Lihat visualisasi & chart",
    "visualization.export": "Export chart/gambar",
    "tasks.view": "Lihat papan tugas",
    "tasks.assign": "Assign pertanyaan ke anggota tim",
    "tasks.manage_own": "Isi status & kesimpulan tugas sendiri",
    "users.manage_staff": "Kelola akun staff (buat/hapus/reset password)",
    "users.manage_all": "Kelola SEMUA akun termasuk admin (khusus superadmin)",
    "audit.view": "Lihat audit log",
}

# Permission yang BOLEH diatur ulang lewat UI (users.manage_all sengaja
# dikecualikan — itu selalu implisit milik superadmin lewat wildcard).
EDITABLE_PERMISSIONS = [p for p in PERMISSION_LABELS if p != "users.manage_all"]

ALL_ROLES = ["superadmin", "admin", "staff"]
EDITABLE_ROLES = ["admin", "staff"]  # superadmin tidak pernah diedit lewat UI


def has_permission(role: str, permission: str) -> bool:
    """Cek apakah suatu role punya izin atas permission tertentu (baca dari DB)."""
    if role == "superadmin":
        return True  # wildcard permanen, tidak pernah dibatasi DB

    from utils.db import get_permissions_for_role
    return permission in get_permissions_for_role(role)


def get_role_permissions(role: str) -> set:
    """Return set semua permission efektif untuk suatu role, dari database."""
    if role == "superadmin":
        return set(PERMISSION_LABELS.keys())  # termasuk users.manage_all

    from utils.db import get_permissions_for_role
    return get_permissions_for_role(role)


def require_permission(permission: str) -> dict:
    """
    Panggil di awal halaman (setelah/menggantikan require_login biasa).
    Kalau user tidak login -> tampilkan form login.
    Kalau login tapi tidak punya permission -> tampilkan error & stop.
    Return dict user kalau lolos.
    """
    user = require_login()
    if not has_permission(user["role"], permission):
        label = PERMISSION_LABELS.get(permission, permission)
        st.error(
            f":material/block: Akses ditolak. Anda tidak memiliki izin "
            f"**\"{label}\"** ({permission}). Role Anda: `{user['role']}`."
        )
        st.stop()
    return user
