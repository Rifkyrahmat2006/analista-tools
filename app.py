import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer
from utils.auth import require_login, render_user_badge_sidebar
from utils.db import init_db, get_dashboard_summary, format_relative_time

st.set_page_config(
    page_title="Analista Tools",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme_css()

current_user = require_login()
render_user_badge_sidebar()
init_db()

# Label & pembersih detail utk baris Aktivitas Terbaru -- murni
# presentational, tidak perlu masuk utils/db.py (bukan logic bisnis).
ACTION_LABELS = {
    "login": ":material/login: Login",
    "logout": ":material/logout: Logout",
    "assign_question": ":material/assignment: Assign pertanyaan",
    "update_assignment": ":material/edit: Update tugas",
    "register_questions": ":material/auto_awesome: Deteksi pertanyaan",
    "upload_dataset": ":material/upload: Upload dataset",
    "reset_password": ":material/key: Reset password",
    "create_user": ":material/person_add: Buat user baru",
    "deactivate_user": ":material/person_off: Nonaktifkan user",
}


def _clean_detail(detail: str, max_len: int = 60) -> str:
    if not detail:
        return ""
    flat = " ".join(detail.split())  # gabung newline/spasi ganda jadi 1 baris
    return flat if len(flat) <= max_len else flat[:max_len].rstrip() + "..."


dataset_name = st.session_state.get("dataset_name")
summary = get_dashboard_summary(dataset_name)

# --------------- Header ringkas ---------------
st.markdown("# :material/dashboard: Dashboard")
st.caption(f"Selamat datang, **{current_user['full_name']}** — ringkasan kondisi Analista Tools saat ini.")

if not dataset_name:
    st.warning(
        ":material/warning: Belum ada dataset aktif. Upload dataset di halaman "
        "**Upload Data** untuk melihat ringkasan lengkap sesuai dataset itu "
        "(ringkasan di bawah ini masih menampilkan data GLOBAL lintas semua dataset)."
    )

st.markdown("---")

# --------------- Metric cards ringkas ---------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Pertanyaan", summary["total_questions"])
c2.metric("Sudah Ditugaskan", summary["total_assigned"])
c3.metric("Belum Ditugaskan", summary["total_unassigned"])
c4.metric("Anggota Tim Aktif", summary["total_active_users"])

st.markdown("---")

# --------------- Progres Tugas (donut) + Breakdown Tim (bar) ---------------
col_progress, col_team = st.columns(2)

with col_progress:
    st.markdown("### :material/pie_chart: Progres Pembagian Tugas")
    status_df = pd.DataFrame([
        {"Status": "Belum Dikerjakan", "Jumlah": summary["status_counts"]["belum_dikerjakan"]},
        {"Status": "Dikerjakan", "Jumlah": summary["status_counts"]["dikerjakan"]},
        {"Status": "Selesai", "Jumlah": summary["status_counts"]["selesai"]},
    ])
    if status_df["Jumlah"].sum() > 0:
        fig = px.pie(
            status_df, names="Status", values="Jumlah", hole=0.5,
            color="Status",
            color_discrete_map={
                "Belum Dikerjakan": "#94a3b8",
                "Dikerjakan": "#fbbf24",
                "Selesai": "#34d399",
            },
        )
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    else:
        st.info("Belum ada pertanyaan yang ditugaskan.")

with col_team:
    st.markdown("### :material/groups: Anggota Tim per Role")
    team_df = pd.DataFrame([
        {"Role": k.capitalize(), "Jumlah": v} for k, v in summary["users_by_role"].items()
    ])
    fig2 = px.bar(team_df, x="Role", y="Jumlah", color="Role", text="Jumlah")
    fig2.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
    st.plotly_chart(fig2, use_container_width=True, config={"displaylogo": False})

st.markdown("---")

# --------------- Aktivitas Terbaru ---------------
st.markdown("### :material/history: Aktivitas Terbaru")
if summary["recent_activity"]:
    for act in summary["recent_activity"]:
        label = ACTION_LABELS.get(act["action"], act["action"])
        detail_txt = _clean_detail(act.get("detail", ""))
        time_txt = format_relative_time(act["timestamp"])
        detail_suffix = f": _{detail_txt}_" if detail_txt else ""
        st.markdown(
            f"**{act['username']}** — {label}{detail_suffix}  \n"
            f"<span style='font-size:0.78rem;opacity:0.6;'>{time_txt}</span>",
            unsafe_allow_html=True,
        )
else:
    st.caption("Belum ada aktivitas tercatat.")

st.markdown("---")

# --------------- Quick Links (pengganti "Mulai Cepat") ---------------
st.markdown("### :material/rocket_launch: Quick Links")
qc1, qc2, qc3 = st.columns(3)
with qc1:
    if st.button(":material/upload: Upload Data", use_container_width=True):
        st.switch_page("pages/1_upload_data.py")
with qc2:
    if st.button(":material/assignment: Pembagian Tugas", use_container_width=True):
        st.switch_page("pages/6_pembagian_tugas.py")
with qc3:
    if st.button(":material/bar_chart: Visualization", use_container_width=True):
        st.switch_page("pages/4_visualization.py")

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
