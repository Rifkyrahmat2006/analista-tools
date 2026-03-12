"""
Pivot Analysis Utility
Handles single choice and scale analysis.
"""

import pandas as pd


def single_choice_analysis(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Analyze a single choice column using value_counts.
    Returns a DataFrame with columns: [Value, Count, Percentage]
    """
    counts = df[column].value_counts().reset_index()
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
