import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_cleaning import (
    strip_whitespace,
    lowercase_normalize,
    remove_null_rows,
    remove_duplicate_rows,
    replace_values,
    rename_column,
    drop_columns,
    fill_null_values,
    get_data_summary,
)

st.set_page_config(page_title="Data Cleaning", page_icon="🧹", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .clean-stat {
        background: linear-gradient(145deg, #1e1e2e, #2a2a3e);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .clean-stat-val { font-size: 1.5rem; font-weight: 700; color: #667eea; }
    .clean-stat-lbl { font-size: 0.8rem; color: #9a9ab0; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🧹 Data Cleaning")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu di halaman **📤 Upload Data**.")
    st.stop()

df = st.session_state.df.copy()

# --------------- Data Summary ---------------
summary = get_data_summary(df)

col1, col2, col3, col4 = st.columns(4)
for col, (label, value) in zip(
    [col1, col2, col3, col4],
    [
        ("Total Baris", summary["total_rows"]),
        ("Total Kolom", summary["total_columns"]),
        ("Total Null", summary["total_nulls"]),
        ("Baris Duplikat", summary["duplicate_rows"]),
    ],
):
    with col:
        st.markdown(f"""
        <div class="clean-stat">
            <div class="clean-stat-val">{value}</div>
            <div class="clean-stat-lbl">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")

# --------------- Cleaning Operations ---------------
tab_quick, tab_replace, tab_columns, tab_editor = st.tabs([
    "⚡ Quick Clean", "🔄 Replace Values", "📝 Kelola Kolom", "✏️ Edit Data"
])

with tab_quick:
    st.markdown("### Operasi Pembersihan Cepat")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("🔤 Strip Whitespace", use_container_width=True, help="Hapus spasi di awal dan akhir teks"):
            df = strip_whitespace(df)
            st.session_state.df = df
            st.success("✅ Whitespace dihapus!")
            st.rerun()

        if st.button("🗑️ Hapus Baris Null", use_container_width=True, help="Hapus baris yang memiliki nilai kosong"):
            before = len(df)
            df = remove_null_rows(df)
            st.session_state.df = df
            removed = before - len(df)
            st.success(f"✅ {removed} baris null dihapus!")
            st.rerun()

    with col_b:
        if st.button("🔡 Lowercase Semua Teks", use_container_width=True, help="Ubah semua teks menjadi huruf kecil"):
            df = lowercase_normalize(df)
            st.session_state.df = df
            st.success("✅ Teks dinormalisasi ke lowercase!")
            st.rerun()

        if st.button("🚫 Hapus Duplikat", use_container_width=True, help="Hapus baris yang sama persis"):
            before = len(df)
            df = remove_duplicate_rows(df)
            st.session_state.df = df
            removed = before - len(df)
            st.success(f"✅ {removed} baris duplikat dihapus!")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Hapus Null per Kolom")
    null_cols = [col for col in df.columns if df[col].isnull().sum() > 0]
    if null_cols:
        selected_null_col = st.selectbox("Pilih kolom", null_cols, key="null_col")
        null_action = st.radio(
            "Tindakan",
            ["Hapus baris dengan null", "Isi dengan nilai tertentu"],
            key="null_action",
            horizontal=True,
        )

        if null_action == "Hapus baris dengan null":
            if st.button("Jalankan", key="exec_null_drop"):
                before = len(df)
                df = remove_null_rows(df, subset=[selected_null_col])
                st.session_state.df = df
                st.success(f"✅ {before - len(df)} baris dihapus!")
                st.rerun()
        else:
            fill_val = st.text_input("Nilai pengisi", key="fill_val")
            if st.button("Jalankan", key="exec_null_fill") and fill_val:
                df = fill_null_values(df, selected_null_col, fill_val)
                st.session_state.df = df
                st.success(f"✅ Null di kolom '{selected_null_col}' diisi dengan '{fill_val}'!")
                st.rerun()
    else:
        st.info("✅ Tidak ada kolom dengan nilai null.")

with tab_replace:
    st.markdown("### Ganti Nilai")

    rep_col = st.selectbox("Pilih kolom", df.columns.tolist(), key="rep_col")
    if rep_col:
        unique_vals = df[rep_col].dropna().unique()
        st.caption(f"Jumlah nilai unik: {len(unique_vals)}")

        if len(unique_vals) <= 50:
            with st.expander("Lihat nilai unik"):
                st.write(sorted([str(v) for v in unique_vals]))

        col_old, col_new = st.columns(2)
        with col_old:
            old_val = st.text_input("Nilai lama", key="old_val")
        with col_new:
            new_val = st.text_input("Nilai baru", key="new_val")

        if st.button("🔄 Ganti", type="primary", key="exec_replace"):
            if old_val:
                df = replace_values(df, rep_col, old_val, new_val)
                st.session_state.df = df
                st.success(f"✅ '{old_val}' → '{new_val}' di kolom '{rep_col}'")
                st.rerun()

with tab_columns:
    st.markdown("### Kelola Kolom")

    col_rename, col_drop = st.columns(2)

    with col_rename:
        st.markdown("#### Rename Kolom")
        rename_col = st.selectbox("Pilih kolom", df.columns.tolist(), key="rename_col")
        new_name = st.text_input("Nama baru", key="new_col_name")
        if st.button("✏️ Rename", key="exec_rename") and new_name:
            df = rename_column(df, rename_col, new_name)
            st.session_state.df = df
            st.success(f"✅ Kolom '{rename_col}' → '{new_name}'")
            st.rerun()

    with col_drop:
        st.markdown("#### Hapus Kolom")
        drop_cols = st.multiselect("Pilih kolom untuk dihapus", df.columns.tolist(), key="drop_cols")
        if st.button("🗑️ Hapus Kolom", key="exec_drop") and drop_cols:
            df = drop_columns(df, drop_cols)
            st.session_state.df = df
            st.success(f"✅ {len(drop_cols)} kolom dihapus!")
            st.rerun()

with tab_editor:
    st.markdown("### Edit Data Langsung")
    st.caption("Klik sel untuk mengedit. Perubahan akan otomatis disimpan saat Anda klik di luar sel.")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=500,
        num_rows="dynamic",
    )

    if st.button("💾 Simpan Perubahan", type="primary", key="save_edits"):
        st.session_state.df = edited_df
        st.success("✅ Perubahan disimpan!")
        st.rerun()

# --------------- Preview ---------------
st.markdown("---")
st.markdown("### 👀 Preview Data (Setelah Cleaning)")
st.dataframe(st.session_state.df, use_container_width=True, height=400)

# Sidebar
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
