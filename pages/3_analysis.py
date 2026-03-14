import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pivot_analysis import single_choice_analysis, scale_analysis, scale_statistics, cross_tabulation, get_single_choice_preview
from utils.multi_select_analysis import multi_choice_analysis, multi_choice_combinations, get_multiple_choice_preview
from utils.text_analysis import analyze_text_column, get_top_keywords
from utils.export_helpers import table_to_png
from utils.question_detection import detect_question_type, analyze_column_features
from utils.theme import inject_theme_css, get_light_plotly_layout

st.set_page_config(page_title="Analysis", page_icon="📈", layout="wide")

inject_theme_css()

# Custom Plotly color sequence (to keep brand colors)
PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
LIGHT_LAYOUT = get_light_plotly_layout()

with st.sidebar:
    st.markdown("### 🖨️ Export Settings")
    force_light_mode = st.checkbox(
        "Paksa Chart Terang", 
        help="Aktifkan agar chart Plotly berlatar putih. Sangat berguna sebelum Anda mengunduh chart (logo kamera) agar hasil download siap cetak."
    )

    if st.button("Reset Pengaturan Kolom", use_container_width=True):
        st.session_state.question_types = {}
        st.rerun()

st.markdown("# 📈 Analysis")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# --------------- Question Type Configuration ---------------
st.markdown("### ⚙️ Konfigurasi Tipe Pertanyaan")
st.caption("Tentukan tipe setiap kolom untuk menjalankan analisis yang sesuai. Tipe terdeteksi otomatis — Anda bisa override manual.")

TYPE_OPTIONS = ["skip", "single_choice", "multiple_choice", "scale", "open_text"]

if "question_types" not in st.session_state:
    st.session_state.question_types = {}

# Pre-compute detections (cached per dataset to avoid re-running)
if "detected_types" not in st.session_state or st.session_state.get("_det_id") != id(df):
    st.session_state.detected_types = {}
    st.session_state.detected_features = {}
    for col in df.columns:
        st.session_state.detected_types[col] = detect_question_type(df[col])
        st.session_state.detected_features[col] = analyze_column_features(df[col])
    st.session_state._det_id = id(df)

# Show configuration in a vertical block layout
search_q = st.text_input("🔍 Cari Pertanyaan...", placeholder="Ketik kata kunci pertanyaan...", key="search_config")

for col_name in df.columns:
    if search_q and search_q.lower() not in col_name.lower():
        continue
        
    suggested = st.session_state.detected_types.get(col_name, "skip")
    current_val = st.session_state.question_types.get(col_name, suggested)
    default_idx = TYPE_OPTIONS.index(current_val) if current_val in TYPE_OPTIONS else 0
    
    with st.container(border=True):
        # Block style header
        c1, c2 = st.columns([3, 1])
        
        with c1:
            st.markdown(f"**{col_name}**")
        with c2:
            st.selectbox(
                "Tipe Pertanyaan",
                options=TYPE_OPTIONS,
                index=default_idx,
                key=f"qtype_{col_name}",
                label_visibility="collapsed"
            )
            # update session state immediately
            st.session_state.question_types[col_name] = st.session_state[f"qtype_{col_name}"]

        st.markdown("<br>", unsafe_allow_html=True)

        if current_val in ["multiple_choice", "single_choice"]:
            if current_val == "multiple_choice":
                prev_data = get_multiple_choice_preview(df[col_name])
            else:
                prev_data = get_single_choice_preview(df[col_name])
                
            ms_key = f"mainopts_{col_name}"
            # Initialize state
            if ms_key not in st.session_state:
                st.session_state[ms_key] = prev_data.get("main_names", []).copy()
                
            current_mains = st.session_state[ms_key]
            
            # Show current Main Options
            st.caption("Options preview:")
            counts_dict = prev_data.get("counts", {})
            for opt in current_mains.copy():
                r1, r2 = st.columns([0.95, 0.05])
                count_val = counts_dict.get(opt, 0)
                with r1:
                    st.markdown(f"◯ {opt} ({count_val})")
                with r2:
                    if st.button("❌", key=f"del_{col_name}_{opt}"):
                        st.session_state[ms_key].remove(opt)
                        st.rerun()

            # Identify Others
            other_opts = [o for o in prev_data.get("all", []) if o not in current_mains]
            other_count = sum(counts_dict.get(o, 0) for o in other_opts)
            
            if other_count > 0:
                st.markdown(f"◯ **Other** ({other_count})")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Interactive 'Other' list
            if other_opts:
                st.caption("Other responses:")
                for oth in other_opts:
                    count_val = counts_dict.get(oth, 0)
                    or1, or2 = st.columns([0.95, 0.05])
                    with or1:
                        st.markdown(f"• {oth} ({count_val})")
                    with or2:
                        if st.button("➕", key=f"add_oth_{col_name}_{oth}"):
                            st.session_state[ms_key].append(oth)
                            st.rerun()

            # Add option manual input
            st.markdown("<br>", unsafe_allow_html=True)
            c_add1, c_add2 = st.columns([0.8, 0.2])
            with c_add1:
                new_opt = st.text_input("Add option", key=f"txt_{col_name}", label_visibility="collapsed", placeholder="Ketik opsi manual...")
            with c_add2:
                if st.button("Add", key=f"btn_add_{col_name}", use_container_width=True):
                    all_opts = prev_data.get("all", [])
                    if new_opt and new_opt not in current_mains and new_opt in all_opts:
                        st.session_state[ms_key].append(new_opt)
                        st.rerun()
                    elif new_opt and new_opt not in all_opts:
                        st.warning("Opsi tidak ditemukan.")
            
        elif current_val == "scale":
            st.caption("Distribution Preview:")
            prev_data = df[col_name].value_counts().sort_index()
            for val, count in prev_data.items():
                st.markdown(f"**{val}** ({count})")
                
        # Handle Open Text (Rules say: "Only display question text and selector. No options preview.")
        elif current_val == "open_text":
            pass
            
        # Column Stats
        feat = st.session_state.detected_features.get(col_name, {})
        with st.expander("📊 Column Stats", expanded=False):
            st.markdown(
                f"- **Total responses:** {df[col_name].count()}\n"
                f"- **Unique values:** {int(df[col_name].dropna().nunique())}\n"
                f"- **Null ratio:** {feat.get('null_ratio', 0)}\n"
                f"- **Delimiter ratio:** {feat.get('delimiter_ratio', 0)}\n"
                f"- **Numeric ratio:** {feat.get('numeric_ratio', 0)}\n"
                f"- **Avg text length:** {feat.get('avg_text_length', 0)}\n"
                f"- **Avg word count:** {feat.get('avg_word_count', 0)}"
            )

    st.markdown("---")

st.success("✅ Konfigurasi tersimpan. Silakan buka halaman **Responses Analysis** di menu samping untuk melihat chart dan tabel.")

# Sidebar
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
        st.markdown("---")
        st.markdown("**Kolom Terkonfigurasi:**")
        for col_name, q_type in configured_cols.items():
            st.caption(f"• {col_name}: `{q_type}`")
