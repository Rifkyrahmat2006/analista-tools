"""
Merge Suggestions
==================
Hitung rekomendasi penggabungan kandidat cluster berdasarkan kemiripan semantik.

PRINSIP:
- Tidak ada AI/API
- Keputusan merge tetap di tangan analis
- Hanya sarankan merge jika ada bukti kuat (bukan hanya kata umum)

Scoring menggunakan kombinasi:
1. Centroid Cosine Similarity (bobot 0.50)
2. Substantive Phrase/Keyword Overlap (bobot 0.40)  ← lebih ketat dari sebelumnya
3. Penalti generic term overlap (bobot -0.10)

False positive dikurangi dengan:
- Mensyaratkan minimal 1 overlap di substantive term atau phrase
- Memberikan penalti untuk overlap kata-kata umum saja
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import scipy.sparse as sp
from typing import List, Dict, Set

# ---------------------------------------------------------------------------
# GENERIC TERMS (Kata umum yang TIDAK menjadi dasar merge)
# ---------------------------------------------------------------------------
# Diperluas dari versi sebelumnya untuk mengurangi false positive
GENERIC_TERMS: Set[str] = {
    # Konteks kampus umum
    "mahasiswa", "organisasi", "program", "lembaga", "kegiatan",
    "kampus", "bem", "kementerian", "panitia", "acara", "univ", "universitas",
    # Kata kerja modal umum
    "cara", "alam", "kerja", "orang", "pihak", "hal", "waktu", "satu",
    # Kata sifat umum
    "baik", "lebih", "besar", "banyak", "lain", "setiap", "semua",
    # Filler survei
    "langsung", "perlu", "harus", "akan", "bisa", "dapat",
}


def _get_term_weight(term: str) -> float:
    """
    Bobot untuk satu term.
    Kata umum diberi bobot 0.1 (hampir tidak dihitung).
    Kata substantif diberi bobot 1.0.
    """
    return 0.1 if term.lower() in GENERIC_TERMS else 1.0


def _weighted_keyword_overlap(
    kw_a: List[str],
    kw_b: List[str],
) -> float:
    """
    Hitung weighted Jaccard similarity antara dua keyword list.
    Generic terms diberi bobot sangat rendah (0.1).
    
    Returns:
        Weighted Jaccard similarity (0.0 - 1.0)
    """
    set_a = set(kw_a)
    set_b = set(kw_b)
    
    overlap = set_a.intersection(set_b)
    union = set_a.union(set_b)
    
    if not union:
        return 0.0
    
    weighted_overlap = sum(_get_term_weight(w) for w in overlap)
    weighted_union = sum(_get_term_weight(w) for w in union)
    
    return weighted_overlap / weighted_union if weighted_union > 0 else 0.0


def _phrase_overlap_score(
    phrases_a: List[str],
    phrases_b: List[str],
) -> float:
    """
    Hitung skor overlap frasa (bigram/phrase).
    Phrase overlap jauh lebih bermakna daripada single keyword overlap.
    
    Returns:
        Score 0.0-1.0 (1.0 = semua frasa overlap)
    """
    if not phrases_a or not phrases_b:
        return 0.0
    
    set_a = set(p.lower() for p in phrases_a)
    set_b = set(p.lower() for p in phrases_b)
    
    overlap = set_a.intersection(set_b)
    
    # Jaccard similarity frasa
    union = set_a.union(set_b)
    return len(overlap) / len(union) if union else 0.0


def _has_meaningful_overlap(
    kw_a: List[str],
    kw_b: List[str],
    phrases_a: List[str],
    phrases_b: List[str],
) -> bool:
    """
    Cek apakah ada overlap bermakna (bukan hanya kata umum).
    
    Syarat: Minimal salah satu dari:
    - Ada frasa yang overlap
    - Ada minimal 1 substantive keyword (non-generic) yang overlap
    """
    # Cek phrase overlap
    set_pa = set(p.lower() for p in phrases_a)
    set_pb = set(p.lower() for p in phrases_b)
    if set_pa.intersection(set_pb):
        return True
    
    # Cek substantive keyword overlap
    set_a = set(w.lower() for w in kw_a if w.lower() not in GENERIC_TERMS)
    set_b = set(w.lower() for w in kw_b if w.lower() not in GENERIC_TERMS)
    
    if set_a.intersection(set_b):
        return True
    
    return False


def calculate_merge_suggestions(
    groups: dict,
    tfidf_matrix,
    resp_ids: list,
    threshold: float = 0.35,
) -> List[Dict]:
    """
    Hitung similarity antar Candidate Group untuk mengusulkan merge.
    Tidak menggunakan AI/API, hanya perhitungan similarity lokal.

    PERBAIKAN dari versi sebelumnya:
    - Scoring lebih ketat: Membutuhkan bukti meaningful overlap
    - Penalti untuk overlap kata-kata umum saja (GENERIC_TERMS)
    - False positive dikurangi dengan syarat: HARUS ada phrase atau
      substantive keyword overlap, tidak cukup hanya centroid similarity

    Args:
        groups    : Dict of {group_id: CandidateGroup}
        tfidf_matrix : Sparse TF-IDF matrix dari semua valid responses
        resp_ids  : List of response_ids yang sesuai dengan urutan baris
        threshold : Ambang batas composite score untuk disarankan (default 0.35)

    Returns:
        List of dicts berisi usulan merge, sorted by composite score desc.
    """
    if not groups or len(groups) < 2 or tfidf_matrix is None or not resp_ids:
        return []

    # Hanya evaluasi group yang bukan 'Other'
    eval_groups = {gid: g for gid, g in groups.items() if not g.is_other}
    group_ids = list(eval_groups.keys())
    n_groups = len(group_ids)

    if n_groups < 2:
        return []

    # Map response_id → index baris tfidf_matrix
    resp_id_to_idx = {rid: i for i, rid in enumerate(resp_ids)}

    # Hitung centroid per group
    centroids = {}
    for gid, group in eval_groups.items():
        indices = [resp_id_to_idx[rid] for rid in group.response_ids if rid in resp_id_to_idx]
        if not indices:
            centroids[gid] = None
            continue

        group_matrix = tfidf_matrix[indices]
        if sp.issparse(group_matrix):
            centroid = np.array(group_matrix.mean(axis=0))
        else:
            centroid = group_matrix.mean(axis=0)
        centroids[gid] = centroid.reshape(1, -1)

    suggestions = []

    for i in range(n_groups):
        for j in range(i + 1, n_groups):
            gid_a = group_ids[i]
            gid_b = group_ids[j]
            group_a = eval_groups[gid_a]
            group_b = eval_groups[gid_b]

            c_a = centroids[gid_a]
            c_b = centroids[gid_b]

            if c_a is None or c_b is None:
                continue

            # ── 1. Centroid Cosine Similarity (bobot 0.50) ───────────────────
            centroid_sim = float(cosine_similarity(c_a, c_b)[0][0])

            # ── 2. Weighted Keyword Overlap (bobot 0.40) ─────────────────────
            kw_a = list(group_a.top_keywords or [])
            kw_b = list(group_b.top_keywords or [])
            weighted_kw_overlap = _weighted_keyword_overlap(kw_a, kw_b)

            # ── 3. Phrase Overlap (bobot 0.30, bonus) ────────────────────────
            ph_a = list(group_a.top_phrases or [])
            ph_b = list(group_b.top_phrases or [])
            phrase_sim = _phrase_overlap_score(ph_a, ph_b)

            # ── 4. Penalti generic-only overlap ──────────────────────────────
            # Jika overlap keyword HANYA berisi generic terms → composite diturunkan
            overlap_kw = set(kw_a).intersection(set(kw_b))
            generic_only_overlap = all(w.lower() in GENERIC_TERMS for w in overlap_kw) if overlap_kw else False
            generic_penalty = 0.15 if generic_only_overlap else 0.0

            # ── 5. Composite Score ────────────────────────────────────────────
            composite = (
                centroid_sim * 0.50
                + weighted_kw_overlap * 0.30
                + phrase_sim * 0.20
                - generic_penalty
            )

            # ── 6. GUARD: Hanya sarankan merge jika ada meaningful overlap ───
            has_meaningful = _has_meaningful_overlap(kw_a, kw_b, ph_a, ph_b)

            # Syarat merge: composite >= threshold DAN ada meaningful overlap
            if composite >= threshold and has_meaningful:
                suggestions.append({
                    "group_a": gid_a,
                    "group_b": gid_b,
                    "score": composite,
                    "centroid_sim": centroid_sim,
                    "weighted_kw_overlap": float(weighted_kw_overlap),
                    "phrase_sim": float(phrase_sim),
                    "overlap_keywords": list(overlap_kw - GENERIC_TERMS),  # tampilkan non-generic saja
                    "overlap_phrases": list(set(p.lower() for p in ph_a).intersection(set(p.lower() for p in ph_b))),
                    "reason": _build_merge_reason(centroid_sim, weighted_kw_overlap, phrase_sim, overlap_kw - GENERIC_TERMS),
                })

    # Urutkan berdasarkan skor tertinggi
    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions


def _build_merge_reason(
    centroid_sim: float,
    kw_overlap: float,
    phrase_sim: float,
    substantive_overlap_kw: set,
) -> str:
    """Buat string penjelasan singkat alasan merge disarankan."""
    reasons = []
    if centroid_sim >= 0.5:
        reasons.append(f"kemiripan vector tinggi ({centroid_sim:.2f})")
    elif centroid_sim >= 0.35:
        reasons.append(f"kemiripan vector sedang ({centroid_sim:.2f})")

    if phrase_sim > 0:
        reasons.append(f"ada frasa yang sama")

    if substantive_overlap_kw:
        kw_str = ", ".join(list(substantive_overlap_kw)[:3])
        reasons.append(f"berbagi kata kunci substantif: {kw_str}")

    return " | ".join(reasons) if reasons else "Kemiripan umum"
