
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
from utils.theme import inject_theme_css, get_light_plotly_layout

st.set_page_config(page_title="Responses Analysis", page_icon="📊", layout="wide")

inject_theme_css()

PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
LIGHT_LAYOUT = get_light_plotly_layout()

with st.sidebar:
    st.markdown("### 🖨️ Export Settings")
    force_light_mode = st.checkbox(
        "Paksa Chart Terang", 
        help="Aktifkan agar chart Plotly berlatar putih. Sangat berguna sebelum Anda mengunduh chart (logo kamera) agar hasil download siap cetak."
    )

st.markdown("# 📊 Responses Analysis")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

if "question_types" not in st.session_state:
    st.info("👆 Silakan lakukan konfigurasi pertanyaan di halaman 'Analysis' terlebih dahulu.")
    st.stop()

# --------------- Run Analysis ---------------
configured_cols = {k: v for k, v in st.session_state.question_types.items() if v != "skip"}

if not configured_cols:
    st.info("👆 Konfigurasi pertanyaan masih kosong. Silakan buka halaman 'Analysis'.")
    st.stop()

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
        main_opts = st.session_state.get(f"mainopts_{col_name}")
        result = single_choice_analysis(df, col_name, main_options=main_opts)
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
        main_opts = st.session_state.get(f"mainopts_{col_name}")
        result = multi_choice_analysis(df, col_name, main_options=main_opts)

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
