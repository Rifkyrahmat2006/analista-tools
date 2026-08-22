"""
Seed script: buat akun awal untuk 4 anggota tim di dokumen pembagian tugas.

Jalankan sekali: .venv/bin/python scripts/seed_users.py

PENTING: password default di sini HARUS diganti setelah login pertama.
Password dicetak ke terminal (bukan hardcode di kode) supaya tidak
ter-commit ke git secara tidak sengaja.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import secrets
from utils.db import init_db, create_user, get_user_by_username

# (username, full_name, role)
SEED_USERS = [
    ("rifky", "Rifky Dwi Rahmat Prakoso", "superadmin"),
    ("yufi", "Yufi", "admin"),
    ("reivan", "Reivan", "staff"),
    ("d", "D", "staff"),
]


def main():
    init_db()
    print("=" * 60)
    print("SEEDING AKUN AWAL — SIMPAN PASSWORD DI BAWAH INI!")
    print("(Password TIDAK bisa dilihat lagi setelah ini, hanya bisa direset)")
    print("=" * 60)

    for username, full_name, role in SEED_USERS:
        if get_user_by_username(username):
            print(f"[SKIP] '{username}' sudah ada, tidak dibuat ulang.")
            continue

        password = secrets.token_urlsafe(9)  # ~12 karakter acak
        create_user(username, password, full_name, role, created_by="seed_script")
        print(f"[OK] {full_name:30} | username: {username:12} | role: {role:12} | password: {password}")

    print("=" * 60)
    print("Selesai. Segera minta tiap anggota tim login & ganti password.")


if __name__ == "__main__":
    main()
