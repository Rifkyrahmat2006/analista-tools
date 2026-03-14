"""
Question Type Detection Utility
Automatically detects the most likely question type for survey columns.

Detection Pipeline (priority order):
  1. skip         — mostly empty column
  2. scale        — numeric Likert-style values
  3. multiple_choice — delimiter-separated multi-answers
  4. open_text    — long free-text responses
  5. single_choice — categorical with limited unique values
"""

import pandas as pd
import numpy as np
from typing import Dict

DELIMITERS = [",", ";", "|", "/"]


def analyze_column_features(series: pd.Series) -> Dict[str, float]:
    """
    Compute statistical features of a column for question type detection.

    Returns a dictionary with keys:
        null_ratio, unique_ratio, delimiter_ratio,
        numeric_ratio, avg_text_length, avg_word_count
    """
    total = len(series)
    if total == 0:
        return {
            "null_ratio": 1.0,
            "unique_ratio": 0.0,
            "delimiter_ratio": 0.0,
            "numeric_ratio": 0.0,
            "avg_text_length": 0.0,
            "avg_word_count": 0.0,
        }

    null_ratio = series.isna().sum() / total

    non_null = series.dropna().astype(str)
    non_null_count = len(non_null)

    if non_null_count == 0:
        return {
            "null_ratio": null_ratio,
            "unique_ratio": 0.0,
            "delimiter_ratio": 0.0,
            "numeric_ratio": 0.0,
            "avg_text_length": 0.0,
            "avg_word_count": 0.0,
        }

    unique_count = non_null.nunique()
    unique_ratio = unique_count / non_null_count

    # Delimiter detection
    has_delimiter = non_null.apply(
        lambda x: any(d in str(x) for d in DELIMITERS)
    )
    delimiter_ratio = has_delimiter.sum() / non_null_count

    # Numeric detection
    numeric_converted = pd.to_numeric(non_null, errors="coerce")
    numeric_ratio = numeric_converted.notna().sum() / non_null_count

    # Text length metrics
    avg_text_length = non_null.str.len().mean()
    avg_word_count = non_null.str.split().apply(len).mean()

    return {
        "null_ratio": round(null_ratio, 4),
        "unique_ratio": round(unique_ratio, 4),
        "delimiter_ratio": round(delimiter_ratio, 4),
        "numeric_ratio": round(numeric_ratio, 4),
        "avg_text_length": round(avg_text_length, 2),
        "avg_word_count": round(avg_word_count, 2),
    }


def _compute_avg_delimiter_count(series: pd.Series) -> float:
    """Count average number of delimiters per non-null response."""
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return 0.0

    def count_delimiters(text: str) -> int:
        return sum(text.count(d) for d in DELIMITERS)

    return non_null.apply(count_delimiters).mean()


def _compute_avg_items_per_response(series: pd.Series) -> float:
    """
    Estimate average number of items per response by splitting on
    the most common delimiter.
    """
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return 1.0

    # Find the dominant delimiter
    best_delim = ","
    best_count = 0
    for d in DELIMITERS:
        total_count = non_null.str.count(f"\\{d}" if d in (".", "|") else d).sum()
        if total_count > best_count:
            best_count = total_count
            best_delim = d

    items_per_row = non_null.apply(
        lambda x: len([p.strip() for p in x.split(best_delim) if p.strip()])
    )
    return items_per_row.mean()


def detect_question_type(series: pd.Series) -> str:
    """
    Detect the most likely question type for a survey column.

    Returns one of:
        'skip', 'scale', 'multiple_choice', 'open_text', 'single_choice'
    """
    features = analyze_column_features(series)

    # --- STEP 1: Skip Detection ---
    if features["null_ratio"] > 0.8:
        return "skip"

    non_null = series.dropna().astype(str)
    non_null_count = len(non_null)

    if non_null_count == 0:
        return "skip"

    # --- STEP 2: Scale Detection ---
    if features["numeric_ratio"] > 0.8:
        numeric_vals = pd.to_numeric(non_null, errors="coerce").dropna()
        unique_count = numeric_vals.nunique()
        value_range = numeric_vals.max() - numeric_vals.min() if len(numeric_vals) > 0 else 0

        if unique_count <= 10 and value_range <= 20:
            return "scale"

    # --- STEP 3: Multiple Choice Detection ---
    if features["delimiter_ratio"] > 0.25:
        avg_items = _compute_avg_items_per_response(series)
        avg_delim_count = _compute_avg_delimiter_count(series)

        # Guard against false positives (e.g. "Teknik Informatika, S1")
        if avg_items >= 1.5 and avg_delim_count > 1:
            return "multiple_choice"

    # --- STEP 4: Open Text Detection ---
    if features["avg_text_length"] > 40 or features["avg_word_count"] > 8:
        return "open_text"

    # --- STEP 5: Single Choice Detection ---
    unique_count = non_null.nunique()
    if unique_count <= 30 and features["avg_text_length"] < 40:
        return "single_choice"

    # Fallback
    return "open_text"
