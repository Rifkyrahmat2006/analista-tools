import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pivot_analysis import single_choice_analysis, scale_analysis, scale_statistics, cross_tabulation
from utils.multi_select_analysis import multi_choice_analysis, multi_choice_combinations
from utils.text_analysis import analyze_text_column, get_top_keywords
from utils.export_helpers import chart_to_png, table_to_png

st.set_page_config(page_title="Analysis", page_icon="📈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .analysis-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.5rem;
        color: white;
        margin-bottom: 1.5rem;
    }
    .analysis-header h2 { color: white; margin: 0; }
    .analysis-header p { color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Custom Plotly theme
PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#e0e0e0"),
    margin=dict(t=40, b=40, l=40, r=40),
)

st.markdown("# 📈 Analysis")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# --------------- Question Type Configuration ---------------
st.markdown("### ⚙️ Konfigurasi Tipe Pertanyaan")
st.caption("Tentukan tipe setiap kolom untuk menjalankan analisis yang sesuai.")

if "question_types" not in st.session_state:
    st.session_state.question_types = {}

# Show configuration in expander
with st.expander("📋 Konfigurasi Kolom", expanded=True):
    cols_per_row = 3
    columns = df.columns.tolist()

    for i in range(0, len(columns), cols_per_row):
        row_cols = st.columns(cols_per_row)
        for j, col_widget in enumerate(row_cols):
            idx = i + j
            if idx < len(columns):
                col_name = columns[idx]
                with col_widget:
                    q_type = st.selectbox(
                        f"**{col_name}**",
                        options=["skip", "single_choice", "multiple_choice", "scale", "open_text"],
                        index=0,
                        key=f"qtype_{col_name}",
                        help=f"Contoh data: {', '.join(str(v) for v in df[col_name].dropna().head(3).tolist())}",
                    )
                    st.session_state.question_types[col_name] = q_type

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
                fig_bar.update_layout(**PLOTLY_LAYOUT, showlegend=False)
                fig_bar.update_traces(textposition="outside")
                st.plotly_chart(fig_bar, use_container_width=True)

            with tab_pie:
                fig_pie = px.pie(
                    result, names="Value", values="Count",
                    color_discrete_sequence=PLOTLY_COLORS,
                    hole=0.4,
                )
                fig_pie.update_layout(**PLOTLY_LAYOUT)
                fig_pie.update_traces(textinfo="label+percent")
                st.plotly_chart(fig_pie, use_container_width=True)

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            try:
                png_bytes = chart_to_png(fig_bar)
                st.download_button("🖼️ Download Chart (PNG)", data=png_bytes,
                                   file_name=f"{col_name}_bar_chart.png", mime="image/png",
                                   use_container_width=True, key=f"dl_chart_{col_name}")
            except Exception:
                pass
        with exp2:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Frekuensi")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp3:
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
            fig_scale.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
            fig_scale.update_traces(textposition="outside")
            fig_scale.update_xaxes(type="category")
            st.plotly_chart(fig_scale, use_container_width=True)

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            try:
                png_bytes = chart_to_png(fig_scale)
                st.download_button("🖼️ Download Chart (PNG)", data=png_bytes,
                                   file_name=f"{col_name}_scale_chart.png", mime="image/png",
                                   use_container_width=True, key=f"dl_chart_{col_name}")
            except Exception:
                pass
        with exp2:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Distribusi Scale")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp3:
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
            fig_multi.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
            fig_multi.update_traces(textposition="outside")
            st.plotly_chart(fig_multi, use_container_width=True)

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            try:
                png_bytes = chart_to_png(fig_multi)
                st.download_button("🖼️ Download Chart (PNG)", data=png_bytes,
                                   file_name=f"{col_name}_multi_chart.png", mime="image/png",
                                   use_container_width=True, key=f"dl_chart_{col_name}")
            except Exception:
                pass
        with exp2:
            try:
                tbl_png = table_to_png(result, title=f"{col_name} — Frekuensi Jawaban")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp3:
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
            fig_text.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
            fig_text.update_traces(textposition="outside")
            st.plotly_chart(fig_text, use_container_width=True)

            st.caption("💡 Untuk wordcloud, kunjungi halaman **☁️ Wordcloud**")

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            try:
                png_bytes = chart_to_png(fig_text)
                st.download_button("🖼️ Download Chart (PNG)", data=png_bytes,
                                   file_name=f"{col_name}_keywords_chart.png", mime="image/png",
                                   use_container_width=True, key=f"dl_chart_{col_name}")
            except Exception:
                pass
        with exp2:
            try:
                tbl_png = table_to_png(top_kw, title=f"{col_name} — Top Keywords")
                st.download_button("📋 Download Tabel (PNG)", data=tbl_png,
                                   file_name=f"{col_name}_keywords_table.png", mime="image/png",
                                   use_container_width=True, key=f"dl_tbl_{col_name}")
            except Exception:
                pass
        with exp3:
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
