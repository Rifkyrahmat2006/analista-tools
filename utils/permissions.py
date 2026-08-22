"""
RBAC (Role-Based Access Control) — Permission Matrix Terpusat
=================================================================
Satu sumber kebenaran untuk "siapa boleh apa" di seluruh Analista Tools.
Menggantikan pengecekan role ad-hoc (mis. `if role in (...)` yang
tersebar di tiap halaman) dengan permission bernama yang jelas maknanya.

CARA PAKAI:
    from utils.permissions import require_permission, has_permission

    # Di awal halaman, setelah require_login():
    user = require_permission("dataset.upload")

    # Untuk kondisi tampilan (show/hide tombol dsb), tanpa memblokir halaman:
    if has_permission(user["role"], "tasks.assign"):
        st.button("Assign ke anggota tim")

PRINSIP:
- superadmin: akses penuh ke semua permission (wildcard).
- admin: kelola operasional (dataset, analisis, assign tugas, kelola
  staff, lihat audit log) — TIDAK bisa kelola sesama admin/superadmin.
- staff: kerjakan dataset & tugas milik sendiri — TIDAK bisa kelola user,
  TIDAK bisa assign tugas ke orang lain, TIDAK bisa lihat audit log.
"""

import streamlit as st

from utils.auth import require_login

# ─────────────────────────────────────────────────────────────
# PERMISSION MATRIX
# ─────────────────────────────────────────────────────────────
# Format: "domain.action" — domain = area fitur, action = operasi spesifik.
PERMISSIONS = {
    "superadmin": {"*"},  # wildcard: semua permission di bawah ini otomatis diizinkan
    "admin": {
        "dataset.upload",
        "dataset.view",
        "dataset.clean",
        "analysis.run",
        "visualization.view",
        "visualization.export",
        "tasks.view",
        "tasks.assign",          # assign pertanyaan ke anggota tim lain
        "tasks.manage_own",      # isi kesimpulan/status tugas milik sendiri
        "users.manage_staff",    # buat/hapus/reset password akun staff SAJA
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

ALL_ROLES = list(PERMISSIONS.keys())


def has_permission(role: str, permission: str) -> bool:
    """Cek apakah suatu role punya izin atas permission tertentu."""
    granted = PERMISSIONS.get(role, set())
    if "*" in granted:
        return True
    return permission in granted


def get_role_permissions(role: str) -> set:
    """Return set semua permission efektif untuk suatu role (wildcard di-expand)."""
    granted = PERMISSIONS.get(role, set())
    if "*" in granted:
        return set(PERMISSION_LABELS.keys()) | {"users.manage_all"}
    return granted


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
