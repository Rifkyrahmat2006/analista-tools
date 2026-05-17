"""
Data Cleaning Utility
Provides functions for cleaning and transforming survey data.
"""

import pandas as pd


def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["object"]).columns:
        df_clean[col] = df_clean[col].str.strip()
    return df_clean


def lowercase_normalize(df: pd.DataFrame, columns: list = None) -> pd.DataFrame:
    """Convert string columns to lowercase."""
    df_clean = df.copy()
    if columns is None:
        columns = df_clean.select_dtypes(include=["object"]).columns.tolist()
    for col in columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].str.lower()
    return df_clean


def remove_null_rows(df: pd.DataFrame, subset: list = None) -> pd.DataFrame:
    """Remove rows with null values."""
    return df.dropna(subset=subset).reset_index(drop=True)


def remove_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate rows."""
    return df.drop_duplicates().reset_index(drop=True)


def replace_values(df: pd.DataFrame, column: str, old_value: str, new_value: str) -> pd.DataFrame:
    """Replace specific values in a column.

    Tries to cast old_value and new_value to the column's dtype so that
    numeric columns are matched correctly (e.g. int 1 ≠ str '1').
    Falls back to string replacement if casting fails.
    """
    df_clean = df.copy()
    col_dtype = df_clean[column].dtype

    def _cast(val, dtype):
        try:
            if pd.api.types.is_integer_dtype(dtype):
                return int(float(val))
            elif pd.api.types.is_float_dtype(dtype):
                return float(val)
        except (ValueError, TypeError):
            pass
        return val

    old_cast = _cast(old_value, col_dtype)
    new_cast = _cast(new_value, col_dtype)

    # Replace typed value; also try raw string fallback so object columns work
    df_clean[column] = df_clean[column].replace(old_cast, new_cast)
    if old_cast != old_value:
        df_clean[column] = df_clean[column].replace(old_value, new_cast)

    return df_clean


def rename_column(df: pd.DataFrame, old_name: str, new_name: str) -> pd.DataFrame:
    """Rename a column."""
    return df.rename(columns={old_name: new_name})


def drop_columns(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Drop specified columns."""
    return df.drop(columns=columns, errors="ignore")


def fill_null_values(df: pd.DataFrame, column: str, fill_value) -> pd.DataFrame:
    """Fill null values in a column with a specified value."""
    df_clean = df.copy()
    df_clean[column] = df_clean[column].fillna(fill_value)
    return df_clean


def get_data_summary(df: pd.DataFrame) -> dict:
    """Get a summary of the DataFrame for display."""
    return {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "null_counts": df.isnull().sum().to_dict(),
        "total_nulls": int(df.isnull().sum().sum()),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
    }
