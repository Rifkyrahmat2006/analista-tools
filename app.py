import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.theme import inject_theme_css

st.set_page_config(
    page_title="Survey Insight Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme_css()

# --------------- Hero Section ---------------
st.markdown("""
<div class="hero-container">
    <h1>📊 Survey Insight Dashboard</h1>
    <p>Upload, bersihkan, analisis, dan visualisasikan data survei Anda dengan mudah</p>
</div>
""", unsafe_allow_html=True)

# --------------- Feature Cards ---------------
st.markdown("### ✨ Fitur Utama")
st.markdown("")

col1, col2, col3, col4, col5 = st.columns(5)

features = [
    ("📤", "Upload Data", "Upload CSV atau Excel langsung dari Google Form export"),
    ("🧹", "Data Cleaning", "Edit, hapus, rename, dan bersihkan data dengan mudah"),
    ("📈", "Analisis", "Analisis otomatis berdasarkan tipe pertanyaan survei"),
    ("📊", "Visualisasi", "Chart interaktif dengan Plotly — bar, pie, dan lainnya"),
    ("☁️", "Wordcloud", "Analisis teks terbuka dan generate wordcloud"),
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
st.markdown("### 🔄 Alur Kerja")
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
st.markdown("### 🚀 Mulai Cepat")
st.markdown("""
1. Buka halaman **📤 Upload Data** di sidebar
2. Upload file CSV atau Excel dari Google Form
3. Bersihkan data di halaman **🧹 Data Cleaning**
4. Konfigurasi tipe pertanyaan dan jalankan analisis di **📈 Analysis**
5. Lihat visualisasi di **📊 Visualization** atau generate **☁️ Wordcloud**
""")

# --------------- Session State Info ---------------
with st.sidebar:
    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ Dataset loaded: **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
    else:
        st.info("📤 Belum ada dataset. Upload data terlebih dahulu.")
