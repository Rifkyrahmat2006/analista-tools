"""
OE Question Profiler
====================
Mendeteksi mode analisis yang tepat berdasarkan teks pertanyaan dan karakteristik data respons.

7 Mode Analisis:
  - concept       : Pertanyaan meminta jenis/metode/pilihan (multi-label)
  - thematic      : Pertanyaan harapan/ekspektasi/opini bebas
  - reason        : Pertanyaan "mengapa" / "alasan"
  - barrier       : Pertanyaan "kendala" / "hambatan" / "masalah"
  - recommendation: Pertanyaan "saran" / "perlu ditingkatkan"
  - evaluation    : Pertanyaan "bagaimana" / "penilaian" / "evaluasi"
  - general       : Fallback — thematic analysis umum
"""

import re
from typing import Dict, List, Tuple, Optional
import pandas as pd

# ---------------------------------------------------------------------------
# MODE CONSTANTS
# ---------------------------------------------------------------------------

ANALYSIS_MODES = [
    "concept",
    "thematic",
    "reason",
    "barrier",
    "recommendation",
    "evaluation",
    "general",
]

MODE_LABELS = {
    "concept":        "Ekstraksi Konsep",
    "thematic":       "Analisis Tematik Umum",
    "reason":         "Analisis Alasan",
    "barrier":        "Analisis Hambatan",
    "recommendation": "Analisis Saran",
    "evaluation":     "Analisis Evaluasi",
    "general":        "Analisis Tematik Umum",
}

MODE_DESCRIPTIONS = {
    "concept": (
        "Pertanyaan meminta jenis, metode, pilihan, atau konsep yang dapat disebutkan. "
        "Satu respons dapat mengandung beberapa konsep — sistem akan menghitung tiap konsep secara terpisah (multi-label)."
    ),
    "thematic": (
        "Pertanyaan bersifat eksploratif: harapan, ekspektasi, opini, atau pandangan. "
        "Sistem akan mengelompokkan respons ke dalam tema-tema melalui thematic grouping."
    ),
    "reason": (
        "Pertanyaan meminta alasan atau penjelasan ('mengapa', 'apa alasan'). "
        "Sistem akan mengekstrak alasan-alasan yang disebutkan."
    ),
    "barrier": (
        "Pertanyaan meminta hambatan, kendala, atau masalah. "
        "Sistem akan mengidentifikasi dan menghitung hambatan yang disebutkan."
    ),
    "recommendation": (
        "Pertanyaan meminta saran, rekomendasi, atau hal yang perlu ditingkatkan. "
        "Sistem akan mengekstrak rekomendasi yang disebutkan."
    ),
    "evaluation": (
        "Pertanyaan meminta penilaian, evaluasi, atau pendapat mengenai aspek tertentu. "
        "Sistem akan mengelompokkan aspek-aspek yang disoroti."
    ),
    "general": (
        "Pertanyaan terbuka umum yang tidak cocok dengan mode di atas. "
        "Sistem menggunakan thematic grouping sebagai pendekatan default."
    ),
}

# ---------------------------------------------------------------------------
# SIGNAL PATTERNS
# ---------------------------------------------------------------------------

CONCEPT_PATTERNS = [
    r"\bmetode\s+apa\b",
    r"\bapa\s+saja\b.*\b(metode|cara|teknik|bidang|program|jenis|skill|kemampuan|aktivitas|kegiatan)\b",
    r"\b(metode|cara|teknik|bidang|program|jenis|skill|kemampuan)\b.*\bapa\b",
    r"\bapa\s+(yang|yg)\s+paling\s+efektif\b",
    r"\bapa\s+(yang|yg)\s+ingin\b",
    r"\bapa\s+(yang|yg)\s+paling\s+dibutuhkan\b",
    r"\bsebutkan\b.*\b(metode|cara|bidang|program|jenis|skill)\b",
    r"\b(pilih|memilih|pilihan)\b.*\bapa\b",
    r"\bapa\s+(saja\s+)?(program|kegiatan|bidang|divisi|departemen)\b",
]

CONCEPT_KEYWORDS = {
    "metode", "cara", "teknik", "bidang", "program", "jenis", "skill",
    "kemampuan", "aktivitas", "kegiatan", "divisi", "departemen", "pilihan",
    "opsi", "alternatif", "strategi", "pendekatan", "media", "platform",
    "tools", "instrumen", "alat", "fasilitas",
}

THEMATIC_PATTERNS = [
    r"\bharapan\b",
    r"\bharap(kan)?\b",
    r"\bekspektasi\b",
    r"\bimpian\b",
    r"\bcita.?cita\b",
    r"\bkeinginan\b",
    r"\bpendapat\s+(Anda|kamu|anda|mu)\b",
    r"\bopini\b",
    r"\bpandangan\b",
    r"\bpersepsi\b",
    r"\bpengalaman\b",
    r"\bceritakan\b",
    r"\bjelaskan\b",
    r"\bdeskripsikan\b",
]

THEMATIC_KEYWORDS = {
    "harapan", "ekspektasi", "impian", "cita", "keinginan", "opini",
    "pandangan", "persepsi", "pengalaman", "cerita", "kesan",
    "gambaran", "pendapat",
}

REASON_PATTERNS = [
    r"\bmengapa\b",
    r"\bkenapa\b",
    r"\bapa\s+alasan\b",
    r"\bapa\s+sebab\b",
    r"\bfaktor\s+apa\b",
    r"\bapa\s+yang\s+membuat\b",
    r"\bapa\s+yang\s+mendorong\b",
    r"\bapa\s+yang\s+memotivasi\b",
    r"\blatar\s+belakang\b",
]

REASON_KEYWORDS = {
    "alasan", "sebab", "karena", "mengapa", "kenapa", "motif",
    "motivasi", "dorongan", "faktor", "latar belakang",
}

BARRIER_PATTERNS = [
    r"\bkendala\b",
    r"\bhambatan\b",
    r"\bmasalah\b",
    r"\bkesulitan\b",
    r"\bapa\s+yang\s+(menghambat|menghalangi|menyulitkan|membuat\s+sulit)\b",
    r"\btantangan\b",
    r"\bkekurangan\b",
    r"\bpermasalahan\b",
    r"\bapa\s+keluhan\b",
]

BARRIER_KEYWORDS = {
    "kendala", "hambatan", "masalah", "kesulitan", "tantangan",
    "kekurangan", "permasalahan", "keluhan", "problem", "rintangan",
    "halangan", "penghambat", "gangguan", "keterbatasan",
}

RECOMMENDATION_PATTERNS = [
    r"\bsaran\b",
    r"\brekomendasi\b",
    r"\bapa\s+yang\s+perlu\s+(ditingkatkan|diperbaiki|dibenahi|diubah)\b",
    r"\bapa\s+yang\s+sebaiknya\s+dilakukan\b",
    r"\bmasukan\b",
    r"\bapa\s+yang\s+harus\s+(diperbaiki|ditingkatkan)\b",
    r"\bapa\s+yang\s+perlu\s+dilakukan\b",
    r"\bperlu\s+ditingkatkan\b",
    r"\bperlu\s+diperbaiki\b",
]

RECOMMENDATION_KEYWORDS = {
    "saran", "rekomendasi", "masukan", "usulan", "input", "feedback",
    "solusi", "perbaikan", "peningkatan", "benahi", "tingkatkan",
    "perbaiki", "ubah", "kembangkan",
}

EVALUATION_PATTERNS = [
    r"\bbagaimana\b.*\b(penilaian|pendapat|pandangan)\b",
    r"\bpenilaian\b",
    r"\bevaluasi\b",
    r"\bberi\s+(nilai|penilaian|rating)\b",
    r"\bseberapa\s+(baik|buruk|puas|efektif)\b",
    r"\bapa\s+yang\s+perlu\s+dievaluasi\b",
    r"\btanggapan\b",
    r"\bkomentar\b",
    r"\bulas\b",
    r"\bulasan\b",
    r"\bbagaimana\s+(menurut|pendapat)\b",
]

EVALUATION_KEYWORDS = {
    "penilaian", "evaluasi", "nilai", "tanggapan", "komentar",
    "ulasan", "review", "asesmen",
}


# ---------------------------------------------------------------------------
# CORE PROFILING FUNCTION
# ---------------------------------------------------------------------------

def profile_question(
    question_text: str,
    response_series: Optional[pd.Series] = None,
) -> Dict:
    """
    Deteksi mode analisis yang tepat untuk pertanyaan terbuka.

    Args:
        question_text: Teks pertanyaan (kolom header survei)
        response_series: Opsional — data respons untuk sinyal statistik tambahan

    Returns:
        {
            "detected_mode": str,
            "confidence": float,
            "reasoning": str,
            "signals": dict,
            "all_scores": dict,
        }
    """
    q = question_text.lower().strip() if question_text else ""
    signals = _extract_signals(q, response_series)
    scores = _compute_mode_scores(q, signals)

    detected_mode = max(scores, key=scores.get)
    top_score = scores[detected_mode]

    sorted_scores = sorted(scores.values(), reverse=True)
    second = sorted_scores[1] if len(sorted_scores) > 1 else 0
    if top_score + second > 0:
        confidence = top_score / (top_score + second)
    else:
        confidence = 0.5

    confidence = round(min(1.0, max(0.0, confidence)), 2)
    reasoning = _build_reasoning(detected_mode, signals, scores)

    return {
        "detected_mode": detected_mode,
        "confidence": confidence,
        "reasoning": reasoning,
        "signals": signals,
        "all_scores": scores,
    }


# ---------------------------------------------------------------------------
# SIGNAL EXTRACTION
# ---------------------------------------------------------------------------

def _extract_signals(question_lower: str, response_series: Optional[pd.Series]) -> Dict:
    signals = {}

    signals["has_concept_pattern"] = _match_patterns(question_lower, CONCEPT_PATTERNS)
    signals["has_thematic_pattern"] = _match_patterns(question_lower, THEMATIC_PATTERNS)
    signals["has_reason_pattern"] = _match_patterns(question_lower, REASON_PATTERNS)
    signals["has_barrier_pattern"] = _match_patterns(question_lower, BARRIER_PATTERNS)
    signals["has_recommendation_pattern"] = _match_patterns(question_lower, RECOMMENDATION_PATTERNS)
    signals["has_evaluation_pattern"] = _match_patterns(question_lower, EVALUATION_PATTERNS)

    signals["has_concept_keyword"] = _keyword_hit_count(question_lower, CONCEPT_KEYWORDS)
    signals["has_thematic_keyword"] = _keyword_hit_count(question_lower, THEMATIC_KEYWORDS)
    signals["has_reason_keyword"] = _keyword_hit_count(question_lower, REASON_KEYWORDS)
    signals["has_barrier_keyword"] = _keyword_hit_count(question_lower, BARRIER_KEYWORDS)
    signals["has_recommendation_keyword"] = _keyword_hit_count(question_lower, RECOMMENDATION_KEYWORDS)
    signals["has_evaluation_keyword"] = _keyword_hit_count(question_lower, EVALUATION_KEYWORDS)

    signals["has_superlative_option"] = bool(re.search(
        r"\bpaling\s+(efektif|cocok|baik|tepat|berguna|bermanfaat|dibutuhkan|dipilih)\b",
        question_lower
    ))
    signals["has_apa_saja"] = bool(re.search(r"\bapa\s+saja\b", question_lower))
    
    # Detect controlled concept clues: "(misal...", "(contoh...", or explicit list of options
    signals["has_clue_options"] = bool(re.search(
        r"\(misal|\(contoh|misalnya\s|contohnya\s|seperti\s", 
        question_lower
    ))

    if response_series is not None:
        non_null = response_series.dropna().astype(str)
        non_null = non_null[non_null.str.strip() != ""]
        if len(non_null) > 0:
            def count_items(text: str) -> int:
                parts = re.split(r"[,;/]|\bdan\b|\bserta\b|\bmaupun\b", text)
                return len([p.strip() for p in parts if p.strip()])
            avg_items = non_null.apply(count_items).mean()
            signals["avg_items_per_response"] = round(avg_items, 2)
            signals["avg_response_length"] = round(non_null.str.len().mean(), 1)
            signals["avg_word_count"] = round(non_null.str.split().apply(len).mean(), 1)
        else:
            signals["avg_items_per_response"] = 1.0
            signals["avg_response_length"] = 0.0
            signals["avg_word_count"] = 0.0
    else:
        signals["avg_items_per_response"] = 1.0
        signals["avg_response_length"] = 0.0
        signals["avg_word_count"] = 0.0

    return signals


def _match_patterns(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _keyword_hit_count(text: str, keywords: set) -> int:
    count = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            count += 1
    return count


# ---------------------------------------------------------------------------
# MODE SCORING
# ---------------------------------------------------------------------------

def _compute_mode_scores(question_lower: str, signals: Dict) -> Dict[str, float]:
    scores = {m: 0.0 for m in ANALYSIS_MODES}

    # REASON (Prioritas Tinggi jika intent jelas)
    if signals["has_reason_pattern"]:
        scores["reason"] += 6.0
    scores["reason"] += signals["has_reason_keyword"] * 2.0

    # BARRIER (Prioritas Tinggi jika intent jelas)
    if signals["has_barrier_pattern"]:
        scores["barrier"] += 6.0
    scores["barrier"] += signals["has_barrier_keyword"] * 2.0

    # RECOMMENDATION (Prioritas Tinggi jika intent jelas)
    if signals["has_recommendation_pattern"]:
        scores["recommendation"] += 6.0
    scores["recommendation"] += signals["has_recommendation_keyword"] * 2.0

    # EVALUATION
    if signals["has_evaluation_pattern"]:
        scores["evaluation"] += 5.0
    scores["evaluation"] += signals["has_evaluation_keyword"] * 1.5

    # THEMATIC (Harapan, Opini)
    if signals["has_thematic_pattern"]:
        scores["thematic"] += 5.0
    scores["thematic"] += signals["has_thematic_keyword"] * 2.0
    
    avg_len = signals["avg_response_length"]
    avg_wc = signals["avg_word_count"]
    if avg_len > 60:
        scores["thematic"] += 1.0

    # CONCEPT
    # Concept is now weaker unless there is explicit clue or specific pattern
    if signals["has_concept_pattern"]:
        scores["concept"] += 3.0
    scores["concept"] += signals["has_concept_keyword"] * 1.0
    if signals["has_superlative_option"]:
        scores["concept"] += 1.5
        
    # 'apa saja' only slightly boosts Concept, not strongly
    if signals["has_apa_saja"]:
        scores["concept"] += 0.5
        
    # Strong signal for Concept if there's a clue option list
    if signals["has_clue_options"]:
        scores["concept"] += 4.0
        
    avg_items = signals["avg_items_per_response"]
    if avg_items >= 1.5:
        scores["concept"] += 1.0

    # GENERAL (baseline fallback)
    scores["general"] = 0.5

    # Dampen concept if a stronger specific mode wins (Hierarchical)
    max_exploratory_score = max([scores["reason"], scores["barrier"], scores["recommendation"], scores["thematic"]])
    if max_exploratory_score > 3.0 and not signals["has_clue_options"]:
        scores["concept"] *= 0.2

    return scores


# ---------------------------------------------------------------------------
# REASONING BUILDER
# ---------------------------------------------------------------------------

def _build_reasoning(mode: str, signals: Dict, scores: Dict[str, float]) -> str:
    lines = []
    mode_label = MODE_LABELS.get(mode, mode)
    lines.append(f"Mode terdeteksi: **{mode_label}**\n")

    if mode == "concept":
        reasons = []
        if signals["has_clue_options"]:
            reasons.append("ditemukan daftar opsi/contoh (clue eksplisit) dalam pertanyaan")
        if signals["has_concept_pattern"]:
            reasons.append("pertanyaan menanyakan metode, cara, atau bidang secara spesifik")
        if signals["has_superlative_option"]:
            reasons.append("terdapat frasa 'paling efektif/cocok/baik'")
        if signals["avg_items_per_response"] >= 1.5:
            reasons.append(f"rata-rata {signals['avg_items_per_response']:.1f} item per respons")
        if signals.get("has_apa_saja"):
            reasons.append("terdapat frasa 'apa saja' (kemungkinan multi-item)")
        lines.append("Alasan: " + ("; ".join(reasons) if reasons else "sinyal konsep terdeteksi."))
        lines.append("\n→ Pertanyaan ini meminta daftar item teridentifikasi (Controlled Concept).")

    elif mode == "thematic":
        reasons = []
        if signals["has_thematic_pattern"]:
            reasons.append("pertanyaan mengeksplorasi harapan, ekspektasi, atau opini secara bebas")
        if signals["has_thematic_keyword"] > 0:
            reasons.append("mengandung kata kunci tematik utama")
        lines.append("Alasan: " + ("; ".join(reasons) if reasons else "sinyal eksploratif tematik terdeteksi."))
        lines.append("\n→ Respons bebas akan dikelompokkan ke dalam tema utama (Exploratory).")

    elif mode == "reason":
        lines.append("Alasan: Ditemukan sinyal kuat yang menanyakan alasan, motif, atau penyebab ('mengapa/kenapa').")
        lines.append("\n→ Output difokuskan pada ekstraksi tema alasan.")

    elif mode == "barrier":
        lines.append("Alasan: Ditemukan konsep atau kata kunci hambatan, masalah, atau kendala.")
        lines.append("\n→ Output difokuskan pada pengelompokan tematik hambatan.")

    elif mode == "recommendation":
        lines.append("Alasan: Ditemukan sinyal kuat yang meminta saran, masukan, atau rekomendasi perbaikan.")
        lines.append("\n→ Output difokuskan pada pengelompokan tematik saran.")

    elif mode == "evaluation":
        lines.append("Alasan: Ditemukan sinyal kuat yang meminta penilaian, evaluasi, atau review.")
        lines.append("\n→ Output difokuskan pada tema evaluasi respons.")

    else:
        lines.append("Alasan: Tidak ditemukan intent spesifik. Menggunakan analisis tematik umum.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def get_mode_info(mode: str) -> Dict[str, str]:
    return {
        "mode": mode,
        "label": MODE_LABELS.get(mode, mode),
        "description": MODE_DESCRIPTIONS.get(mode, ""),
    }


def get_all_modes_for_selectbox() -> List[Tuple[str, str]]:
    return [(m, MODE_LABELS[m]) for m in ANALYSIS_MODES]
