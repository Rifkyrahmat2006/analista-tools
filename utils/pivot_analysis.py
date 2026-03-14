"""
Pivot Analysis Utility
Handles single choice and scale analysis.
"""

import pandas as pd
import streamlit as st


def single_choice_analysis(df: pd.DataFrame, column: str, main_options: list = None) -> pd.DataFrame:
    """
    Analyze a single choice column using value_counts.
    If main_options is provided, responses not in main_options are grouped as 'Other'.
    Returns a DataFrame with columns: [Value, Count, Percentage]
    """
    series = df[column]
    if main_options is not None:
        series = series.apply(lambda x: x if x in main_options else "Other")
        
    counts = series.value_counts().reset_index()
    counts.columns = ["Value", "Count"]
    total = counts["Count"].sum()
    counts["Percentage"] = (counts["Count"] / total * 100).round(2)
    return counts


def scale_analysis(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Analyze a scale/Likert column using value_counts sorted by index.
    Returns a DataFrame with columns: [Scale, Count, Percentage]
    """
    counts = df[column].value_counts().sort_index().reset_index()
    counts.columns = ["Scale", "Count"]
    total = counts["Count"].sum()
    counts["Percentage"] = (counts["Count"] / total * 100).round(2)
    return counts


def scale_statistics(df: pd.DataFrame, column: str) -> dict:
    """
    Calculate basic statistics for a scale column.
    """
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    return {
        "mean": round(series.mean(), 2),
        "median": round(series.median(), 2),
        "mode": series.mode().tolist(),
        "std": round(series.std(), 2),
        "min": series.min(),
        "max": series.max(),
        "count": int(series.count()),
    }


def cross_tabulation(df: pd.DataFrame, col1: str, col2: str) -> pd.DataFrame:
    """
    Create a cross-tabulation between two columns.
    """
    return pd.crosstab(df[col1], df[col2], margins=True, margins_name="Total")


@st.cache_data(show_spinner=False)
def get_single_choice_preview(series: pd.Series) -> dict:
    """
    Extract answer options, count them, and group rare answers into 'Other'.
    Cached for performance on large datasets.
    """
    counts = series.dropna().astype(str).str.strip().value_counts()
    
    # Remove empty strings if any
    if "" in counts.index:
        counts = counts.drop("")
        
    total_responses = counts.sum()
    
    if total_responses == 0:
        return {"main": [], "other": [], "other_count": 0}
        
    threshold = max(3, total_responses * 0.02)
    
    main_options_series = counts[counts >= threshold]
    other_options = counts[counts < threshold]
    
    return {
        "all": counts.index.tolist(),
        "main": [(k, v) for k, v in main_options_series.items()],
        "main_names": main_options_series.index.tolist(),
        "other": other_options.index.tolist(),
        "other_count": len(other_options)
    }

