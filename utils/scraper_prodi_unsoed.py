"""
Scraper Data Program Studi Unsoed
===================================
Sumber: https://pendaftaran.admisi.unsoed.ac.id/apps/info/prodi-dan-daya-tampung

CATATAN:
- Halaman ini TIDAK memiliki API publik. Data prodi & daya tampung
  di-render sebagai HTML statis (blok <table> hasil CMS/rich-text editor).
- Scraper ini mem-parsing tabel HTML tersebut secara langsung.
- Karena bukan API resmi, struktur bisa berubah sewaktu-waktu jika halaman
  di-redesign — jalankan `refresh_prodi_data()` secara berkala untuk update.

OUTPUT:
- data/reference/prodi_unsoed.json  (list of dict, sumber utama)
- data/reference/prodi_unsoed.csv   (untuk dibuka manual/Excel)
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

URL_SOURCE = "https://pendaftaran.admisi.unsoed.ac.id/apps/info/prodi-dan-daya-tampung"

BASE_DIR = Path(__file__).parent.parent
REFERENCE_DIR = BASE_DIR / "data" / "reference"
JSON_PATH = REFERENCE_DIR / "prodi_unsoed.json"
CSV_PATH = REFERENCE_DIR / "prodi_unsoed.csv"

# Mapping section header (dalam HTML) -> nama kategori program yang rapi
SECTION_LABELS = {
    "PROGRAM SARJANA": "Sarjana (S1)",
    "PROGRAM SARJANA (KELAS INTERNASIONAL)": "Sarjana Kelas Internasional (S1)",
    "PROGRAM DIPLOMA 3": "Diploma 3 (D3)",
}


def _clean_text(text: Optional[str]) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def fetch_html(url: str = URL_SOURCE, timeout: int = 20) -> str:
    """Ambil HTML mentah dari halaman sumber."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_prodi_tables(html: str) -> List[Dict]:
    """
    Parse semua tabel prodi dari HTML halaman "prodi-dan-daya-tampung".

    Strategi:
    - Cari kontainer konten (.content-tables) berisi rangkaian <h2> (judul
      section) diikuti <table> (data section tsb).
    - Untuk tiap <table>, ambil header (thead > th) sebagai nama kolom,
      lalu setiap <tr> di tbody jadi satu baris dict.
    - Tambahkan kolom `kategori_program` dari <h2> section terdekat
      sebelumnya, dan `sumber_url` + `scraped_at` untuk traceability.
    """
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one(".content-tables")
    if container is None:
        # fallback: cari semua <table> di whole page
        container = soup

    records: List[Dict] = []
    current_section = "Lainnya"

    # Iterasi elemen anak container secara berurutan supaya h2 -> table terjaga urutannya
    for el in container.find_all(["h2", "table"], recursive=True):
        if el.name == "h2":
            raw = _clean_text(el.get_text())
            # buang emoji/simbol di depan judul, ambil label yang cocok
            matched = None
            # Cocokkan key TERPANJANG dulu supaya "PROGRAM SARJANA (KELAS
            # INTERNASIONAL)" tidak salah ke-match sebagai "PROGRAM SARJANA".
            for key, label in sorted(SECTION_LABELS.items(), key=lambda kv: -len(kv[0])):
                if key in raw.upper():
                    matched = label
                    break
            current_section = matched or raw
        elif el.name == "table":
            headers = [
                _clean_text(th.get_text())
                for th in el.select("thead th")
            ]
            if not headers:
                # fallback: pakai row pertama sebagai header
                first_row = el.find("tr")
                headers = [_clean_text(td.get_text()) for td in first_row.find_all(["td", "th"])] if first_row else []

            body_rows = el.select("tbody tr") or el.find_all("tr")[1:]

            for tr in body_rows:
                cells = tr.find_all("td")
                if not cells:
                    continue
                values = [_clean_text(td.get_text()) for td in cells]
                if not headers or len(values) < len(headers):
                    # baris tidak lengkap, skip
                    continue

                row_dict = {}
                for h, v in zip(headers, values):
                    key = _normalize_key(h)
                    row_dict[key] = v

                row_dict["kategori_program"] = current_section
                records.append(row_dict)

    return records


def _normalize_key(header: str) -> str:
    """Ubah nama kolom header jadi snake_case key yang konsisten."""
    mapping = {
        "no": "no",
        "kode": "kode_prodi",
        "nama program studi": "nama_prodi",
        "jenjang": "jenjang",
        "fakultas": "fakultas",
        "peringkat": "akreditasi",
    }
    key = header.strip().lower()
    return mapping.get(key, re.sub(r"[^a-z0-9]+", "_", key).strip("_"))


def build_search_aliases(records: List[Dict]) -> List[Dict]:
    """
    Tambahkan field `aliases` per prodi untuk mempermudah fuzzy/keyword
    matching saat deteksi jurusan dari teks bebas (mis. jawaban survei).

    Aliases mencakup: nama asli, versi tanpa 'Kelas Internasional',
    singkatan umum (kalau ada di dictionary), dan nama tanpa kata jenjang.
    """
    common_abbr = {
        "teknik informatika": ["ti", "if", "informatika"],
        "sistem informasi": ["si", "sisfo"],
        "ilmu hukum": ["hukum"],
        "ilmu komunikasi": ["ikom", "komunikasi"],
        "manajemen": ["mnj"],
        "akuntansi": ["akun"],
        "kedokteran": ["fk"],
        "kedokteran gigi": ["fkg"],
        "kedokteran hewan": ["fkh"],
        "hubungan internasional": ["hi"],
        "ilmu pemerintahan": ["ip"],
        "administrasi publik": ["ap"],
        "administrasi bisnis": ["ab", "adbis"],
        "agroteknologi": ["agtek"],
        "agribisnis": ["agb"],
        "peternakan": ["fapet"],
        "perikanan dan kelautan": ["fpik", "perikanan", "kelautan"],
        "biologi": ["bio"],
        "matematika": ["mtk"],
        "fisika": ["fis"],
        "kimia": ["kim"],
        "farmasi": ["farm"],
        "keperawatan": ["kep"],
        "psikologi": ["psi"],
        "teknik sipil": ["sipil"],
        "teknik elektro": ["elektro"],
        "arsitektur": ["ars"],
        "ekonomi pembangunan": ["ep"],
    }

    for r in records:
        nama = r.get("nama_prodi", "")
        nama_lower = nama.lower()
        aliases = {nama_lower}

        # versi tanpa embel-embel kelas internasional
        stripped = re.sub(r"\s*kelas internasional\s*", "", nama_lower).strip()
        if stripped:
            aliases.add(stripped)

        # cocokkan ke dictionary singkatan (exact atau substring match)
        for full, abbrs in common_abbr.items():
            if full in nama_lower or nama_lower in full:
                aliases.update(abbrs)
                aliases.add(full)

        r["aliases"] = sorted(a for a in aliases if a)

    return records


def refresh_prodi_data(url: str = URL_SOURCE) -> List[Dict]:
    """
    Ambil ulang data dari sumber, parse, simpan ke JSON & CSV.
    Return list of dict hasil scraping.
    """
    html = fetch_html(url)
    records = parse_prodi_tables(html)
    records = build_search_aliases(records)

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "data": records,
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # simpan versi CSV juga (tanpa kolom aliases yang berupa list)
    try:
        import pandas as pd
        df = pd.DataFrame(records)
        if "aliases" in df.columns:
            df["aliases"] = df["aliases"].apply(lambda x: "|".join(x) if isinstance(x, list) else x)
        df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    except ImportError:
        pass

    return records


def load_prodi_data(auto_refresh_if_missing: bool = True) -> List[Dict]:
    """
    Load data prodi dari cache JSON lokal. Jika belum ada dan
    auto_refresh_if_missing=True, scrape dulu dari sumber.
    """
    if not JSON_PATH.exists():
        if auto_refresh_if_missing:
            return refresh_prodi_data()
        return []

    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return payload.get("data", [])


def get_last_scraped_info() -> Optional[Dict]:
    """Return metadata scraping terakhir (source_url, scraped_at, total_records)."""
    if not JSON_PATH.exists():
        return None
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return {
        "source_url": payload.get("source_url"),
        "scraped_at": payload.get("scraped_at"),
        "total_records": payload.get("total_records"),
    }


if __name__ == "__main__":
    data = refresh_prodi_data()
    print(f"Scraped {len(data)} program studi dari {URL_SOURCE}")
    for d in data[:5]:
        print(d)
