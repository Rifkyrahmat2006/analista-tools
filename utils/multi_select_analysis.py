"""
Multi Select Analysis Utility
Handles multiple choice / checkbox question analysis.
"""

import pandas as pd


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
