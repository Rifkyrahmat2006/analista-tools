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
import time
from utils.db import init_db, create_user, get_user_by_username

# (username, full_name, role)
SEED_USERS = [
    ("rifky", "Rifky Dwi Rahmat Prakoso", "superadmin"),
    ("yufi", "Yufi", "admin"),
    ("reivan", "Reivan", "staff"),
    ("d", "D", "staff"),
]


def _init_db_with_retry(max_attempts: int = 10, delay_seconds: float = 2.0) -> None:
    """
    Retry koneksi DB — meski docker-compose punya depends_on:
    condition: service_healthy, race condition kecil masih mungkin
    terjadi (mis. Postgres healthy tapi belum terima koneksi baru).
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            init_db()
            return
        except Exception as e:
            last_error = e
            print(f"[WAIT] Database belum siap (percobaan {attempt}/{max_attempts}): {e}")
            time.sleep(delay_seconds)
    raise RuntimeError(f"Gagal konek database setelah {max_attempts} percobaan") from last_error


def main():
    _init_db_with_retry()
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
