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
    detect_hidden_nulls,
)
from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer

st.set_page_config(page_title="Data Cleaning", layout="wide")

inject_theme_css()

st.markdown("# :material/cleaning_services: Data Cleaning")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning(":material/warning: Belum ada dataset. Silakan upload data terlebih dahulu di halaman **:material/upload: Upload Data**.")
    st.stop()

if "cleaning_log" not in st.session_state:
    st.session_state.cleaning_log = []
if "df_prev" not in st.session_state:
    st.session_state.df_prev = None

def log_action(action: str):
    st.session_state.cleaning_log.append({
        "waktu": pd.Timestamp.now().strftime("%H:%M:%S"),
        "aksi": action
    })

def apply_change(new_df, action_desc):
    st.session_state.df_prev = st.session_state.df.copy()
    st.session_state.df = new_df
    log_action(action_desc)

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

# --------------- Anomali Redirect ---------------
null_counts = {col: cnt for col, cnt in summary["null_counts"].items() if cnt > 0}
if null_counts:
    with st.expander(f":material/warning: {len(null_counts)} Kolom Berisi Nilai Anomali (Null) — Klik untuk Redirect", expanded=False):
        st.markdown("Pilih kolom di bawah untuk langsung menuju penanganan nilai null:")
        # Show each column with its null count as a clickable button
        n_cols = min(3, len(null_counts))
        btn_rows = [list(null_counts.items())[i:i+n_cols] for i in range(0, len(null_counts), n_cols)]
        for row in btn_rows:
            cols_btns = st.columns(n_cols)
            for i, (col_name, cnt) in enumerate(row):
                with cols_btns[i]:
                    if st.button(
                        f":material/error: **{col_name}** — {cnt} null",
                        key=f"anom_redirect_{col_name}",
                        use_container_width=True,
                    ):
                        st.session_state["redirect_null_col"] = col_name
                        st.rerun()

# Apply redirect: pre-select column in Quick Clean null section
_redirect_col = st.session_state.pop("redirect_null_col", None)

# --------------- Current Table Preview ---------------
st.markdown("### :material/table_view: Preview Data Saat Ini")

if _redirect_col:
    st.info(f":material/info: Menyorot nilai null pada kolom **{_redirect_col}**")
    
    def highlight_nulls(s):
        if s.name == _redirect_col:
            return ['background-color: rgba(236, 72, 153, 0.2); color: #ec4899; font-weight: bold;' if pd.isna(v) else '' for v in s]
        return ['' for v in s]
        
    st.dataframe(df.style.apply(highlight_nulls), use_container_width=True, height=350)
else:
    st.dataframe(df, use_container_width=True, height=350)

st.markdown("---")

# --------------- Cleaning Operations ---------------
tab_quick, tab_replace, tab_columns, tab_editor, tab_fuzzy, tab_validation, tab_log = st.tabs([
    ":material/flash_on: Quick", ":material/find_replace: Replace", ":material/view_column: Kolom", ":material/edit: Edit", ":material/merge_type: Kategori", ":material/verified_user: Validasi", ":material/history: Log"
])

with tab_quick:
    st.markdown("### Operasi Pembersihan Cepat")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button(":material/visibility_off: Deteksi Null Terselubung", use_container_width=True, help="Ubah '-', 'N/A', spasi kosong menjadi nilai Null asli"):
            before_nulls = df.isnull().sum().sum()
            new_df = detect_hidden_nulls(df)
            after_nulls = new_df.isnull().sum().sum()
            apply_change(new_df, f"Deteksi Null Terselubung (Ditemukan {after_nulls - before_nulls} null baru)")
            st.success(f":material/check_circle: {after_nulls - before_nulls} nilai null terselubung berhasil diungkap!")
            st.rerun()

        if st.button(":material/format_clear: Strip Whitespace", use_container_width=True, help="Hapus spasi di awal dan akhir teks"):
            new_df = strip_whitespace(df)
            apply_change(new_df, "Strip whitespace dari teks")
            st.success(":material/check_circle: Whitespace dihapus!")
            st.rerun()

    with col_b:
        if st.button(":material/text_format: Lowercase Semua Teks", use_container_width=True, help="Ubah semua teks menjadi huruf kecil"):
            new_df = lowercase_normalize(df)
            apply_change(new_df, "Ubah teks ke lowercase")
            st.success(":material/check_circle: Teks dinormalisasi ke lowercase!")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Hapus Baris Null")
    null_subset = st.multiselect("Berdasarkan Kolom (Kosongkan untuk cek semua kolom)", df.columns.tolist(), key="null_subset")
    if st.button(":material/delete: Hapus Baris Null", use_container_width=True, help="Hapus baris yang memiliki nilai kosong"):
        before = len(df)
        new_df = remove_null_rows(df, subset=null_subset if null_subset else None)
        removed = before - len(new_df)
        apply_change(new_df, f"Hapus {removed} baris null")
        st.success(f":material/check_circle: {removed} baris null dihapus!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### Hapus Duplikat")
    dup_subset = st.multiselect("Berdasarkan Kolom Kunci (Kosongkan untuk exact match semua kolom)", df.columns.tolist(), key="dup_subset")
    keep_opt = st.radio("Baris yang Dipertahankan", ["first", "last", "none"], horizontal=True, index=0)
    if st.button(":material/block: Hapus Duplikat", use_container_width=True, help="Hapus duplikat berdasarkan parameter"):
        before = len(df)
        keep_val = False if keep_opt == "none" else keep_opt
        new_df = remove_duplicate_rows(df, subset=dup_subset if dup_subset else None, keep=keep_val)
        removed = before - len(new_df)
        apply_change(new_df, f"Hapus {removed} baris duplikat")
        st.success(f":material/check_circle: {removed} baris duplikat dihapus!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### Hapus Null per Kolom")
    null_cols = [col for col in df.columns if df[col].isnull().sum() > 0]
    if null_cols:
        # Use redirected column if available
        null_col_default = _redirect_col if _redirect_col and _redirect_col in null_cols else null_cols[0]
        null_col_idx = null_cols.index(null_col_default)
        selected_null_col = st.selectbox("Pilih kolom", null_cols, index=null_col_idx, key="null_col")
        null_action = st.radio(
            "Tindakan",
            ["Hapus baris dengan null", "Isi dengan nilai tertentu"],
            key="null_action",
            horizontal=True,
        )

        if null_action == "Hapus baris dengan null":
            if st.button("Jalankan", key="exec_null_drop"):
                before = len(df)
                new_df = remove_null_rows(df, subset=[selected_null_col])
                apply_change(new_df, f"Hapus baris dengan null pada '{selected_null_col}'")
                st.success(f":material/check_circle: {before - len(new_df)} baris dihapus!")
                st.rerun()
        else:
            fill_val = st.text_input("Nilai pengisi", key="fill_val")
            if st.button("Jalankan", key="exec_null_fill") and fill_val:
                new_df = fill_null_values(df, selected_null_col, fill_val)
                apply_change(new_df, f"Isi null di '{selected_null_col}' dengan '{fill_val}'")
                st.success(f":material/check_circle: Null di kolom '{selected_null_col}' diisi dengan '{fill_val}'!")
                st.rerun()
    else:
        st.info(":material/check_circle: Tidak ada kolom dengan nilai null.")

    # Show redirect notification
    if _redirect_col:
        st.info(f":material/info: Diarahkan ke kolom **{_redirect_col}** yang memiliki nilai null.")

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

        if st.button(":material/find_replace: Ganti", type="primary", key="exec_replace"):
            if old_val:
                before_vals = df[rep_col].tolist()
                new_df = replace_values(df, rep_col, old_val, new_val)
                after_vals = new_df[rep_col].tolist()
                changed = sum(1 for a, b in zip(before_vals, after_vals) if a != b)
                if changed > 0:
                    apply_change(new_df, f"Ganti '{old_val}' menjadi '{new_val}' di '{rep_col}'")
                    st.success(f":material/check_circle: {changed} nilai diubah: '{old_val}' → '{new_val}' di kolom '{rep_col}'")
                    st.rerun()
                else:
                    st.warning(f":material/warning: Tidak ada nilai '{old_val}' yang ditemukan di kolom '{rep_col}'. Periksa tipe data atau ejaan nilai.")
            else:
                st.warning(":material/warning: Masukkan nilai lama terlebih dahulu.")

with tab_columns:
    st.markdown("### Kelola Kolom")

    col_rename, col_drop = st.columns(2)

    with col_rename:
        st.markdown("#### Rename Kolom")
        rename_col = st.selectbox("Pilih kolom", df.columns.tolist(), key="rename_col")
        new_name = st.text_input("Nama baru", key="new_col_name")
        if st.button(":material/edit: Rename", key="exec_rename") and new_name:
            new_df = rename_column(df, rename_col, new_name)
            apply_change(new_df, f"Rename kolom '{rename_col}' menjadi '{new_name}'")
            st.success(f":material/check_circle: Kolom '{rename_col}' → '{new_name}'")
            st.rerun()

    with col_drop:
        st.markdown("#### Hapus Kolom")
        drop_cols = st.multiselect("Pilih kolom untuk dihapus", df.columns.tolist(), key="drop_cols")
        if st.button(":material/delete: Hapus Kolom", key="exec_drop") and drop_cols:
            new_df = drop_columns(df, drop_cols)
            apply_change(new_df, f"Hapus {len(drop_cols)} kolom")
            st.success(f":material/check_circle: {len(drop_cols)} kolom dihapus!")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Ekstrak Jawaban 'Lainnya' (Multi-Select)")
    st.caption("Jika Anda memiliki pertanyaan Checkbox (Multi-select) dengan opsi 'Lainnya', teks spesifik yang diketik responden (contoh 'Lainnya: saya suka kopi') akan diekstrak ke kolom baru agar analisis chart tetap rapi (menjadi 'Lainnya' saja).")
    lainnya_col = st.selectbox("Pilih kolom Multi-Select", df.select_dtypes(include=['object']).columns.tolist(), key="lainnya_col")
    
    if st.button(":material/call_split: Ekstrak Teks 'Lainnya'", key="exec_lainnya"):
        from utils.multi_select_analysis import extract_lainnya
        new_df = extract_lainnya(df, lainnya_col)
        # Check if new column was created
        expected_new_col = f"{lainnya_col}_lainnya_text"
        if expected_new_col in new_df.columns:
            apply_change(new_df, f"Ekstrak teks 'Lainnya' dari '{lainnya_col}'")
            st.success(f":material/check_circle: Teks 'Lainnya' berhasil dipisahkan ke kolom baru: `{expected_new_col}`!")
            st.rerun()
        else:
            st.info(f":material/info: Tidak ditemukan teks 'Lainnya: ...' atau 'Other: ...' pada kolom '{lainnya_col}'.")

with tab_editor:
    st.markdown("### Edit Data Langsung")
    st.caption("Klik sel untuk mengedit. Perubahan akan otomatis disimpan saat Anda klik di luar sel.")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=500,
        num_rows="dynamic",
    )

    if st.button(":material/save: Simpan Perubahan", type="primary", key="save_edits"):
        apply_change(edited_df, "Edit data tabel secara manual")
        st.success(":material/check_circle: Perubahan disimpan!")
        st.rerun()

with tab_fuzzy:
    st.markdown("### Standarisasi Kategori (Fuzzy Matching)")
    st.caption("Deteksi kategori yang memiliki nama mirip (typo) dan gabungkan menjadi satu.")
    fuzzy_col = st.selectbox("Pilih kolom kategori", df.select_dtypes(include=['object']).columns.tolist(), key="fuzzy_col")
    
    if fuzzy_col:
        try:
            from thefuzz import process, fuzz
            unique_vals = df[fuzzy_col].dropna().unique().tolist()
            if len(unique_vals) > 1 and len(unique_vals) <= 500:
                threshold = st.slider("Tingkat Kemiripan Minimal (%)", 70, 99, 85, key="fuzzy_thresh")
                
                clusters = []
                visited = set()
                for val in unique_vals:
                    if val in visited:
                        continue
                    matches = process.extract(val, unique_vals, scorer=fuzz.ratio, limit=10)
                    similar = [m[0] for m in matches if m[1] >= threshold and m[0] != val]
                    if similar:
                        clusters.append((val, similar))
                        visited.update(similar)
                        visited.add(val)
                
                if clusters:
                    st.success(f":material/check_circle: Ditemukan {len(clusters)} kelompok kategori yang mirip!")
                    for idx, (main_val, sim_vals) in enumerate(clusters):
                        with st.container():
                            st.markdown(f"**Target Utama**: `{main_val}`")
                            st.write(f"Mirip dengan: {', '.join([f'`{v}`' for v in sim_vals])}")
                            if st.button(f"Merge ke '{main_val}'", key=f"fuzzy_merge_{idx}"):
                                new_df = df.copy()
                                new_df[fuzzy_col] = new_df[fuzzy_col].replace(sim_vals, main_val)
                                apply_change(new_df, f"Fuzzy Merge: {sim_vals} menjadi '{main_val}' di '{fuzzy_col}'")
                                st.rerun()
                            st.markdown("---")
                else:
                    st.info(":material/info: Tidak ditemukan kategori yang mirip berdasarkan persentase kemiripan.")
            elif len(unique_vals) > 500:
                st.warning("Terlalu banyak nilai unik (>500) untuk dilakukan fuzzy matching. Silakan gunakan Replace Manual.")
        except ImportError:
            st.error("Pustaka `thefuzz` belum terinstal.")

with tab_validation:
    st.markdown("### Validasi Responden")
    st.caption("Deteksi baris (responden) yang mencurigakan seperti asal isi (Straight-lining).")
    
    scale_cols = st.multiselect("Pilih kolom skala/numerik untuk dicek (min. 3)", df.select_dtypes(include=['number']).columns.tolist(), key="val_cols")
    
    if len(scale_cols) >= 3:
        if st.button("Deteksi Straight-lining"):
            std_dev = df[scale_cols].std(axis=1)
            straight_liners = df[std_dev == 0]
            
            if len(straight_liners) > 0:
                st.warning(f":material/warning: Ditemukan {len(straight_liners)} baris yang menjawab sama untuk semua kolom terpilih!")
                with st.expander("Lihat Data Mencurigakan"):
                    st.dataframe(straight_liners)
                if st.button(f"Hapus {len(straight_liners)} Baris Mencurigakan", type="primary"):
                    new_df = df.drop(straight_liners.index).reset_index(drop=True)
                    apply_change(new_df, f"Hapus {len(straight_liners)} baris (Straight-lining) pada kolom {scale_cols}")
                    st.rerun()
            else:
                st.success(":material/check_circle: Tidak ditemukan indikasi straight-lining yang sempurna (semua jawaban persis sama).")
    else:
        st.info("Pilih minimal 3 kolom numerik untuk mendeteksi pola straight-lining.")

with tab_log:
    st.markdown("### Riwayat Modifikasi (Cleaning Log)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if not st.session_state.cleaning_log:
            st.info("Belum ada riwayat modifikasi pada sesi ini.")
        else:
            log_df = pd.DataFrame(st.session_state.cleaning_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True)
            
    with col2:
        if st.session_state.df_prev is not None:
            if st.button(":material/undo: Undo Aksi Terakhir", type="primary", use_container_width=True):
                st.session_state.df = st.session_state.df_prev.copy()
                st.session_state.df_prev = None
                log_action("Undo diklik")
                st.success("Aksi terakhir dibatalkan!")
                st.rerun()
        else:
            st.button(":material/undo: Undo (Tidak Tersedia)", disabled=True, use_container_width=True)

# --------------- Preview ---------------
st.markdown("---")
st.markdown("### :material/visibility: Preview Data (Setelah Cleaning)")
st.dataframe(st.session_state.df, use_container_width=True, height=400)

# Sidebar
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f":material/check_circle: **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")

render_sidebar_footer()
render_page_footer()
