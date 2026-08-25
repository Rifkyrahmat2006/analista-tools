"""
Database Layer: Auth, RBAC, Audit Log, & Task Assignment
============================================================
PostgreSQL (via psycopg3), cocok untuk deployment Docker multi-container.
Koneksi dibaca dari env var DATABASE_URL (docker-compose menyuntikkan ini
otomatis, lihat docker-compose.yml). Fallback ke localhost utk dev lokal.

Tabel:
- users             : akun (username, password hash, role, aktif/tidak)
- audit_log         : jejak aktivitas (siapa, apa, kapan, detail)
- survey_questions  : daftar pertanyaan survei + tipe + chart yang disarankan
- assignments       : penugasan pertanyaan ke user + kesimpulan tertulis
- sessions          : token login persisten lintas refresh (cookie browser)
- role_permissions  : RBAC dinamis, bisa diedit superadmin lewat UI

Role hierarchy (dari tertinggi ke terendah):
- superadmin : akses penuh (wildcard permanen, TIDAK PERNAH dibatasi lewat
               tabel role_permissions — safety net anti-lock-out).
- admin      : izin diatur lewat role_permissions (default: kelola dataset,
               analisis, assign tugas, kelola user staff, lihat audit log).
- staff      : izin diatur lewat role_permissions (default: kerjakan
               dataset & tugas milik sendiri saja).
"""

import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import bcrypt
import psycopg
from psycopg.rows import dict_row

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

SESSION_TTL_DAYS = 7


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://analista:analista@localhost:5432/analista_tools",
    )


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(_database_url(), row_factory=dict_row, autocommit=False)
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Buat semua tabel jika belum ada. Idempotent — aman dipanggil berkali-kali."""
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'staff')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TEXT NOT NULL,
                created_by TEXT,
                last_login_at TEXT
            )
        """)

        # Migrasi kolom avatar_data (foto profil, disimpan sbg PNG/JPEG bytes
        # langsung di DB — dataset user kecil, jadi tidak perlu object storage
        # terpisah). ADD COLUMN IF NOT EXISTS aman dipanggil berkali-kali dan
        # tidak menghapus data existing di tabel users yang sudah berjalan.
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data BYTEA")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_mime TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS survey_questions (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role TEXT NOT NULL,
                permission TEXT NOT NULL,
                PRIMARY KEY (role, permission)
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_assignments_user ON assignments(assigned_to)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")

        # Seed default permission matrix HANYA kalau tabel masih kosong
        # (first run) — supaya tidak menimpa perubahan yang sudah dibuat
        # superadmin lewat UI pada run berikutnya.
        cur.execute("SELECT COUNT(*) as c FROM role_permissions")
        if cur.fetchone()["c"] == 0:
            from utils.permissions import DEFAULT_PERMISSIONS
            for role, perms in DEFAULT_PERMISSIONS.items():
                for perm in perms:
                    cur.execute(
                        "INSERT INTO role_permissions (role, permission) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (role, perm),
                    )


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
               VALUES (%s, %s, %s, %s, TRUE, %s, %s)""",
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
        cur.execute("SELECT * FROM users WHERE username = %s", (username.strip().lower(),))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict]:
    with db_cursor() as cur:
        cur.execute("SELECT id, username, full_name, role, active, created_at, created_by, last_login_at FROM users ORDER BY role, username")
        return [dict(r) for r in cur.fetchall()]


def update_user_active(user_id: int, active: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE users SET active = %s WHERE id = %s", (active, user_id))


def update_user_role(user_id: int, new_role: str) -> None:
    if new_role not in ROLES:
        raise ValueError(f"Role tidak valid: {new_role}")
    with db_cursor() as cur:
        cur.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))


def reset_user_password(user_id: int, new_plain_password: str) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_plain_password), user_id))


def change_own_password(user_id: int, old_plain_password: str, new_plain_password: str) -> tuple:
    """
    Ganti password milik SENDIRI — beda dgn reset_user_password() (dipakai
    admin utk reset password user LAIN, tidak perlu tahu password lama).
    Di sini password lama WAJIB diverifikasi dulu, supaya orang yang
    kebetulan lihat sesi browser user lain (belum logout) tidak bisa
    seenaknya ganti password tanpa tahu password aslinya.

    Return (success: bool, error_message: str atau None).
    """
    with db_cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return False, "Akun tidak ditemukan."
        if not verify_password(old_plain_password, row["password_hash"]):
            return False, "Password lama salah."
        if len(new_plain_password) < 6:
            return False, "Password baru minimal 6 karakter."
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hash_password(new_plain_password), user_id),
        )
    return True, None


def update_avatar(user_id: int, image_bytes: bytes, mime_type: str) -> None:
    """Simpan/ganti foto profil user. image_bytes sudah dalam format final (lihat utils/avatar.py utk resize/compress)."""
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET avatar_data = %s, avatar_mime = %s WHERE id = %s",
            (image_bytes, mime_type, user_id),
        )


def remove_avatar(user_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE users SET avatar_data = NULL, avatar_mime = NULL WHERE id = %s", (user_id,))


def get_avatar(user_id: int) -> Optional[tuple]:
    """Return (image_bytes, mime_type) atau None kalau user belum punya foto profil."""
    with db_cursor() as cur:
        cur.execute("SELECT avatar_data, avatar_mime FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row or not row["avatar_data"]:
            return None
        avatar_bytes = bytes(row["avatar_data"]) if not isinstance(row["avatar_data"], bytes) else row["avatar_data"]
        return avatar_bytes, row["avatar_mime"] or "image/png"


def delete_user(user_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


def touch_last_login(username: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = %s WHERE username = %s",
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

def create_session_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now.replace(microsecond=0) + timedelta(days=SESSION_TTL_DAYS)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
    return token


def get_user_by_session_token(token: str) -> Optional[Dict]:
    """Return user dict kalau token valid & belum expired, None kalau tidak."""
    if not token:
        return None
    with db_cursor() as cur:
        cur.execute("SELECT * FROM sessions WHERE token = %s", (token,))
        session = cur.fetchone()
        if not session:
            return None
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
            return None
        cur.execute("SELECT * FROM users WHERE id = %s", (session["user_id"],))
        user_row = cur.fetchone()
        if not user_row or not user_row["active"]:
            return None
        return dict(user_row)


def delete_session_token(token: str) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE token = %s", (token,))


def delete_all_sessions_for_user(user_id: int) -> None:
    """Force-logout semua sesi aktif milik satu user (mis. saat reset password)."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def can_manage_role(actor_role: str, target_role: str) -> bool:
    return target_role in ROLE_CAN_MANAGE.get(actor_role, set())


# ─────────────────────────────────────────────────────────────
# AUDIT LOG (Accounting)
# ─────────────────────────────────────────────────────────────

def log_action(username: str, role: Optional[str], action: str, detail: str = "") -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (username, role, action, detail, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (username, role, action, detail, datetime.now(timezone.utc).isoformat()),
        )


def get_audit_log(limit: int = 200, username_filter: Optional[str] = None) -> List[Dict]:
    with db_cursor() as cur:
        if username_filter:
            cur.execute(
                "SELECT * FROM audit_log WHERE username = %s ORDER BY id DESC LIMIT %s",
                (username_filter, limit),
            )
        else:
            cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (limit,))
        return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# SURVEY QUESTIONS & TASK ASSIGNMENT (pengganti dokumen pembagian tugas)
# ─────────────────────────────────────────────────────────────

def update_question_type_chart(question_id: int, question_type: str, suggested_chart: str) -> None:
    """
    Update tipe pertanyaan & chart yang disarankan secara MANUAL (override
    hasil deteksi otomatis). Dipakai di UI "Assign Pertanyaan ke Anggota
    Tim" -- admin bisa koreksi kalau deteksi otomatis kurang tepat utk
    pertanyaan tertentu (mis. kolom numerik yg sebenarnya open_text, atau
    sebaliknya).
    """
    with db_cursor() as cur:
        cur.execute(
            "UPDATE survey_questions SET question_type = %s, suggested_chart = %s WHERE id = %s",
            (question_type, suggested_chart, question_id),
        )


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
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (dataset_name, column_name) DO UPDATE SET
                       question_type = EXCLUDED.question_type,
                       suggested_chart = EXCLUDED.suggested_chart""",
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
               WHERE sq.dataset_name = %s
               ORDER BY sq.id""",
            (dataset_name,),
        )
        return [dict(r) for r in cur.fetchall()]


def assign_question(question_id: int, user_id: Optional[int], assigned_by: str) -> None:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM assignments WHERE question_id = %s", (question_id,))
        existing = cur.fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            cur.execute(
                "UPDATE assignments SET assigned_to = %s, assigned_by = %s, updated_at = %s WHERE question_id = %s",
                (user_id, assigned_by, now, question_id),
            )
        else:
            cur.execute(
                """INSERT INTO assignments (question_id, assigned_to, assigned_by, status, created_at, updated_at)
                   VALUES (%s, %s, %s, 'belum_dikerjakan', %s, %s)""",
                (question_id, user_id, assigned_by, now, now),
            )


def update_assignment_progress(question_id: int, status: str, conclusion_text: Optional[str] = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE assignments SET status = %s, conclusion_text = COALESCE(%s, conclusion_text), updated_at = %s WHERE question_id = %s",
            (status, conclusion_text, datetime.now(timezone.utc).isoformat(), question_id),
        )


def get_my_assignments(user_id: int) -> List[Dict]:
    with db_cursor() as cur:
        cur.execute(
            """SELECT sq.*, a.id as assignment_id, a.status, a.conclusion_text, a.updated_at as assignment_updated_at
               FROM assignments a
               JOIN survey_questions sq ON sq.id = a.question_id
               WHERE a.assigned_to = %s
               ORDER BY sq.dataset_name, sq.id""",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# ROLE PERMISSIONS (RBAC dinamis — bisa diedit superadmin lewat UI)
# ─────────────────────────────────────────────────────────────
# NOTE: role "superadmin" SENGAJA selalu wildcard penuh (tidak pernah
# dibatasi lewat tabel ini) — safety net supaya superadmin tidak bisa
# mengunci diri sendiri keluar dari sistem secara tidak sengaja.

def get_permissions_for_role(role: str) -> set:
    """Baca izin efektif satu role langsung dari database."""
    with db_cursor() as cur:
        cur.execute("SELECT permission FROM role_permissions WHERE role = %s", (role,))
        return {r["permission"] for r in cur.fetchall()}


def get_all_role_permissions() -> Dict[str, set]:
    """Baca izin efektif SEMUA role dari database, dalam satu query."""
    with db_cursor() as cur:
        cur.execute("SELECT role, permission FROM role_permissions")
        result: Dict[str, set] = {}
        for r in cur.fetchall():
            result.setdefault(r["role"], set()).add(r["permission"])
        return result


def set_role_permission(role: str, permission: str, granted: bool) -> None:
    """Tambah atau cabut satu izin dari satu role."""
    with db_cursor() as cur:
        if granted:
            cur.execute(
                "INSERT INTO role_permissions (role, permission) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (role, permission),
            )
        else:
            cur.execute(
                "DELETE FROM role_permissions WHERE role = %s AND permission = %s",
                (role, permission),
            )


def reset_role_permissions_to_default() -> None:
    """Kembalikan seluruh permission matrix ke default bawaan aplikasi."""
    from utils.permissions import DEFAULT_PERMISSIONS
    with db_cursor() as cur:
        cur.execute("DELETE FROM role_permissions")
        for role, perms in DEFAULT_PERMISSIONS.items():
            for perm in perms:
                cur.execute(
                    "INSERT INTO role_permissions (role, permission) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (role, perm),
                )
