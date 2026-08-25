"""
Wordcloud UI — Reusable Wordcloud Section
============================================
Ekstraksi 1:1 dari tab Wordcloud di pages/4_visualization.py, dibungkus
jadi satu fungsi supaya bisa dipanggil juga dari pages/6_pembagian_tugas.py
(tab "Tugas Saya", untuk pertanyaan bertipe open_text) TANPA duplikasi
kode dan TANPA perlu pindah halaman.

Tidak ada perubahan logika analisis/rendering dari versi Visualization —
hanya dipindah ke fungsi bersama supaya reusable di kedua halaman.
"""

from io import BytesIO

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.text_analysis import analyze_text_column, get_top_keywords, generate_wordcloud
from utils.export_helpers import render_copy_button
from utils.chart_builder import COLOR_SCALES, SCALE_EMOJIS, PLOTLY_SCALE_MAP

WC_SCALE_EMOJIS = {
    "Set2": "🟢 🟠 🔵", "Set3": "🟢 🟡 🟣", "Pastel1": "🔴 🔵 🟢",
    "Dark2": "🟢 🟠 🟣", "Accent": "🟢 🟣 🟠", "tab10": "🔵 🟠 🟢",
    "viridis": "🟣 🟢 🟡", "plasma": "🔵 🟣 🟡",
}


def render_wordcloud_section(df: pd.DataFrame, column: str, key_prefix: str, force_light_mode: bool = False):
    """
    Render seksi wordcloud lengkap (pengaturan + generate + hasil) untuk
    SATU kolom teks tertentu — dipakai baik di halaman Visualization
    (user pilih kolom dari dropdown semua kolom teks) maupun di
    Pembagian Tugas (kolom sudah ditentukan dari assignment, jadi
    section-nya langsung tampil tanpa dropdown kolom lagi).

    key_prefix: prefix unik untuk semua widget key Streamlit di section
    ini, supaya tidak bentrok kalau dipanggil berkali-kali di halaman
    yang sama (mis. beda pertanyaan open_text yang dipilih user).
    """
    col_config, col_preview = st.columns([1, 2])

    with col_config:
        st.markdown("#### :material/settings: Pengaturan")
        max_words = st.slider("Jumlah Kata Maksimum", 20, 200, 100, step=10, key=f"{key_prefix}_maxwords")
        top_n     = st.slider("Top Keywords", 5, 50, 20, key=f"{key_prefix}_topn")
        colormap = st.selectbox(
            ":material/palette: Skema Warna Wordcloud",
            ["Set2", "Set3", "Pastel1", "Dark2", "Accent", "tab10", "viridis", "plasma"],
            key=f"{key_prefix}_colormap", format_func=lambda x: f"{WC_SCALE_EMOJIS.get(x, '●')} {x}",
        )
        kw_colorscale = st.selectbox(
            ":material/palette: Skema Warna Top Keyword", COLOR_SCALES, index=0,
            key=f"{key_prefix}_kw_colorscale", format_func=lambda x: f"{SCALE_EMOJIS.get(x, '●')} {x}",
        )
        bg_color = st.color_picker("Background Color", value="#FFFFFF", key=f"{key_prefix}_bgcolor")
        st.markdown("---")
        use_stemming = st.checkbox(
            "Gunakan Stemming (Sastrawi)", value=False, key=f"{key_prefix}_stem",
            help="Mengubah kata berimbuhan menjadi kata dasar (misal: 'mengajar' -> 'ajar'). Dapat memperlambat proses pada data besar.",
        )
        extra_stopwords_input = st.text_area(
            ":material/block: Stopwords Tambahan", placeholder="dll, dsb, yg, tdk", key=f"{key_prefix}_stopwords",
        )
        generate_btn = st.button(":material/rocket_launch: Generate Wordcloud", type="primary",
                                  use_container_width=True, key=f"{key_prefix}_generate")

    with col_preview:
        if generate_btn:
            with st.spinner("Menganalisis teks..."):
                extra_sw = {w.strip().lower() for w in extra_stopwords_input.split(",") if w.strip()}
                analysis  = analyze_text_column(df, column, extra_stopwords=extra_sw, use_stemming=use_stemming)
                word_freq = analysis["word_freq"]
                top_kw    = get_top_keywords(word_freq, top_n=top_n)

            # Simpan hasil analisis ke session_state supaya bisa dipakai
            # PEMANGGIL (mis. tombol "Generate Draft dengan AI" di
            # pages/6_pembagian_tugas.py) TANPA perlu analisis ulang teks
            # dari nol -- top_kw ini agregat kata kunci, BUKAN jawaban
            # mentah individual mahasiswa (aman dikirim ke API AI pihak
            # ketiga, lihat utils/ai_generate.py).
            st.session_state[f"{key_prefix}_last_top_kw"] = top_kw

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Respons", analysis["total_responses"])
            c2.metric("Total Kata", analysis["total_words"])
            c3.metric("Kata Unik", analysis["unique_words"])

            if word_freq:
                wc = generate_wordcloud(word_freq, width=1000, height=500, background_color=bg_color, colormap=colormap, max_words=max_words)
                if wc:
                    import matplotlib
                    matplotlib.use("Agg")
                    import matplotlib.pyplot as plt

                    fig_wc, ax = plt.subplots(figsize=(12, 6))
                    ax.imshow(wc, interpolation="bilinear")
                    ax.axis("off")
                    fig_wc.patch.set_facecolor(bg_color)
                    plt.tight_layout(pad=0)
                    st.pyplot(fig_wc, use_container_width=True)
                    plt.close(fig_wc)

                    buf = BytesIO()
                    wc_img = wc.to_image()
                    wc_img.save(buf, format="PNG")
                    img_bytes = buf.getvalue()

                    c_dl1, c_dl2 = st.columns(2)
                    with c_dl1:
                        st.download_button(
                            ":material/download: Download Wordcloud (PNG)",
                            data=img_bytes, file_name=f"wordcloud_{column}.png",
                            mime="image/png", use_container_width=True, key=f"{key_prefix}_dl_wc",
                        )
                    with c_dl2:
                        render_copy_button(img_bytes, "Copy Wordcloud PNG", key=f"{key_prefix}_copy_wc")

                    with st.expander(":material/image: Tampilkan Wordcloud (Untuk Copy Manual)"):
                        st.info("Klik kanan pada gambar di bawah dan pilih **Copy Image** atau **Save Image As**.")
                        st.image(img_bytes)

                st.markdown("### :material/key: Top Keywords")
                kw_theme = PLOTLY_SCALE_MAP.get(kw_colorscale, kw_colorscale)
                fig_kw = px.bar(top_kw, x="Frequency", y="Keyword", orientation="h", color="Frequency",
                                 color_continuous_scale=kw_theme, text="Frequency")
                fig_kw.update_layout(yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20),
                                      height=max(300, top_n * 25), coloraxis_showscale=False)
                if force_light_mode:
                    from utils.theme import get_light_plotly_layout
                    fig_kw.update_layout(**get_light_plotly_layout())
                st.plotly_chart(fig_kw, use_container_width=True, theme=None if force_light_mode else "streamlit",
                                 key=f"{key_prefix}_fig_kw")

                try:
                    fig_kw_exp = go.Figure(fig_kw)
                    fig_kw_exp.update_layout(paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#1a1a2e"), width=1400)
                    kw_png = fig_kw_exp.to_image(format="png", scale=2)
                    render_copy_button(kw_png, "Copy Chart PNG", key=f"{key_prefix}_copy_kw_chart")
                    with st.expander(":material/image: Tampilkan Gambar (Untuk Copy Manual)"):
                        st.info("Klik kanan pada gambar di bawah dan pilih **Copy Image** atau **Save Image As**.")
                        st.image(kw_png)
                except Exception as e:
                    st.warning(f":material/warning: Gagal membuat gambar chart Top Keywords: {e}")

                with st.expander(":material/table_chart: Lihat Tabel Kata"):
                    st.dataframe(top_kw, use_container_width=True, hide_index=True)
            else:
                st.warning("Tidak ada kata yang ditemukan.")
        else:
            st.info(":material/arrow_back: Atur opsi di sebelah kiri lalu klik **Generate Wordcloud**.")
