"""
Multi Select Analysis Utility
Handles multiple choice / checkbox question analysis.
"""

import pandas as pd
import streamlit as st


def split_and_explode(df: pd.DataFrame, column: str, delimiter: str = ",") -> pd.Series:
    """
    Split comma-separated values and explode into individual rows.
    Returns a cleaned Series with individual values.
    """
    series = df[column].dropna().astype(str)
    exploded = series.str.split(delimiter).explode()
    exploded = exploded.str.strip()
    exploded = exploded[exploded != ""]
    return exploded


def multi_choice_analysis(df: pd.DataFrame, column: str, delimiter: str = ",") -> pd.DataFrame:
    """
    Analyze a multiple choice column.
    Pipeline: split → explode → count frequency
    Returns a DataFrame with columns: [Value, Count, Percentage]
    """
    exploded = split_and_explode(df, column, delimiter)
    counts = exploded.value_counts().reset_index()
    counts.columns = ["Value", "Count"]
    total_responses = df[column].dropna().shape[0]
    counts["Percentage"] = (counts["Count"] / total_responses * 100).round(2)
    return counts


def multi_choice_combinations(df: pd.DataFrame, column: str, delimiter: str = ",", top_n: int = 10) -> pd.DataFrame:
    """
    Analyze the most common combinations of multi-choice answers.
    """
    series = df[column].dropna().astype(str)
    # Normalize: sort items within each response
    normalized = series.apply(
        lambda x: ", ".join(sorted([item.strip() for item in x.split(delimiter) if item.strip()]))
    )
    counts = normalized.value_counts().head(top_n).reset_index()
    counts.columns = ["Combination", "Count"]
    return counts


@st.cache_data(show_spinner=False)
def get_multiple_choice_preview(series: pd.Series, delimiter: str = ",") -> dict:
    """
    Extract answer options, count them, and group rare answers into 'Other'.
    Cached for performance on large datasets.
    """
    exploded = series.dropna().astype(str).str.split(delimiter).explode()
    exploded = exploded.str.strip()
    exploded = exploded[exploded != ""]
    
    counts = exploded.value_counts()
    total_responses = len(exploded)
    
    if total_responses == 0:
        return {"main": [], "other": [], "other_count": 0}
        
    threshold = max(3, total_responses * 0.02)
    
    main_options = counts[counts >= threshold]
    other_options = counts[counts < threshold]
    
    return {
        "main": [(k, v) for k, v in main_options.items()],
        "other": other_options.index.tolist(),
        "other_count": len(other_options)
    }

