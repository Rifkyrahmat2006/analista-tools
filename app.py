import streamlit as st

st.set_page_config(
    page_title="Survey Insight Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------- Custom CSS ---------------
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hero gradient header */
    .hero-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 3rem 2.5rem;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .hero-container h1 {
        font-size: 2.8rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: white;
    }
    .hero-container p {
        font-size: 1.15rem;
        opacity: 0.9;
        margin: 0;
    }

    /* Feature cards */
    .feature-card {
        background: linear-gradient(145deg, #1e1e2e, #2a2a3e);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 1.8rem 1.5rem;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }
    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
    }
    .feature-icon {
        font-size: 2.8rem;
        margin-bottom: 0.8rem;
    }
    .feature-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.4rem;
        color: #e0e0e0;
    }
    .feature-desc {
        font-size: 0.88rem;
        color: #9a9ab0;
        line-height: 1.5;
    }

    /* Pipeline step */
    .pipeline-step {
        display: inline-block;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        margin: 0.3rem;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .pipeline-arrow {
        display: inline-block;
        color: #667eea;
        font-size: 1.3rem;
        margin: 0 0.2rem;
        vertical-align: middle;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }

    /* Hide default streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


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
