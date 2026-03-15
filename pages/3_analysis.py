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
st.markdown("### 📊 Hasil Analisis")
st.caption("Konfigurasi tipe setiap kolom untuk menyesuaikan analisis yang dihasilkan. Tipe terdeteksi otomatis — Anda bisa mengubahkan secara manual.")

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

        # ----------------- Configuration & Previews -----------------
        if current_val in ["multiple_choice", "single_choice"]:
            if current_val == "multiple_choice":
                prev_data = get_multiple_choice_preview(df[col_name])
            else:
                prev_data = get_single_choice_preview(df[col_name])
                
            ms_key = f"mainopts_{col_name}"
            hd_key = f"hiddenpts_{col_name}"
            # Initialize states
            if ms_key not in st.session_state:
                st.session_state[ms_key] = prev_data.get("main_names", []).copy()
            if hd_key not in st.session_state:
                st.session_state[hd_key] = set()
                
            current_mains = st.session_state[ms_key]
            current_hiddens = st.session_state[hd_key]
            
            # Show current Main Options
            st.caption("Options preview:")
            counts_dict = prev_data.get("counts", {})
            for opt in current_mains.copy():
                r1, r_hide, r_del = st.columns([0.85, 0.05, 0.05])
                count_val = counts_dict.get(opt, 0)
                
                is_hidden = opt in current_hiddens
                
                with r1:
                    strike = "~~" if is_hidden else ""
                    st.markdown(f"{strike}◯ {opt} ({count_val}){strike}")
                with r_hide:
                    eye_icon = "🙈" if is_hidden else "👁️"
                    if st.button(eye_icon, key=f"hide_{col_name}_{opt}"):
                        if is_hidden:
                            st.session_state[hd_key].remove(opt)
                        else:
                            st.session_state[hd_key].add(opt)
                        st.rerun()
                with r_del:
                    if st.button("❌", key=f"del_{col_name}_{opt}"):
                        st.session_state[ms_key].remove(opt)
                        if opt in st.session_state[hd_key]:
                            st.session_state[hd_key].remove(opt)
                        st.rerun()

            # Identify Others
            other_opts = [o for o in prev_data.get("all", []) if o not in current_mains]
            other_count = sum(counts_dict.get(o, 0) for o in other_opts)
            
            if other_count > 0:
                or1, or_hide, or_del = st.columns([0.85, 0.05, 0.05])
                is_other_hidden = "Other" in current_hiddens
                with or1:
                    strike = "~~" if is_other_hidden else ""
                    st.markdown(f"{strike}◯ **Other** ({other_count}){strike}")
                with or_hide:
                    eye_icon = "🙈" if is_other_hidden else "👁️"
                    if st.button(eye_icon, key=f"hide_{col_name}_Other"):
                        if is_other_hidden:
                            st.session_state[hd_key].remove("Other")
                        else:
                            st.session_state[hd_key].add("Other")
                        st.rerun()
                with or_del:
                    # Provide an empty column for visual consistency
                    pass
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Interactive 'Other' list
            if other_opts:
                with st.expander("Other responses detailed:"):
                    for oth in other_opts:
                        count_val = counts_dict.get(oth, 0)
                        orq1, orq2 = st.columns([0.95, 0.05])
                        with orq1:
                            st.markdown(f"• {oth} ({count_val})")
                        with orq2:
                            if st.button("➕", key=f"add_oth_{col_name}_{oth}"):
                                st.session_state[ms_key].append(oth)
                                st.rerun()

            # Add option manual input
            st.markdown("<br>", unsafe_allow_html=True)
            c_add1, c_add2 = st.columns([0.8, 0.2])
            with c_add1:
                new_opt = st.text_input("Add option", key=f"txt_{col_name}", label_visibility="collapsed", placeholder="Ketik opsi manual yang ingin dipindahkan dari Other...")
            with c_add2:
                if st.button("Add", key=f"btn_add_{col_name}", use_container_width=True):
                    all_opts = prev_data.get("all", [])
                    if new_opt and new_opt not in current_mains and new_opt in all_opts:
                        st.session_state[ms_key].append(new_opt)
                        st.rerun()
                    elif new_opt and new_opt not in all_opts:
                        st.warning("Opsi tidak ditemukan pada data kolom ini.")
            
        elif current_val == "scale":
            st.caption("Distribution Preview:")
            prev_data = df[col_name].value_counts().sort_index()
            for val, count in prev_data.items():
                st.markdown(f"• **{val}** : {count}")
                
        # Handle Open Text
        elif current_val == "open_text":
            pass
            
        st.markdown("---")

        # ----------------- Render Chart Analytics -----------------
        if current_val == "single_choice":
            main_opts = st.session_state.get(f"mainopts_{col_name}", [])
            hidden_opts = st.session_state.get(f"hiddenpts_{col_name}", set())
            result = single_choice_analysis(df, col_name, main_options=main_opts)
            
            # Filter hidden
            result = result[~result['Value'].isin(hidden_opts)]

            col_table, col_chart = st.columns([1, 2])
            with col_table:
                st.markdown("#### 📋 Tabel Frekuensi")
                st.dataframe(result, use_container_width=True, hide_index=True)

            with col_chart:
                fig_bar = px.bar(
                    result, x="Value", y="Count",
                    color="Value", color_discrete_sequence=PLOTLY_COLORS,
                    text="Count",
                )
                fig_bar.update_layout(showlegend=False, margin=dict(t=40, b=40, l=40, r=40))
                if force_light_mode: fig_bar.update_layout(**LIGHT_LAYOUT)
                fig_bar.update_traces(textposition="outside")
                bar_config = {"toImageButtonOptions": {"filename": f"{col_name}_bar_chart", "scale": 2}}
                st.plotly_chart(fig_bar, use_container_width=True, config=bar_config, theme=None if force_light_mode else "streamlit")

        elif current_val == "scale":
            result = scale_analysis(df, col_name)
            stats = scale_statistics(df, col_name)

            col_stats, col_chart = st.columns([1, 2])
            with col_stats:
                st.markdown("#### 📋 Distribusi")
                st.dataframe(result, use_container_width=True, hide_index=True)

                st.markdown("#### 📊 Statistik")
                stat_cols = st.columns(2)
                with stat_cols[0]:
                    st.metric("Mean", stats["mean"])
                    st.metric("Median", stats["median"])
                with stat_cols[1]:
                    st.metric("Std Dev", stats["std"])
                    st.metric("Responses", stats["count"])

            with col_chart:
                fig_scale = px.bar(
                    result, x="Scale", y="Count",
                    color="Count", color_continuous_scale="Purples",
                    text="Count",
                )
                fig_scale.update_layout(coloraxis_showscale=False, margin=dict(t=40, b=40, l=40, r=40))
                if force_light_mode: fig_scale.update_layout(**LIGHT_LAYOUT)
                fig_scale.update_traces(textposition="outside")
                fig_scale.update_xaxes(type="category")
                scale_config = {"toImageButtonOptions": {"filename": f"{col_name}_scale_chart", "scale": 2}}
                st.plotly_chart(fig_scale, use_container_width=True, config=scale_config, theme=None if force_light_mode else "streamlit")

        elif current_val == "multiple_choice":
            main_opts = st.session_state.get(f"mainopts_{col_name}", [])
            hidden_opts = st.session_state.get(f"hiddenpts_{col_name}", set())
            result = multi_choice_analysis(df, col_name, main_options=main_opts)

            # Filter hidden
            result = result[~result['Value'].isin(hidden_opts)]

            col_table, col_chart = st.columns([1, 2])
            with col_table:
                st.markdown("#### 📋 Frekuensi Jawaban")
                st.dataframe(result, use_container_width=True, hide_index=True)

            with col_chart:
                fig_multi = px.bar(
                    result, x="Count", y="Value",
                    orientation="h",
                    color="Count", color_continuous_scale="Purples",
                    text="Count",
                )
                fig_multi.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed", title=None), margin=dict(t=40, b=40))
                if force_light_mode: fig_multi.update_layout(**LIGHT_LAYOUT)
                fig_multi.update_traces(textposition="outside")
                multi_config = {"toImageButtonOptions": {"filename": f"{col_name}_multi_chart", "scale": 2}}
                st.plotly_chart(fig_multi, use_container_width=True, config=multi_config, theme=None if force_light_mode else "streamlit")

        elif current_val == "open_text":
            analysis = analyze_text_column(df, col_name)
            top_kw = get_top_keywords(analysis["word_freq"], top_n=15)

            col_stats, col_chart = st.columns([1, 2])
            with col_stats:
                st.markdown("#### 📊 Statistik Teks")
                st.metric("Total Respons", analysis["total_responses"])
                st.metric("Total Kata", analysis["total_words"])
                st.metric("Kata Unik", analysis["unique_words"])

            with col_chart:
                fig_text = px.bar(
                    top_kw, x="Frequency", y="Keyword",
                    orientation="h",
                    color="Frequency", color_continuous_scale="Purples",
                    text="Frequency",
                )
                fig_text.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"), margin=dict(t=40, b=40, l=40, r=40))
                if force_light_mode: fig_text.update_layout(**LIGHT_LAYOUT)
                fig_text.update_traces(textposition="outside")
                text_config = {"toImageButtonOptions": {"filename": f"{col_name}_keywords_chart", "scale": 2}}
                st.plotly_chart(fig_text, use_container_width=True, config=text_config, theme=None if force_light_mode else "streamlit")

            st.caption("💡 Untuk wordcloud, kunjungi halaman **☁️ Wordcloud**")

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
