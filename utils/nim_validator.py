"""
Validasi NIM Mahasiswa Unsoed
===============================
Fitur ini TIDAK melakukan brute-force/enumerasi NIM. Setiap baris data
(yang sudah punya kolom NIM dari user) di-cross-check SATU KALI ke sistem
resmi registrasi.unsoed.ac.id/info-mahasiswa, untuk:

1. Validasi format NIM (struktural, sebelum kirim request apa pun)
2. Konfirmasi NIM tsb terdaftar di sistem Unsoed
3. Cocokkan Nama / Fakultas / Program Studi yang diklaim vs data resmi

PRINSIP ETIS:
- 1 request per baris data yang user sediakan sendiri (tidak enumerasi nomor urut)
- Delay antar-request supaya tidak membebani server kampus
- Tidak menyimpan/expose data mahasiswa LAIN yang tidak ada di dataset user
- User bertanggung jawab bahwa NIM yang divalidasi memang miliknya sendiri
  atau data yang mereka punya hak untuk proses (mis. panitia BEM dgn data
  pendaftar resmi)
"""

import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

try:
    from thefuzz import fuzz
    _HAS_THEFUZZ = True
except ImportError:
    _HAS_THEFUZZ = False

INFO_MAHASISWA_URL = "https://registrasi.unsoed.ac.id/info-mahasiswa"

# Struktur umum NIM Unsoed: 3 karakter kode fakultas/prodi (huruf+angka+huruf,
# mis. "H1D") diikuti 6 digit (3 digit tahun angkatan + 3 digit nomor urut).
# Contoh: H1D024001 -> H1D | 024 (angkatan 2024) | 001 (no urut)
NIM_PATTERN = re.compile(r"^[A-Z][0-9][A-Z][0-9]{6}$")


def validate_nim_format(nim: str) -> Dict:
    """
    Validasi format NIM secara struktural TANPA request ke server apa pun.

    Returns dict: {valid, nim, kode_prefix, angkatan_tersirat, alasan}
    """
    if not isinstance(nim, str):
        nim = str(nim) if nim is not None else ""
    nim_clean = nim.strip().upper()

    if not nim_clean:
        return {"valid": False, "nim": nim_clean, "alasan": "NIM kosong"}

    if not NIM_PATTERN.match(nim_clean):
        return {
            "valid": False,
            "nim": nim_clean,
            "alasan": "Format tidak sesuai pola Unsoed (contoh: H1D024001 — "
                      "huruf-angka-huruf lalu 6 digit)",
        }

    tahun_3digit = nim_clean[3:6]
    # 3 digit ini merepresentasikan tahun angkatan (mis. "024" -> 2024).
    # Ambil 2 digit terakhir sebagai tahun pendek.
    tahun_2digit = tahun_3digit[-2:]
    return {
        "valid": True,
        "nim": nim_clean,
        "kode_prefix": nim_clean[:3],
        "angkatan_tersirat": f"20{tahun_2digit}" if tahun_2digit.isdigit() else None,
        "no_urut": nim_clean[6:],
        "alasan": None,
    }


def _get_session_and_token(session: requests.Session) -> Optional[str]:
    """Ambil CSRF token dari halaman form (perlu untuk POST)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    resp = session.get(INFO_MAHASISWA_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    match = re.search(r'name="_token"\s+value="([^"]+)"', resp.text)
    return match.group(1) if match else None


def fetch_mahasiswa_by_nim(nim: str, session: Optional[requests.Session] = None) -> Dict:
    """
    Query SATU NIM ke sistem resmi registrasi.unsoed.ac.id.
    Return dict berisi data resmi (nim, nama, angkatan, fakultas, prodi,
    pembiayaan, status) atau {"found": False} kalau NIM tidak terdaftar.

    Pass `session` (requests.Session) untuk reuse koneksi & token saat
    memvalidasi banyak baris sekaligus (hindari re-fetch token tiap kali).
    """
    own_session = session is None
    sess = session or requests.Session()

    try:
        token = _get_session_and_token(sess)
        if not token:
            return {"found": False, "error": "Gagal mengambil CSRF token dari server"}

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Referer": INFO_MAHASISWA_URL,
        }
        resp = sess.post(
            INFO_MAHASISWA_URL,
            data={"_token": token, "nim": nim},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        dl = soup.select_one("dl")
        if dl is None:
            return {"found": False}

        data = {}
        for row in dl.select("div"):
            dt = row.find("dt")
            dd = row.find("dd")
            if dt is None or dd is None:
                continue
            key = dt.get_text(strip=True).lower().replace(" ", "_")
            data[key] = dd.get_text(strip=True)

        if not data.get("nim"):
            return {"found": False}

        return {
            "found": True,
            "nim": data.get("nim"),
            "nama": data.get("nama"),
            "angkatan": data.get("angkatan"),
            "fakultas": data.get("fakultas"),
            "program_studi": data.get("program_studi"),
            "pembiayaan": data.get("pembiayaan"),
            "status": data.get("status"),
        }
    except requests.RequestException as e:
        return {"found": False, "error": str(e)}
    finally:
        if own_session:
            sess.close()


def _similarity(a: Optional[str], b: Optional[str]) -> float:
    """Skor kemiripan 0-100 antara dua string (case-insensitive)."""
    if not a or not b:
        return 0.0
    a, b = str(a).strip().lower(), str(b).strip().lower()
    if a == b:
        return 100.0
    if _HAS_THEFUZZ:
        return float(fuzz.token_sort_ratio(a, b))
    return 100.0 if a in b or b in a else 0.0


def validate_row(
    nim: str,
    claimed_nama: Optional[str] = None,
    claimed_fakultas: Optional[str] = None,
    claimed_prodi: Optional[str] = None,
    session: Optional[requests.Session] = None,
    nama_threshold: float = 70.0,
    fakultas_threshold: float = 70.0,
    prodi_threshold: float = 70.0,
) -> Dict:
    """
    Validasi lengkap 1 baris: format -> query server -> cocokkan klaim.

    Returns dict siap dipakai sebagai 1 baris hasil di tabel Streamlit:
        nim, format_valid, ditemukan, nama_resmi, nama_cocok,
        fakultas_resmi, fakultas_cocok, prodi_resmi, prodi_cocok,
        status_resmi, catatan
    """
    fmt = validate_nim_format(nim)
    result = {
        "nim": fmt["nim"],
        "format_valid": fmt["valid"],
        "ditemukan": None,
        "nama_resmi": None,
        "nama_cocok": None,
        "fakultas_resmi": None,
        "fakultas_cocok": None,
        "prodi_resmi": None,
        "prodi_cocok": None,
        "status_resmi": None,
        "catatan": fmt.get("alasan") or "",
    }

    if not fmt["valid"]:
        return result

    server_data = fetch_mahasiswa_by_nim(fmt["nim"], session=session)

    if server_data.get("error"):
        result["catatan"] = f"Gagal query server: {server_data['error']}"
        return result

    result["ditemukan"] = server_data.get("found", False)
    if not result["ditemukan"]:
        result["catatan"] = "NIM tidak ditemukan di sistem Unsoed"
        return result

    result["nama_resmi"] = server_data.get("nama")
    result["fakultas_resmi"] = server_data.get("fakultas")
    result["prodi_resmi"] = server_data.get("program_studi")
    result["status_resmi"] = server_data.get("status")

    if claimed_nama:
        sim = _similarity(claimed_nama, result["nama_resmi"])
        result["nama_cocok"] = sim >= nama_threshold
    if claimed_fakultas:
        sim = _similarity(claimed_fakultas, result["fakultas_resmi"])
        result["fakultas_cocok"] = sim >= fakultas_threshold
    if claimed_prodi:
        sim = _similarity(claimed_prodi, result["prodi_resmi"])
        result["prodi_cocok"] = sim >= prodi_threshold

    return result


def validate_dataframe_rows(
    rows: List[Dict],
    delay_seconds: float = 0.6,
    progress_callback=None,
) -> List[Dict]:
    """
    Validasi banyak baris SECARA BERURUTAN (bukan paralel) dengan delay
    antar-request untuk menghormati server Unsoed.

    rows: list of dict {nim, nama, fakultas, prodi} (nama/fakultas/prodi opsional)
    progress_callback: optional callable(current_index, total) dipanggil tiap baris,
        cocok untuk update st.progress() di Streamlit.

    Returns list of dict hasil validate_row(), urutan sama dengan input.
    """
    session = requests.Session()
    results = []
    total = len(rows)
    try:
        for i, row in enumerate(rows):
            res = validate_row(
                nim=row.get("nim", ""),
                claimed_nama=row.get("nama"),
                claimed_fakultas=row.get("fakultas"),
                claimed_prodi=row.get("prodi"),
                session=session,
            )
            results.append(res)
            if progress_callback:
                progress_callback(i + 1, total)
            if i < total - 1 and res["format_valid"]:
                # hanya delay kalau memang barusan kirim request ke server
                time.sleep(delay_seconds)
    finally:
        session.close()

    return results
