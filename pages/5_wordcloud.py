import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import sys
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.text_analysis import analyze_text_column, get_top_keywords, generate_wordcloud
from utils.theme import inject_theme_css, get_plotly_export_layout

st.set_page_config(page_title="Wordcloud", page_icon="☁️", layout="wide")

inject_theme_css()

st.markdown("# ☁️ Wordcloud Generator")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# Identify text columns (object dtype)
text_columns = df.select_dtypes(include=["object"]).columns.tolist()

if not text_columns:
    st.warning("⚠️ Tidak ada kolom teks dalam dataset.")
    st.stop()

# --------------- Settings ---------------
col_config, col_preview = st.columns([1, 2])

with col_config:
    st.markdown("### ⚙️ Pengaturan")

    selected_col = st.selectbox("📝 Pilih Kolom Teks", text_columns)

    st.markdown("---")

    max_words = st.slider("Jumlah Kata Maksimum", 20, 200, 100, step=10)
    top_n = st.slider("Top Keywords", 5, 50, 20)

    colormap = st.selectbox(
        "🎨 Skema Warna",
        ["Set2", "Set3", "Pastel1", "Dark2", "Accent", "tab10", "viridis", "plasma", "inferno", "cool"],
    )

    bg_color = st.color_picker("Background Color", value="#0e1117")

    st.markdown("---")

    extra_stopwords_input = st.text_area(
        "🚫 Stopwords Tambahan",
        placeholder="Masukkan kata yang ingin diabaikan, pisahkan dengan koma.\nContoh: dll, dsb, yg, tdk",
        height=100,
    )
    extra_stopwords = set()
    if extra_stopwords_input:
        extra_stopwords = {w.strip().lower() for w in extra_stopwords_input.split(",") if w.strip()}

    generate_btn = st.button("🚀 Generate Wordcloud", type="primary", use_container_width=True)

with col_preview:
    if generate_btn and selected_col:
        with st.spinner("Menganalisis teks..."):
            analysis = analyze_text_column(df, selected_col, extra_stopwords=extra_stopwords)
            word_freq = analysis["word_freq"]
            top_kw = get_top_keywords(word_freq, top_n=top_n)

        # Stats
        c1, c2, c3 = st.columns(3)
        for c, (val, lbl) in zip(
            [c1, c2, c3],
            [
                (analysis["total_responses"], "Total Respons"),
                (analysis["total_words"], "Total Kata"),
                (analysis["unique_words"], "Kata Unik"),
            ],
        ):
            with c:
                st.markdown(f"""
                <div class="wc-stat">
                    <div class="wc-stat-val">{val}</div>
                    <div class="wc-stat-lbl">{lbl}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("")

        if word_freq:
            # Generate Wordcloud
            wc = generate_wordcloud(
                word_freq,
                width=1000,
                height=500,
                background_color=bg_color,
                colormap=colormap,
                max_words=max_words,
            )

            if wc:
                # Display wordcloud
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off")
                fig.patch.set_facecolor(bg_color)
                plt.tight_layout(pad=0)
                st.pyplot(fig, use_container_width=True)

                # Download wordcloud
                buf = BytesIO()
                wc.to_image().save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    "📥 Download Wordcloud (PNG)",
                    data=buf,
                    file_name=f"wordcloud_{selected_col}.png",
                    mime="image/png",
                    use_container_width=True,
                )

            # Top keywords
            st.markdown("### 🔑 Top Keywords")

            EXPORT_LAYOUT = get_plotly_export_layout()

            fig = px.bar(
                top_kw, x="Frequency", y="Keyword",
                orientation="h",
                color="Frequency",
                color_continuous_scale="Purples",
                text="Frequency",
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(t=20, b=20, l=20, r=20),
                height=max(300, top_n * 25),
                coloraxis_showscale=False,
            )
            fig.update_traces(textposition="outside")
            wc_chart_config = {"toImageButtonOptions": {"filename": f"{selected_col}_keywords", "scale": 2, **EXPORT_LAYOUT}}
            st.plotly_chart(fig, use_container_width=True, config=wc_chart_config)

            # Data table
            with st.expander("📋 Lihat Tabel Kata"):
                st.dataframe(top_kw, use_container_width=True, hide_index=True)

                csv_data = top_kw.to_csv(index=False)
                st.download_button(
                    "📄 Download Keywords (CSV)",
                    data=csv_data,
                    file_name=f"keywords_{selected_col}.csv",
                    mime="text/csv",
                )
        else:
            st.warning("⚠️ Tidak ada kata yang ditemukan setelah cleaning.")

    elif not generate_btn:
        st.markdown("")
        st.markdown("")
        st.info("👈 Pilih kolom teks dan klik **Generate Wordcloud** untuk memulai analisis.")

# Sidebar
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
