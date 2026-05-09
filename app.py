import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer

st.set_page_config(
    page_title="Analista Tools",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme_css()

# --------------- Hero Section ---------------
st.markdown("""
<div class="hero-container">
    <div style="display: flex; align-items: center; justify-content: center; gap: 12px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>
        <h1 style="margin: 0; color: white !important;">Analista Tools</h1>
    </div>
    <p>Upload, bersihkan, analisis, dan visualisasikan data survei Anda dengan mudah</p>
</div>
""", unsafe_allow_html=True)

# --------------- Feature Cards ---------------
st.markdown("### :material/stars: Fitur Utama")
st.markdown("")

col1, col2, col3, col4, col5 = st.columns(5)

features = [
    ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>', "Upload Data", "Upload CSV atau Excel langsung dari Google Form export"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>', "Data Cleaning", "Edit, hapus, rename, dan bersihkan data dengan mudah"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>', "Analisis", "Analisis otomatis berdasarkan tipe pertanyaan survei"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg>', "Visualisasi", "Chart interaktif: bar, pie, donut, treemap, wordcloud"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>', "Wordcloud", "Wordcloud terintegrasi di tab Visualisasi"),
]

for col, (icon, title, desc) in zip([col1, col2, col3, col4, col5], features):
    with col:
        st.markdown(f"""
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <div class="feature-title">{title}</div>
            <div class="feature-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")
st.markdown("")

# --------------- Pipeline ---------------
st.markdown("### :material/sync: Alur Kerja")
st.markdown("")

steps = ["Upload Dataset", "Preview Data", "Data Cleaning", "Konfigurasi Tipe", "Analisis", "Visualisasi"]
pipeline_html = ""
for i, step in enumerate(steps):
    pipeline_html += f'<span class="pipeline-step">{step}</span>'
    if i < len(steps) - 1:
        pipeline_html += '<span class="pipeline-arrow">→</span>'

st.markdown(f'<div style="text-align:center; padding: 1rem 0;">{pipeline_html}</div>', unsafe_allow_html=True)

st.markdown("")

# --------------- Quick Start ---------------
st.markdown("### :material/rocket_launch: Mulai Cepat")
st.markdown("""
1. Buka halaman **:material/upload: Upload Data** di sidebar
2. Upload file CSV atau Excel dari Google Form
3. Bersihkan data di halaman **:material/cleaning_services: Data Cleaning**
4. Konfigurasi tipe pertanyaan dan jalankan analisis di **:material/trending_up: Analysis**
5. Lihat visualisasi & generate **:material/cloud: Wordcloud** di **:material/bar_chart: Visualization**
""")

# --------------- Session State Info ---------------
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f":material/check_circle: Dataset loaded: **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
    else:
        st.info(":material/info: Belum ada dataset. Upload data terlebih dahulu.")

render_sidebar_footer()
render_page_footer()
