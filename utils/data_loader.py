"""
Data Loader Utility
Handles loading CSV and Excel files into pandas DataFrames.
"""

import pandas as pd
import streamlit as st
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "datasets"


def ensure_data_dir():
    """Ensure the data/datasets directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@st.cache_data
def load_csv(file) -> pd.DataFrame:
    """Load a CSV file and return a DataFrame."""
    try:
        df = pd.read_csv(file)
        return df
    except Exception as e:
        st.error(f"❌ Error loading CSV: {e}")
        return None


@st.cache_data
def load_excel(file) -> pd.DataFrame:
    """Load an Excel file and return a DataFrame."""
    try:
        df = pd.read_excel(file, engine="openpyxl")
        return df
    except Exception as e:
        st.error(f"❌ Error loading Excel: {e}")
        return None


def load_file(uploaded_file) -> pd.DataFrame:
    """
    Load a file based on its extension.
    Supports .csv, .xlsx, .xls
    """
    if uploaded_file is None:
        return None

    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):
        return load_csv(uploaded_file)
    elif filename.endswith((".xlsx", ".xls")):
        return load_excel(uploaded_file)
    else:
        st.error("❌ Format file tidak didukung. Gunakan CSV atau Excel (.xlsx/.xls).")
        return None


def save_dataset(df: pd.DataFrame, filename: str) -> str:
    """Save a DataFrame to the local datasets folder."""
    ensure_data_dir()
    filepath = DATA_DIR / filename
    if filename.endswith(".csv"):
        df.to_csv(filepath, index=False)
    elif filename.endswith((".xlsx", ".xls")):
        df.to_excel(filepath, index=False, engine="openpyxl")
    return str(filepath)


def list_saved_datasets() -> list:
    """List all saved datasets in the data directory."""
    ensure_data_dir()
    files = []
    for f in DATA_DIR.iterdir():
        if f.suffix in [".csv", ".xlsx", ".xls"]:
            files.append(f.name)
    return sorted(files)


def load_saved_dataset(filename: str) -> pd.DataFrame:
    """Load a previously saved dataset."""
    filepath = DATA_DIR / filename
    if filepath.suffix == ".csv":
        return pd.read_csv(filepath)
    elif filepath.suffix in [".xlsx", ".xls"]:
        return pd.read_excel(filepath, engine="openpyxl")
    return None
