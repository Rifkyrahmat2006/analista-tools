"""
Deteksi & Normalisasi Jurusan/Program Studi
=============================================
Mencocokkan teks bebas (jawaban survei responden, mis. "TI", "tek informatika",
"Teknik Informatika S1") ke daftar program studi resmi Unsoed hasil scraping
(lihat utils/scraper_prodi_unsoed.py).

Pipeline:
1. Normalisasi teks input (lowercase, strip, buang noise umum: "s1", "jurusan", dll)
2. Exact match ke nama_prodi / alias
3. Kalau tidak exact, fuzzy match (thefuzz) ke seluruh nama_prodi + alias
4. Return kode_prodi, nama_prodi resmi, fakultas, skor kepercayaan match

Dipakai di:
- pages/2_data_cleaning.py -> tab baru "Deteksi Jurusan" (standardisasi kolom prodi)
- utils/question_detection.py -> bisa dipanggil sebagai heuristic tambahan untuk
  mendeteksi kolom yang berisi nama program studi/jurusan
"""

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from utils.scraper_prodi_unsoed import load_prodi_data

try:
    from thefuzz import fuzz, process
    _HAS_THEFUZZ = True
except ImportError:
    _HAS_THEFUZZ = False

# Noise words yang sering ikut terketik responden dan perlu dibuang sebelum matching
_NOISE_PATTERN = re.compile(
    r"\b(jurusan|prodi|program studi|fakultas|s1|s\.1|d3|d\.3|kelas internasional|"
    r"international class|reguler)\b",
    flags=re.IGNORECASE,
)


def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.lower().strip()
    t = _NOISE_PATTERN.sub("", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _detect_jenjang(text: str) -> Optional[str]:
    """Deteksi jenjang (S1/D3) yang disebut eksplisit di teks mentah, sebelum di-strip."""
    if not isinstance(text, str):
        return None
    t = text.upper()
    if re.search(r"\bD\s?\.?\s?I{2,3}\b|\bD3\b|\bD-3\b", t):
        return "D3"
    if re.search(r"\bS\s?\.?\s?1\b", t):
        return "S1"
    return None


def _build_lookup(prodi_data: List[Dict]) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    Bangun index: alias_string -> list of record prodi (bisa lebih dari satu
    kalau nama sama muncul di jenjang berbeda, mis. "Akuntansi" ada di S1
    dan D3), plus daftar semua alias (untuk fuzzy candidate pool).
    """
    lookup: Dict[str, List[Dict]] = {}
    for rec in prodi_data:
        candidates = set(rec.get("aliases", []))
        candidates.add(rec.get("nama_prodi", "").lower())
        for c in candidates:
            norm = _normalize(c)
            if not norm:
                continue
            lookup.setdefault(norm, [])
            if rec not in lookup[norm]:
                lookup[norm].append(rec)
    return lookup, list(lookup.keys())


def _pick_record(candidates: List[Dict], jenjang_hint: Optional[str]) -> Dict:
    """Kalau satu alias punya >1 record (beda jenjang), pilih yang cocok dengan hint jenjang."""
    if len(candidates) == 1 or not jenjang_hint:
        return candidates[0]
    for c in candidates:
        if c.get("jenjang") == jenjang_hint:
            return c
    return candidates[0]


def match_prodi(
    text: str,
    prodi_data: Optional[List[Dict]] = None,
    fuzzy_threshold: int = 80,
) -> Optional[Dict]:
    """
    Cocokkan satu string input ke program studi resmi.

    Returns dict berisi:
        kode_prodi, nama_prodi, fakultas, jenjang, kategori_program,
        match_type ('exact' | 'fuzzy' | 'none'), confidence (0-100)
    atau None jika input kosong.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return None

    if prodi_data is None:
        prodi_data = load_prodi_data()

    lookup, all_keys = _build_lookup(prodi_data)
    norm_input = _normalize(text)
    jenjang_hint = _detect_jenjang(text)

    if not norm_input:
        return None

    # 1. Exact match
    if norm_input in lookup:
        rec = _pick_record(lookup[norm_input], jenjang_hint)
        return _format_result(rec, "exact", 100)

    # 2. Fuzzy match
    if _HAS_THEFUZZ and all_keys:
        best = process.extractOne(norm_input, all_keys, scorer=fuzz.token_sort_ratio)
        if best and best[1] >= fuzzy_threshold:
            rec = _pick_record(lookup[best[0]], jenjang_hint)
            return _format_result(rec, "fuzzy", best[1])

    # 3. Keyword-containment match (fallback terakhir, HATI-HATI false positive):
    # cek apakah input = alias resmi + kata filler generik saja, mis.
    # "ahli gizi" -> alias "gizi" + filler "ahli" -> match ke "Ilmu Gizi".
    # TIDAK dipakai kalau kata sisanya adalah disiplin ilmu lain (mis.
    # "teknik kimia" TIDAK boleh match ke "Kimia" karena "teknik" bukan
    # filler, itu penanda program studi berbeda yang mungkin tidak ada).
    _FILLER_WORDS = {"ahli", "sarjana", "tenaga", "jurusan", "bidang", "ilmu", "program"}
    input_words = set(norm_input.split())
    keyword_candidates = []
    for key in all_keys:
        if len(key) < 4:
            continue
        key_words = key.split()
        if len(key_words) == 1 and key in input_words:
            leftover = input_words - set(key_words)
            if leftover and not leftover.issubset(_FILLER_WORDS):
                continue  # ada kata non-filler tersisa -> terlalu berisiko, skip
            keyword_candidates.append(key)
        elif len(key_words) > 1 and f" {key} " in f" {norm_input} ":
            leftover = input_words - set(key_words)
            if leftover and not leftover.issubset(_FILLER_WORDS):
                continue
            keyword_candidates.append(key)

    if keyword_candidates:
        # pilih alias terpanjang (paling spesifik) untuk menghindari ambiguitas
        best_key = max(keyword_candidates, key=len)
        rec = _pick_record(lookup[best_key], jenjang_hint)
        return _format_result(rec, "keyword", 60)

    return _format_result(None, "none", 0, raw_text=text)


def _format_result(rec: Optional[Dict], match_type: str, confidence: float, raw_text: str = "") -> Dict:
    if rec is None:
        return {
            "input_text": raw_text,
            "kode_prodi": None,
            "nama_prodi": None,
            "fakultas": None,
            "jenjang": None,
            "kategori_program": None,
            "akreditasi": None,
            "match_type": match_type,
            "confidence": confidence,
        }
    return {
        "input_text": raw_text,
        "kode_prodi": rec.get("kode_prodi"),
        "nama_prodi": rec.get("nama_prodi"),
        "fakultas": rec.get("fakultas"),
        "jenjang": rec.get("jenjang"),
        "kategori_program": rec.get("kategori_program"),
        "akreditasi": rec.get("akreditasi"),
        "match_type": match_type,
        "confidence": confidence,
    }


def detect_prodi_column(series: pd.Series, sample_size: int = 50, min_match_ratio: float = 0.5) -> bool:
    """
    Heuristic: apakah sebuah kolom survei kemungkinan besar berisi nama
    program studi/jurusan? Dicek dengan mencoba match sample nilai unik
    ke database prodi.

    Return True jika >= min_match_ratio dari sample berhasil match
    (exact atau fuzzy dengan confidence tinggi).
    """
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False

    unique_vals = non_null.unique().tolist()[:sample_size]
    if not unique_vals:
        return False

    prodi_data = load_prodi_data()
    matched = 0
    for v in unique_vals:
        result = match_prodi(v, prodi_data=prodi_data, fuzzy_threshold=85)
        if result and result["match_type"] in ("exact", "fuzzy"):
            matched += 1

    return (matched / len(unique_vals)) >= min_match_ratio


def normalize_prodi_column(series: pd.Series, fuzzy_threshold: int = 80) -> pd.DataFrame:
    """
    Terapkan match_prodi ke seluruh kolom, return DataFrame hasil dengan
    kolom tambahan: nama_prodi_std, nama_prodi_display, kode_prodi,
    fakultas, jenjang, match_type, confidence.

    nama_prodi_display berformat "S1/D3 Nama Prodi" (mis. "S1 Kimia",
    "D3 Akuntansi") — cocok dipakai langsung sebagai label chart/visualisasi
    karena tetap membedakan prodi yang sama namanya tapi beda jenjang.

    Cocok dipakai di pages/2_data_cleaning.py untuk standarisasi kolom
    "Jurusan/Prodi asal" pada survei.
    """
    prodi_data = load_prodi_data()

    results = []
    for val in series:
        r = match_prodi(str(val) if pd.notna(val) else "", prodi_data=prodi_data, fuzzy_threshold=fuzzy_threshold)
        results.append(r or {})

    result_df = pd.DataFrame(results)
    result_df.rename(columns={"nama_prodi": "nama_prodi_std"}, inplace=True)

    def _make_display(row) -> Optional[str]:
        nama = row.get("nama_prodi_std")
        jenjang = row.get("jenjang")
        if not nama or pd.isna(nama):
            return None
        if not jenjang or pd.isna(jenjang):
            return nama
        return f"{jenjang} {nama}"

    result_df["nama_prodi_display"] = result_df.apply(_make_display, axis=1)
    return result_df
