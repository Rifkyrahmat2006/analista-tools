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


def extract_lainnya(df: pd.DataFrame, column: str, delimiter: str = ",") -> pd.DataFrame:
    """
    Extracts 'Lainnya: [text]' or 'Other: [text]' from a multiselect column into a new column.
    The original column will have the text replaced with just 'Lainnya'.
    Returns a new DataFrame with the added column.
    """
    df_clean = df.copy()
    if column not in df_clean.columns:
        return df_clean
        
    lainnya_col_name = f"{column}_lainnya_text"
    
    # We will use regex to find 'Lainnya: ' or 'Other: ' followed by any text,
    # capture that text, and replace the whole thing in the original string with 'Lainnya'
    
    import re
    
    def process_row(val):
        if not isinstance(val, str):
            return val, None
            
        items = [item.strip() for item in val.split(delimiter) if item.strip()]
        new_items = []
        lainnya_texts = []
        
        for item in items:
            # Match "Lainnya: something" or "Other: something" (case insensitive)
            match = re.match(r"^(?i)(lainnya|other)\s*:\s*(.*)$", item)
            if match:
                new_items.append("Lainnya")
                lainnya_text = match.group(2).strip()
                if lainnya_text:
                    lainnya_texts.append(lainnya_text)
            else:
                new_items.append(item)
                
        new_val = f"{delimiter} ".join(new_items)
        lainnya_val = " | ".join(lainnya_texts) if lainnya_texts else None
        
        return new_val, lainnya_val

    # Apply to series
    results = df_clean[column].apply(process_row)
    df_clean[column] = results.apply(lambda x: x[0])
    
    # Only add the new column if there were any 'Lainnya' texts found
    lainnya_series = results.apply(lambda x: x[1])
    if lainnya_series.notna().any():
        # Insert right after the original column
        col_idx = df_clean.columns.get_loc(column) + 1
        df_clean.insert(col_idx, lainnya_col_name, lainnya_series)
        
    return df_clean


import re as _re

def _normalize_other(val: str) -> str:
    """
    Normalize Google Forms free-text "Other:" / "Lainnya:" responses to the
    literal string "Other" so they consolidate as one group.
    E.g. "Other: bla bla" → "Other"
         "Lainnya: xyz"   → "Other"
    """
    m = _re.match(r"^(?:lainnya|other)\s*:\s*.*$", val.strip(), flags=_re.IGNORECASE)
    return "Other" if m else val


def multi_choice_analysis(df: pd.DataFrame, column: str, delimiter: str = ",", main_options: list = None) -> pd.DataFrame:
    """
    Analyze a multiple choice column.
    Pipeline: split → normalize Others → explode → count frequency
    If main_options is provided, responses not in main_options are grouped as 'Other'.
    Returns a DataFrame with columns: [Value, Count, Percentage]
    """
    exploded = split_and_explode(df, column, delimiter)

    # Always normalize "Other: ..." / "Lainnya: ..." patterns first
    exploded = exploded.apply(_normalize_other)

    if main_options is not None:
        # Normalize main_options entries too (in case they contain "Other: ..." labels)
        normalized_main = {_normalize_other(o) for o in main_options}
        exploded = exploded.apply(lambda x: x if x in normalized_main else "Other")

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
    
    main_options_series = counts[counts >= threshold]
    other_options = counts[counts < threshold]
    
    return {
        "all": counts.index.tolist(),
        "counts": counts.to_dict(),
        "main": [(k, v) for k, v in main_options_series.items()],
        "main_names": main_options_series.index.tolist(),
        "other": other_options.index.tolist(),
        "other_count": len(other_options)
    }

