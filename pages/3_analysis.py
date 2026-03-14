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
st.markdown("---")

for col_name in df.columns:
    suggested = st.session_state.detected_types.get(col_name, "skip")
    current_val = st.session_state.question_types.get(col_name, suggested)
    default_idx = TYPE_OPTIONS.index(current_val) if current_val in TYPE_OPTIONS else 0
    
    with st.container():
        # Block style header
        c1, c2 = st.columns([3, 1])
        
        with c1:
            st.markdown(f"#### {col_name}")
            # Badge
            badge_color = "#43e97b" if current_val == suggested else "#fa709a"
            st.markdown(
                f'<span style="background:{badge_color};color:#111;padding:2px 8px;'
                f'border-radius:8px;font-size:0.75rem;">🤖 Suggested: {suggested}</span>',
                unsafe_allow_html=True,
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Preview section based on currently selected type
            if current_val == "multiple_choice":
                st.caption("**Options Preview (Multiple Choice):**")
                prev_data = get_multiple_choice_preview(df[col_name])
                for opt, count in prev_data["main"]:
                    st.markdown(f"• {opt} ({count})")
                if prev_data["other_count"] > 0:
                    st.markdown(f"• **Other** ({prev_data['other_count']})")
                    with st.expander("Lihat Other responses"):
                        for oth in prev_data["other"]:
                            st.markdown(f"- {oth}")
                            
            elif current_val == "single_choice":
                st.caption("**Options Preview (Single Choice):**")
                prev_data = get_single_choice_preview(df[col_name])
                for opt, count in prev_data["main"]:
                    st.markdown(f"• {opt} ({count})")
                if prev_data["other_count"] > 0:
                    st.markdown(f"• **Other** ({prev_data['other_count']})")
                    with st.expander("Lihat Other responses"):
                        for oth in prev_data["other"]:
                            st.markdown(f"- {oth}")
                            
            elif current_val == "scale":
                st.caption("**Distribution Preview (Scale):**")
                prev_data = df[col_name].value_counts().sort_index()
                for val, count in prev_data.items():
                    st.markdown(f"**{val}** &rarr; {count}")
                    
            elif current_val == "open_text":
                st.caption("*Open Text - no options preview*")
                
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

        with c2:
            st.selectbox(
                "Tipe Pertanyaan",
                options=TYPE_OPTIONS,
                index=default_idx,
                key=f"qtype_{col_name}",
                label_visibility="collapsed"
            )
            # We must update session state immediately so the preview reflects the choice
            st.session_state.question_types[col_name] = st.session_state[f"qtype_{col_name}"]

        st.markdown("---")

st.markdown("---")

# --------------- Run Analysis ---------------
configured_cols = {k: v for k, v in st.session_state.question_types.items() if v != "skip"}

if not configured_cols:
    st.info("👆 Pilih tipe pertanyaan untuk kolom yang ingin dianalisis, kemudian scroll ke bawah untuk melihat hasil.")
    st.stop()

st.markdown(f"### 📊 Hasil Analisis ({len(configured_cols)} kolom)")

for col_name, q_type in configured_cols.items():
    st.markdown(f"""
    <div class="analysis-header">
        <h2>{col_name}</h2>
        <p>Tipe: {q_type.replace('_', ' ').title()}</p>
    </div>
    """, unsafe_allow_html=True)

    if q_type == "single_choice":
        result = single_choice_analysis(df, col_name)
        col_table, col_chart = st.columns([1, 2])

        with col_table:
            st.markdown("#### 📋 Tabel Frekuensi")
            st.dataframe(result, use_container_width=True, hide_index=True)

        with col_chart:
            tab_bar, tab_pie = st.tabs(["📊 Bar Chart", "🥧 Pie Chart"])

            with tab_bar:
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

            with tab_pie:
                fig_pie = px.pie(
                    result, names="Value", values="Count",
                    color_discrete_sequence=PLOTLY_COLORS,
                    hole=0.4,
                )
                fig_pie.update_layout(margin=dict(t=40, b=40, l=40, r=40))
                if force_light_mode: fig_pie.update_layout(**LIGHT_LAYOUT)
                fig_pie.update_traces(textinfo="label+percent")
                pie_config = {"toImageButtonOptions": {"filename": f"{col_name}_pie_chart", "scale": 2}}
                st.plotly_chart(fig_pie, use_container_width=True, config=pie_config, theme=None if force_light_mode else "streamlit")

        # Export buttons
        exp1, exp2 = st.columns(2)
        with exp1:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Frekuensi")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp2:
            csv_data = result.to_csv(index=False)
            st.download_button("📄 Download Data (CSV)", data=csv_data,
                               file_name=f"{col_name}_analysis.csv", mime="text/csv",
                               use_container_width=True, key=f"dl_csv_{col_name}")

    elif q_type == "scale":
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

        # Export buttons
        exp1, exp2 = st.columns(2)
        with exp1:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Distribusi Scale")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp2:
            csv_data = result.to_csv(index=False)
            st.download_button("📄 Download Data (CSV)", data=csv_data,
                               file_name=f"{col_name}_analysis.csv", mime="text/csv",
                               use_container_width=True, key=f"dl_csv_{col_name}")

    elif q_type == "multiple_choice":
        result = multi_choice_analysis(df, col_name)

        col_table, col_chart = st.columns([1, 2])

        with col_table:
            st.markdown("#### 📋 Frekuensi Jawaban")
            st.dataframe(result, use_container_width=True, hide_index=True)

            with st.expander("🔗 Kombinasi Populer"):
                combos = multi_choice_combinations(df, col_name)
                st.dataframe(combos, use_container_width=True, hide_index=True)

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

        # Export buttons
        exp1, exp2 = st.columns(2)
        with exp1:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Frekuensi Jawaban")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp2:
            csv_data = result.to_csv(index=False)
            st.download_button("📄 Download Data (CSV)", data=csv_data,
                               file_name=f"{col_name}_analysis.csv", mime="text/csv",
                               use_container_width=True, key=f"dl_csv_{col_name}")

    elif q_type == "open_text":
        analysis = analyze_text_column(df, col_name)
        top_kw = get_top_keywords(analysis["word_freq"], top_n=15)

        col_stats, col_chart = st.columns([1, 2])

        with col_stats:
            st.markdown("#### 📊 Statistik Teks")
            st.metric("Total Respons", analysis["total_responses"])
            st.metric("Total Kata", analysis["total_words"])
            st.metric("Kata Unik", analysis["unique_words"])

            st.markdown("#### 🔑 Top Keywords")
            st.dataframe(top_kw, use_container_width=True, hide_index=True)

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

        # Export buttons
        exp1, exp2 = st.columns(2)
        with exp1:
            try:
                tbl_png = table_to_png(top_kw, title=f"{col_name} — Top Keywords")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_keywords_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp2:
            csv_data = top_kw.to_csv(index=False)
            st.download_button("📄 Download Data (CSV)", data=csv_data,
                               file_name=f"{col_name}_keywords.csv", mime="text/csv",
                               use_container_width=True, key=f"dl_csv_{col_name}")

    st.markdown("---")

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
