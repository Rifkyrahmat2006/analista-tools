"""
Concept Analysis
================
Pipeline multi-label concept extraction untuk pertanyaan terbuka tipe Concept/Option.

Prinsip:
  - Satu respons DAPAT mengandung beberapa konsep sekaligus
  - "Project, mentoring, dan simulasi" → 3 concept mentions, BUKAN 1 cluster
  - Persentase dihitung: unique_responses_mentioning / total_valid (bisa > 100% total)
  - Konsep dinormalisasi via CONCEPT_FAMILIES dictionary (editable)

Digunakan untuk mode: concept, reason, barrier, recommendation
"""

import re
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# CONCEPT FAMILIES — editable normalization dictionary
# Format: { "canonical_name": ["variant1", "variant2", ...] }
# ---------------------------------------------------------------------------

DEFAULT_CONCEPT_FAMILIES: Dict[str, List[str]] = {
    # ── METODE PENGEMBANGAN DIRI ────────────────────────────────────────────
    "Project / Project-Based Learning": [
        "project", "proyek", "projek", "project based", "project-based",
        "pbl", "pembelajaran berbasis proyek", "project based learning",
        "project nyata", "proyek nyata", "project kolaboratif",
    ],
    "Mentoring": [
        "mentoring", "mentor", "pendampingan", "bimbingan", "mentoring langsung",
        "pendampingan mentor", "bimbingan mentor", "peer mentoring",
    ],
    "Workshop": [
        "workshop", "pelatihan", "training", "webinar", "seminar",
        "workshop pelatihan", "training intensif", "workshop intensif",
        "pelatihan intensif", "seminar workshop",
    ],
    "Coaching": [
        "coaching", "coach", "life coaching", "coaching session",
    ],
    "Simulasi / Role Play": [
        "simulasi", "role play", "roleplay", "simulasi nyata",
        "simulasi praktik", "role-play", "simulasi kasus",
    ],
    "Magang / Internship": [
        "magang", "internship", "kerja praktik", "kp", "pkl",
        "kerja lapangan", "praktik kerja", "on the job training",
    ],
    "Diskusi / Forum": [
        "diskusi", "forum", "focus group", "fgd", "diskusi kelompok",
        "forum diskusi", "group discussion",
    ],
    "Studi Kasus": [
        "studi kasus", "case study", "kasus nyata",
        "pembelajaran kasus", "analisis kasus",
    ],
    "Lomba / Kompetisi": [
        "lomba", "kompetisi", "perlombaan", "competition", "contest",
        "kejuaraan", "turnamen",
    ],
    "Organisasi": [
        "organisasi", "berorganisasi", "ikut organisasi",
        "aktif organisasi", "kegiatan organisasi",
    ],
    "Volunteering": [
        "volunteer", "volunteering", "relawan", "sukarela",
        "kegiatan sosial", "pengabdian masyarakat",
    ],
    "Membaca / Riset Mandiri": [
        "membaca", "baca buku", "riset mandiri", "self study",
        "belajar mandiri", "otodidak", "self learning",
    ],
    "Networking": [
        "networking", "jaringan", "koneksi", "relasi",
        "membangun relasi", "membangun koneksi",
    ],
    # ── FASILITAS & INFRASTRUKTUR ──────────────────────────────────────────
    "Kebersihan": [
        "kebersihan", "bersih", "higienitas", "sanitasi",
        "kebersihan lingkungan",
    ],
    "Wifi / Internet": [
        "wifi", "internet", "koneksi internet", "jaringan internet",
        "akses internet", "hotspot",
    ],
    "Ruang Kelas": [
        "ruang kelas", "kelas", "ruangan", "ruang belajar",
        "classroom", "fasilitas kelas",
    ],
    "Laboratorium": [
        "lab", "laboratorium", "lab komputer", "lab sains",
        "fasilitas lab",
    ],
    "Perpustakaan": [
        "perpustakaan", "library", "pustaka", "koleksi buku",
    ],
    "Parkir": [
        "parkir", "area parkir", "tempat parkir", "lahan parkir",
    ],
    "Kantin": [
        "kantin", "cafetaria", "makanan", "makan siang", "food court",
    ],
    # ── ORGANISASI & MANAJEMEN ─────────────────────────────────────────────
    "Transparansi": [
        "transparansi", "transparan", "keterbukaan", "terbuka",
        "open", "informasi terbuka",
    ],
    "Komunikasi": [
        "komunikasi", "koordinasi", "koordinir", "penyampaian informasi",
        "informasi", "penyebaran info",
    ],
    "Kaderisasi": [
        "kaderisasi", "kader", "rekrutmen", "regenerasi", "perekrutan",
    ],
    "Program Kerja": [
        "program kerja", "proker", "program", "kegiatan", "agenda",
    ],
}


# ---------------------------------------------------------------------------
# CONCEPT EXTRACTOR CLASS
# ---------------------------------------------------------------------------

class ConceptExtractor:
    """
    Multi-label concept extractor.
    Setiap respons bisa memiliki 0 atau lebih konsep yang terdeteksi.
    """

    def __init__(
        self,
        concept_families: Optional[Dict[str, List[str]]] = None,
        normalization_dict: Optional[Dict[str, str]] = None,
        stopwords: Optional[Set[str]] = None,
    ):
        self.concept_families = concept_families or DEFAULT_CONCEPT_FAMILIES
        self.normalization_dict = normalization_dict or {}
        self.stopwords = stopwords or set()

        # Build lookup: variant_lower → canonical_name
        self._variant_to_canonical: Dict[str, str] = {}
        for canonical, variants in self.concept_families.items():
            for v in variants:
                self._variant_to_canonical[v.lower().strip()] = canonical
            # Also map the canonical itself
            self._variant_to_canonical[canonical.lower().strip()] = canonical

        # Sort variants by length desc (longest match first to avoid partial matches)
        self._sorted_variants: List[Tuple[int, str, str]] = sorted(
            [
                (len(v), v.lower().strip(), canonical)
                for canonical, variants in self.concept_families.items()
                for v in variants
            ],
            key=lambda x: -x[0],
        )

    def normalize(self, text: str) -> str:
        """Normalisasi teks: lowercase, apply normalization dict."""
        text = text.lower().strip()
        # Apply normalization dict (word by word)
        words = text.split()
        words = [self.normalization_dict.get(w, w) for w in words]
        return " ".join(words)

    def extract_concepts_from_text(self, text: str) -> List[str]:
        """
        Ekstrak daftar konsep canonical dari satu teks respons.
        Returns list of canonical concept names found in text.
        """
        if not text or not isinstance(text, str):
            return []

        normalized = self.normalize(text)
        found_concepts: Set[str] = set()
        remaining = normalized

        # Match longest variants first
        for _, variant, canonical in self._sorted_variants:
            # Use word-boundary-aware matching
            pattern = r"(?<!\w)" + re.escape(variant) + r"(?!\w)"
            if re.search(pattern, remaining, re.IGNORECASE):
                found_concepts.add(canonical)
                # Mark matched span (replace to avoid double-counting)
                remaining = re.sub(pattern, " ", remaining, flags=re.IGNORECASE)

        return list(found_concepts)

    def extract_all(
        self,
        texts: List[str],
        response_ids: Optional[List[str]] = None,
    ) -> Dict:
        """
        Ekstrak konsep dari semua teks.

        Returns:
            {
                "concept_counts": {concept: mention_count},
                "response_mentions": {concept: [resp_ids]},
                "response_concept_map": {resp_id: [concepts]},
                "top_concepts": [(name, count, pct)],
                "cooccurrence": {(c1, c2): count},
                "total_valid": int,
                "uncategorized_count": int,
            }
        """
        if response_ids is None:
            response_ids = [str(i) for i in range(len(texts))]

        concept_counts: Counter = Counter()
        response_mentions: Dict[str, List[str]] = defaultdict(list)
        response_concept_map: Dict[str, List[str]] = {}
        cooccurrence: Counter = Counter()
        uncategorized = 0

        total_valid = len(texts)

        for resp_id, text in zip(response_ids, texts):
            concepts = self.extract_concepts_from_text(text)
            response_concept_map[resp_id] = concepts

            if not concepts:
                uncategorized += 1
            else:
                for c in concepts:
                    concept_counts[c] += 1
                    response_mentions[c].append(resp_id)

                # Co-occurrence (unique pairs in this response)
                unique_concepts = list(set(concepts))
                for i in range(len(unique_concepts)):
                    for j in range(i + 1, len(unique_concepts)):
                        pair = tuple(sorted([unique_concepts[i], unique_concepts[j]]))
                        cooccurrence[pair] += 1

        # Build top_concepts: sorted by count desc
        top_concepts = [
            (name, count, round(count / total_valid * 100, 1) if total_valid > 0 else 0.0)
            for name, count in concept_counts.most_common()
        ]

        return {
            "concept_counts": dict(concept_counts),
            "response_mentions": dict(response_mentions),
            "response_concept_map": response_concept_map,
            "top_concepts": top_concepts,
            "cooccurrence": dict(cooccurrence),
            "total_valid": total_valid,
            "uncategorized_count": uncategorized,
        }


# ---------------------------------------------------------------------------
# LIGHTWEIGHT KEYWORD FREQUENCY (untuk mode tanpa concept families)
# ---------------------------------------------------------------------------

def extract_keyword_concepts(
    texts: List[str],
    response_ids: Optional[List[str]] = None,
    normalization_dict: Optional[Dict[str, str]] = None,
    stopwords: Optional[Set[str]] = None,
    top_n: int = 20,
    min_freq: int = 2,
) -> Dict:
    """
    Fallback concept extraction berbasis TF-IDF keyword frequency.
    Digunakan ketika concept families tidak cukup spesifik.

    Returns:
        {
            "top_concepts": [(term, count, pct)],
            "response_mentions": {term: [resp_ids]},
            "total_valid": int,
        }
    """
    from sklearn.feature_extraction.text import CountVectorizer

    if response_ids is None:
        response_ids = [str(i) for i in range(len(texts))]

    total_valid = len(texts)
    norm_dict = normalization_dict or {}
    sw = stopwords or set()

    def preprocess(text: str) -> str:
        t = text.lower().strip()
        words = t.split()
        words = [norm_dict.get(w, w) for w in words]
        words = [w for w in words if w not in sw and len(w) > 2]
        return " ".join(words)

    processed = [preprocess(t) for t in texts]
    non_empty = [t for t in processed if t.strip()]

    if not non_empty:
        return {
            "top_concepts": [],
            "response_mentions": {},
            "total_valid": total_valid,
        }

    try:
        vec = CountVectorizer(
            ngram_range=(1, 2),
            min_df=min_freq,
            max_df=0.85,
            max_features=200,
        )
        mat = vec.fit_transform(processed)
        feature_names = vec.get_feature_names_out()

        # Count responses (rows) that contain each term
        doc_freq = (mat > 0).sum(axis=0).A1  # type: ignore
        term_freq = mat.sum(axis=0).A1  # type: ignore

        # Build top concepts
        indices = np.argsort(-doc_freq)[:top_n]
        top_concepts = []
        response_mentions: Dict[str, List[str]] = {}

        for idx in indices:
            term = feature_names[idx]
            resp_count = int(doc_freq[idx])
            if resp_count < min_freq:
                continue
            pct = round(resp_count / total_valid * 100, 1) if total_valid > 0 else 0.0
            top_concepts.append((term, resp_count, pct))

            # Find which responses mention this term
            mention_mask = mat[:, idx].toarray().flatten() > 0
            mentions = [response_ids[i] for i, hit in enumerate(mention_mask) if hit]
            response_mentions[term] = mentions

        return {
            "top_concepts": top_concepts,
            "response_mentions": response_mentions,
            "total_valid": total_valid,
        }

    except Exception:
        return {
            "top_concepts": [],
            "response_mentions": {},
            "total_valid": total_valid,
        }


# ---------------------------------------------------------------------------
# HIGH-LEVEL API
# ---------------------------------------------------------------------------

def run_concept_analysis(
    texts: List[str],
    response_ids: Optional[List[str]] = None,
    concept_families: Optional[Dict[str, List[str]]] = None,
    normalization_dict: Optional[Dict[str, str]] = None,
    stopwords: Optional[Set[str]] = None,
    fallback_to_keywords: bool = True,
    top_n: int = 15,
) -> Dict:
    """
    Jalankan concept analysis lengkap.

    Urutan:
    1. Coba ConceptExtractor (dictionary-based)
    2. Jika coverage < 30%, fallback ke keyword-based
    3. Return standardized result

    Returns:
        {
            "mode": "dictionary" | "keyword",
            "top_concepts": [(name, count, pct), ...],
            "response_mentions": {concept: [resp_ids]},
            "response_concept_map": {resp_id: [concepts]},
            "cooccurrence": dict,
            "total_valid": int,
            "coverage_pct": float,
            "uncategorized_count": int,
        }
    """
    if response_ids is None:
        response_ids = [str(i) for i in range(len(texts))]

    total_valid = len(texts)

    extractor = ConceptExtractor(
        concept_families=concept_families,
        normalization_dict=normalization_dict,
        stopwords=stopwords,
    )

    result = extractor.extract_all(texts, response_ids)
    covered = total_valid - result["uncategorized_count"]
    coverage_pct = (covered / total_valid * 100) if total_valid > 0 else 0.0

    # If dictionary coverage is very low, supplement with keyword extraction
    if fallback_to_keywords and coverage_pct < 30 and total_valid > 0:
        kw_result = extract_keyword_concepts(
            texts,
            response_ids=response_ids,
            normalization_dict=normalization_dict,
            stopwords=stopwords,
            top_n=top_n,
            min_freq=max(2, total_valid // 20),
        )
        # Merge: dictionary results take precedence, keyword fills remaining
        merged_top = result["top_concepts"][:]
        existing_names = {c[0] for c in merged_top}
        for name, count, pct in kw_result["top_concepts"]:
            if name not in existing_names:
                merged_top.append((name, count, pct))
        merged_top = sorted(merged_top, key=lambda x: -x[1])[:top_n]

        merged_mentions = dict(result["response_mentions"])
        for name, mentions in kw_result["response_mentions"].items():
            if name not in merged_mentions:
                merged_mentions[name] = mentions

        result["top_concepts"] = merged_top
        result["response_mentions"] = merged_mentions
        result["mode"] = "hybrid"
    else:
        result["mode"] = "dictionary"

    result["coverage_pct"] = round(coverage_pct, 1)
    return result


def get_concept_summary_df(result: Dict) -> pd.DataFrame:
    """Convert concept analysis result ke DataFrame untuk display."""
    rows = []
    for name, count, pct in result.get("top_concepts", []):
        rows.append({
            "Konsep": name,
            "Jumlah Respons": count,
            "% Responden": pct,
        })
    return pd.DataFrame(rows)


def get_cooccurrence_df(result: Dict, top_n: int = 10) -> pd.DataFrame:
    """Convert cooccurrence data ke DataFrame untuk display."""
    coo = result.get("cooccurrence", {})
    if not coo:
        return pd.DataFrame()
    sorted_pairs = sorted(coo.items(), key=lambda x: -x[1])[:top_n]
    rows = [{"Konsep A": a, "Konsep B": b, "Bersama Muncul": cnt} for (a, b), cnt in sorted_pairs]
    return pd.DataFrame(rows)
