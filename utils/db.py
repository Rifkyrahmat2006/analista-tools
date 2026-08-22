"""
Database Layer: Auth, RBAC, Audit Log, & Task Assignment
============================================================
SQLite lokal (persisten di server), bukan file-based session state.
Cocok untuk deployment self-hosted (Proxmox/VPS) sesuai kebutuhan
multi-user Analista Tools.

Tabel:
- users            : akun (username, password hash, role, aktif/tidak)
- audit_log        : jejak aktivitas (siapa, apa, kapan, detail)
- survey_questions : daftar pertanyaan survei + tipe + chart yang disarankan
- assignments       : penugasan pertanyaan ke user + kesimpulan tertulis

Role hierarchy (dari tertinggi ke terendah):
- superadmin : akses penuh, kelola semua user (termasuk admin), lihat semua
               audit log, hapus/reset apa pun.
- admin      : kelola user staff (bukan sesama admin/superadmin), assign
               tugas, lihat audit log, kelola dataset & survey_questions.
- staff      : hanya kerjakan tugas yang di-assign ke dirinya (isi
               kesimpulan, lihat chart pertanyaannya sendiri), tidak bisa
               kelola user atau lihat audit log user lain.
"""

import sqlite3
import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import bcrypt

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "app.db"

ROLES = ["superadmin", "admin", "staff"]

# Hierarki: superadmin bisa kelola siapa saja, admin cuma bisa kelola staff,
# staff tidak bisa kelola siapa pun.
ROLE_CAN_MANAGE = {
    "superadmin": {"superadmin", "admin", "staff"},
    "admin": {"staff"},
    "staff": set(),
}

QUESTION_TYPE_TO_CHART = {
    "single_choice": "Pie / Bar Chart",
    "multiple_choice": "Horizontal Bar Chart",
    "scale": "Bar Chart / Gauge",
    "open_text": "Wordcloud",
    "skip": "-",
}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Buat semua tabel jika belum ada. Idempotent — aman dipanggil berkali-kali."""
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'staff')),
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT,
                last_login_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS survey_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                question_type TEXT,
                suggested_chart TEXT,
                category TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(dataset_name, column_name)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
                assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
                assigned_by TEXT,
                status TEXT NOT NULL DEFAULT 'belum_dikerjakan'
                    CHECK(status IN ('belum_dikerjakan', 'dikerjakan', 'selesai')),
                conclusion_text TEXT,
                updated_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_assignments_user ON assignments(assigned_to)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")


# ─────────────────────────────────────────────────────────────
# PASSWORD HASHING
# ─────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ─────────────────────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────────────────────

def create_user(
    username: str,
    plain_password: str,
    full_name: str,
    role: str,
    created_by: str = "system",
) -> Dict:
    if role not in ROLES:
        raise ValueError(f"Role tidak valid: {role}")

    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO users (username, password_hash, full_name, role, active, created_at, created_by)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (
                username.strip().lower(),
                hash_password(plain_password),
                full_name.strip(),
                role,
                datetime.now(timezone.utc).isoformat(),
                created_by,
            ),
        )
        return {"username": username, "role": role}


def get_user_by_username(username: str) -> Optional[Dict]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict]:
    with db_cursor() as cur:
        cur.execute("SELECT id, username, full_name, role, active, created_at, created_by, last_login_at FROM users ORDER BY role, username")
        return [dict(r) for r in cur.fetchall()]


def update_user_active(user_id: int, active: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))


def update_user_role(user_id: int, new_role: str) -> None:
    if new_role not in ROLES:
        raise ValueError(f"Role tidak valid: {new_role}")
    with db_cursor() as cur:
        cur.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))


def reset_user_password(user_id: int, new_plain_password: str) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_plain_password), user_id))


def delete_user(user_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))


def touch_last_login(username: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = ? WHERE username = ?",
            (datetime.now(timezone.utc).isoformat(), username.strip().lower()),
        )


def authenticate(username: str, plain_password: str) -> Optional[Dict]:
    """Return user dict kalau login sukses & aktif, None kalau gagal."""
    user = get_user_by_username(username)
    if not user or not user["active"]:
        return None
    if not verify_password(plain_password, user["password_hash"]):
        return None
    touch_last_login(username)
    return user


# ─────────────────────────────────────────────────────────────
# SESSION TOKENS (persist login lintas refresh via cookie browser)
# ─────────────────────────────────────────────────────────────
# st.session_state Streamlit hidup per-koneksi WebSocket di server, HILANG
# setiap kali browser refresh (WS baru = "sesi" baru di Streamlit). Supaya
# login bertahan lintas refresh, token acak disimpan di COOKIE BROWSER
# (bukan session_state) dan divalidasi balik ke tabel `sessions` di sini.

SESSION_TTL_DAYS = 7


def create_session_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now.replace(microsecond=0) + timedelta(days=SESSION_TTL_DAYS)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
    return token


def get_user_by_session_token(token: str) -> Optional[Dict]:
    """Return user dict kalau token valid & belum expired, None kalau tidak."""
    if not token:
        return None
    with db_cursor() as cur:
        cur.execute("SELECT * FROM sessions WHERE token = ?", (token,))
        session = cur.fetchone()
        if not session:
            return None
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
        cur.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        user_row = cur.fetchone()
        if not user_row or not user_row["active"]:
            return None
        return dict(user_row)


def delete_session_token(token: str) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE token = ?", (token,))


def delete_all_sessions_for_user(user_id: int) -> None:
    """Force-logout semua sesi aktif milik satu user (mis. saat reset password)."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def can_manage_role(actor_role: str, target_role: str) -> bool:
    return target_role in ROLE_CAN_MANAGE.get(actor_role, set())


# ─────────────────────────────────────────────────────────────
# AUDIT LOG (Accounting)
# ─────────────────────────────────────────────────────────────

def log_action(username: str, role: Optional[str], action: str, detail: str = "") -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (username, role, action, detail, timestamp) VALUES (?, ?, ?, ?, ?)",
            (username, role, action, detail, datetime.now(timezone.utc).isoformat()),
        )


def get_audit_log(limit: int = 200, username_filter: Optional[str] = None) -> List[Dict]:
    with db_cursor() as cur:
        if username_filter:
            cur.execute(
                "SELECT * FROM audit_log WHERE username = ? ORDER BY id DESC LIMIT ?",
                (username_filter, limit),
            )
        else:
            cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# SURVEY QUESTIONS & TASK ASSIGNMENT (pengganti dokumen pembagian tugas)
# ─────────────────────────────────────────────────────────────

def upsert_survey_questions(dataset_name: str, questions: List[Dict]) -> int:
    """
    questions: list of dict {column_name, question_type, category (opsional)}
    Return jumlah pertanyaan yang di-insert/updated.
    """
    count = 0
    with db_cursor() as cur:
        for q in questions:
            chart = QUESTION_TYPE_TO_CHART.get(q.get("question_type"), "-")
            cur.execute(
                """INSERT INTO survey_questions (dataset_name, column_name, question_type, suggested_chart, category, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(dataset_name, column_name) DO UPDATE SET
                       question_type = excluded.question_type,
                       suggested_chart = excluded.suggested_chart""",
                (
                    dataset_name,
                    q["column_name"],
                    q.get("question_type"),
                    chart,
                    q.get("category", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            count += 1
    return count


def list_survey_questions(dataset_name: str) -> List[Dict]:
    with db_cursor() as cur:
        cur.execute(
            """SELECT sq.*, a.id as assignment_id, a.assigned_to, a.status, a.conclusion_text, a.updated_at as assignment_updated_at,
                      u.full_name as assigned_to_name, u.username as assigned_to_username
               FROM survey_questions sq
               LEFT JOIN assignments a ON a.question_id = sq.id
               LEFT JOIN users u ON u.id = a.assigned_to
               WHERE sq.dataset_name = ?
               ORDER BY sq.id""",
            (dataset_name,),
        )
        return [dict(r) for r in cur.fetchall()]


def assign_question(question_id: int, user_id: Optional[int], assigned_by: str) -> None:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM assignments WHERE question_id = ?", (question_id,))
        existing = cur.fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            cur.execute(
                "UPDATE assignments SET assigned_to = ?, assigned_by = ?, updated_at = ? WHERE question_id = ?",
                (user_id, assigned_by, now, question_id),
            )
        else:
            cur.execute(
                """INSERT INTO assignments (question_id, assigned_to, assigned_by, status, created_at, updated_at)
                   VALUES (?, ?, ?, 'belum_dikerjakan', ?, ?)""",
                (question_id, user_id, assigned_by, now, now),
            )


def update_assignment_progress(question_id: int, status: str, conclusion_text: Optional[str] = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE assignments SET status = ?, conclusion_text = COALESCE(?, conclusion_text), updated_at = ? WHERE question_id = ?",
            (status, conclusion_text, datetime.now(timezone.utc).isoformat(), question_id),
        )


def get_my_assignments(user_id: int) -> List[Dict]:
    with db_cursor() as cur:
        cur.execute(
            """SELECT sq.*, a.id as assignment_id, a.status, a.conclusion_text, a.updated_at as assignment_updated_at
               FROM assignments a
               JOIN survey_questions sq ON sq.id = a.question_id
               WHERE a.assigned_to = ?
               ORDER BY sq.dataset_name, sq.id""",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]
