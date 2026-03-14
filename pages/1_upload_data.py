import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_loader import load_file, save_dataset, list_saved_datasets, load_saved_dataset
from utils.theme import init_theme, render_theme_toggle, inject_theme_css

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")

init_theme()
render_theme_toggle()
inject_theme_css()

st.markdown("# 📤 Upload Data")
st.markdown("Upload dataset survei dari file **CSV** atau **Excel** (.xlsx/.xls)")

# --------------- Upload Section ---------------
tab_upload, tab_saved = st.tabs(["📁 Upload Baru", "💾 Dataset Tersimpan"])

with tab_upload:
    uploaded_file = st.file_uploader(
        "Pilih file CSV atau Excel",
        type=["csv", "xlsx", "xls"],
        help="Mendukung file dari Google Form export, CSV, atau Excel",
    )

    if uploaded_file is not None:
        df = load_file(uploaded_file)

        if df is not None:
            st.session_state.df = df
            st.session_state.dataset_name = uploaded_file.name

            st.success(f"✅ File **{uploaded_file.name}** berhasil dimuat!")

            # Statistics cards
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{df.shape[0]}</div>
                    <div class="stat-label">Total Baris</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{df.shape[1]}</div>
                    <div class="stat-label">Total Kolom</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                null_count = int(df.isnull().sum().sum())
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{null_count}</div>
                    <div class="stat-label">Nilai Kosong</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                dup_count = int(df.duplicated().sum())
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{dup_count}</div>
                    <div class="stat-label">Baris Duplikat</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("")

            # Preview
            st.markdown("### 👀 Preview Dataset")

            col_search, col_rows = st.columns([3, 1])
            with col_search:
                search_col = st.multiselect(
                    "Pilih kolom untuk ditampilkan",
                    options=df.columns.tolist(),
                    default=df.columns.tolist(),
                )
            with col_rows:
                n_rows = st.number_input("Jumlah baris", min_value=5, max_value=len(df), value=min(50, len(df)))

            if search_col:
                st.dataframe(df[search_col].head(n_rows), use_container_width=True, height=400)
            else:
                st.dataframe(df.head(n_rows), use_container_width=True, height=400)

            # Column info
            with st.expander("ℹ️ Informasi Kolom", expanded=False):
                col_info = pd.DataFrame({
                    "Tipe Data": df.dtypes.astype(str),
                    "Non-Null": df.count(),
                    "Null": df.isnull().sum(),
                    "Unique": df.nunique(),
                }).reset_index()
                col_info.columns = ["Kolom", "Tipe Data", "Non-Null", "Null", "Unique"]
                st.dataframe(col_info, use_container_width=True, hide_index=True)

            # Save dataset
            st.markdown("---")
            st.markdown("### 💾 Simpan Dataset")
            save_name = st.text_input("Nama file untuk disimpan", value=uploaded_file.name)
            if st.button("💾 Simpan ke Lokal", type="primary"):
                path = save_dataset(df, save_name)
                st.success(f"✅ Dataset disimpan di: `{path}`")

with tab_saved:
    saved_files = list_saved_datasets()
    if saved_files:
        selected_file = st.selectbox("Pilih dataset tersimpan", saved_files)
        if st.button("📂 Muat Dataset", type="primary"):
            df = load_saved_dataset(selected_file)
            if df is not None:
                st.session_state.df = df
                st.session_state.dataset_name = selected_file
                st.success(f"✅ Dataset **{selected_file}** dimuat!")
                st.dataframe(df.head(50), use_container_width=True, height=400)
    else:
        st.info("📭 Belum ada dataset tersimpan. Upload data terlebih dahulu.")

# Sidebar status
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
    else:
        st.info("📤 Belum ada dataset.")
