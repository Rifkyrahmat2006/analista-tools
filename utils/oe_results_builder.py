"""
OE Results Builder
==================
Standarisasi output antar mode analisis pertanyaan terbuka.

Semua mode mengembalikan format yang sama (standar result dict),
sehingga UI dapat merender hasil dengan cara yang konsisten
tanpa perlu tahu detail implementasi tiap mode.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
from utils.oe_question_profiler import MODE_LABELS


# ---------------------------------------------------------------------------
# RESULT ITEM LABELS PER MODE
# ---------------------------------------------------------------------------

MODE_RESULT_LABELS = {
    "concept":        "Konsep",
    "thematic":       "Tema",
    "reason":         "Alasan",
    "barrier":        "Hambatan",
    "recommendation": "Rekomendasi",
    "evaluation":     "Aspek",
    "general":        "Tema",
}

MODE_TOP_LABELS = {
    "concept":        "Top Concepts",
    "thematic":       "Top Themes",
    "reason":         "Top Reasons",
    "barrier":        "Top Barriers",
    "recommendation": "Top Recommendations",
    "evaluation":     "Top Aspects",
    "general":        "Top Themes",
}

# ---------------------------------------------------------------------------
# NARRATIVE TEMPLATES (mode-aware)
# ---------------------------------------------------------------------------

def _build_narrative(mode: str, top_items: List[Tuple], total_valid: int, question_col: str = "") -> str:
    """
    Buat narasi deskriptif berdasarkan mode dan top items.
    Pure Python template — tanpa AI/LLM.
    """
    if not top_items:
        return "Tidak ada data yang cukup untuk menghasilkan narasi."

    question_label = f'"{question_col}"' if question_col else "pertanyaan ini"

    top1_name, top1_count, top1_pct = top_items[0]

    if mode == "concept":
        narasi = (
            f"Berdasarkan hasil analisis respons terhadap {question_label}, "
            f"konsep yang paling banyak disebut adalah **{top1_name}** "
            f"sebanyak **{top1_count} respons** ({top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += (
                f", diikuti oleh **{top2_name}** sebanyak **{top2_count} respons** ({top2_pct:.1f}%)"
            )
        if len(top_items) > 2:
            top3_name, top3_count, top3_pct = top_items[2]
            narasi += (
                f" dan **{top3_name}** sebanyak **{top3_count} respons** ({top3_pct:.1f}%)"
            )
        narasi += ". "
        narasi += (
            "Perlu dicatat bahwa total persentase dapat melebihi 100% karena satu responden "
            "dapat menyebut lebih dari satu konsep."
        )

    elif mode == "thematic":
        narasi = (
            f"Berdasarkan hasil pengelompokan respons terhadap {question_label}, "
            f"tema **{top1_name}** menjadi tema dengan frekuensi tertinggi, "
            f"yaitu sebanyak **{top1_count} respons** ({top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f". Selanjutnya, tema **{top2_name}** ditemukan pada **{top2_count} respons** ({top2_pct:.1f}%)"
        if len(top_items) > 2:
            top3_name = top_items[2][0]
            narasi += (
                f". Secara umum, hasil analisis menunjukkan bahwa respons banyak menyoroti "
                f"aspek **{top1_name}**, **{top2_name}**, dan **{top3_name}**"
            )
        narasi += "."

    elif mode == "reason":
        narasi = (
            f"Berdasarkan hasil analisis terhadap {question_label}, "
            f"alasan yang paling banyak muncul adalah **{top1_name}** "
            f"sebanyak **{top1_count} respons** ({top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f", diikuti oleh **{top2_name}** ({top2_count} respons, {top2_pct:.1f}%)"
        narasi += "."

    elif mode == "barrier":
        narasi = (
            f"Berdasarkan hasil analisis terhadap {question_label}, "
            f"hambatan yang paling banyak disebut adalah **{top1_name}** "
            f"sebanyak **{top1_count} respons** ({top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f", diikuti oleh **{top2_name}** ({top2_count} respons, {top2_pct:.1f}%)"
        narasi += "."

    elif mode == "recommendation":
        narasi = (
            f"Berdasarkan hasil analisis terhadap {question_label}, "
            f"rekomendasi yang paling banyak muncul berkaitan dengan **{top1_name}** "
            f"({top1_count} respons, {top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f", diikuti **{top2_name}** ({top2_count} respons, {top2_pct:.1f}%)"
        narasi += "."

    elif mode == "evaluation":
        narasi = (
            f"Berdasarkan hasil analisis terhadap {question_label}, "
            f"aspek yang paling banyak disoroti adalah **{top1_name}** "
            f"({top1_count} respons, {top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f", diikuti **{top2_name}** ({top2_count} respons, {top2_pct:.1f}%)"
        narasi += "."

    else:  # general
        narasi = (
            f"Berdasarkan hasil pengelompokan respons terhadap {question_label}, "
            f"tema **{top1_name}** merupakan tema yang paling sering muncul "
            f"({top1_count} respons, {top1_pct:.1f}%)"
        )
        if len(top_items) > 1:
            top2_name, top2_count, top2_pct = top_items[1]
            narasi += f", diikuti **{top2_name}** ({top2_count} respons, {top2_pct:.1f}%)"
        narasi += "."

    return narasi


# ---------------------------------------------------------------------------
# RESULT BUILDER — Concept Mode
# ---------------------------------------------------------------------------

def build_concept_result(
    concept_analysis_result: Dict,
    word_cloud_text: str = "",
    top_keywords: Optional[List[Tuple]] = None,
    question_col: str = "",
) -> Dict:
    """
    Build standardized result from concept analysis output.
    """
    top_items = concept_analysis_result.get("top_concepts", [])[:10]
    total_valid = concept_analysis_result.get("total_valid", 0)

    narrative = _build_narrative("concept", top_items, total_valid, question_col)

    return {
        "mode": "concept",
        "top_label": MODE_TOP_LABELS["concept"],
        "item_label": MODE_RESULT_LABELS["concept"],
        "top_items": top_items,           # [(name, count, pct), ...]
        "top3": top_items[:3],
        "total_valid": total_valid,
        "word_cloud_text": word_cloud_text,
        "top_keywords": top_keywords or [],
        "narrative": narrative,
        "detail": concept_analysis_result,  # raw for advanced view
        "coverage_pct": concept_analysis_result.get("coverage_pct", 0.0),
    }


# ---------------------------------------------------------------------------
# RESULT BUILDER — Thematic / General / Evaluation Mode
# ---------------------------------------------------------------------------

def build_thematic_result(
    theme_summary_df: Optional[pd.DataFrame],
    validated_groups: Optional[Dict],
    word_cloud_text: str = "",
    top_keywords: Optional[List[Tuple]] = None,
    question_col: str = "",
    mode: str = "thematic",
) -> Dict:
    """
    Build standardized result from thematic analysis output.
    Works for: thematic, evaluation, general modes.
    """
    top_items = []
    total_valid = 0

    if theme_summary_df is not None and not theme_summary_df.empty:
        for _, row in theme_summary_df.iterrows():
            name = row.get("Tema", str(row.iloc[0]))
            count = int(row.get("Jumlah", row.get("Count", 0)))
            pct = float(row.get("Persentase", row.get("Percentage", 0.0)))
            top_items.append((name, count, pct))
        if top_items:
            total_valid = max(t[1] for t in top_items)

    narrative = _build_narrative(mode, top_items[:10], total_valid, question_col)

    return {
        "mode": mode,
        "top_label": MODE_TOP_LABELS.get(mode, "Top Themes"),
        "item_label": MODE_RESULT_LABELS.get(mode, "Tema"),
        "top_items": top_items[:10],
        "top3": top_items[:3],
        "total_valid": total_valid,
        "word_cloud_text": word_cloud_text,
        "top_keywords": top_keywords or [],
        "narrative": narrative,
        "detail": {"groups": validated_groups or {}},
        "coverage_pct": 100.0,
    }


# ---------------------------------------------------------------------------
# RESULT BUILDER — Multi-label modes (reason, barrier, recommendation)
# ---------------------------------------------------------------------------

def build_multilabel_result(
    concept_analysis_result: Dict,
    word_cloud_text: str = "",
    top_keywords: Optional[List[Tuple]] = None,
    question_col: str = "",
    mode: str = "reason",
) -> Dict:
    """
    Build standardized result for reason/barrier/recommendation modes.
    Uses same multi-label extraction as concept mode.
    """
    top_items = concept_analysis_result.get("top_concepts", [])[:10]
    total_valid = concept_analysis_result.get("total_valid", 0)

    narrative = _build_narrative(mode, top_items, total_valid, question_col)

    return {
        "mode": mode,
        "top_label": MODE_TOP_LABELS.get(mode, "Top Items"),
        "item_label": MODE_RESULT_LABELS.get(mode, "Item"),
        "top_items": top_items,
        "top3": top_items[:3],
        "total_valid": total_valid,
        "word_cloud_text": word_cloud_text,
        "top_keywords": top_keywords or [],
        "narrative": narrative,
        "detail": concept_analysis_result,
        "coverage_pct": concept_analysis_result.get("coverage_pct", 0.0),
    }


# ---------------------------------------------------------------------------
# SUMMARY DF (for display/export)
# ---------------------------------------------------------------------------

def result_to_summary_df(result: Dict) -> pd.DataFrame:
    """Convert standardized result to summary DataFrame."""
    item_label = result.get("item_label", "Item")
    rows = []
    for name, count, pct in result.get("top_items", []):
        rows.append({
            item_label: name,
            "Jumlah Respons": count,
            "% Responden": pct,
        })
    return pd.DataFrame(rows)
