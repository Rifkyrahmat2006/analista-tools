import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.theme import inject_theme_css, render_sidebar_footer, render_page_footer
from utils.auth import render_user_badge_sidebar, current_user
from utils.permissions import require_permission, has_permission
from utils.db import (
    init_db, list_users, upsert_survey_questions, list_survey_questions,
    assign_question, update_assignment_progress, get_my_assignments, log_action,
    QUESTION_TYPE_TO_CHART,
)
from utils.question_detection import detect_question_type
from utils.chart_builder import build_quick_chart, CHART_OPTIONS_PER_TYPE, DEFAULT_CHART_PER_TYPE
from utils.export_helpers import table_to_png, render_copy_button, generate_matplotlib_chart

st.set_page_config(page_title="Pembagian Tugas", layout="wide")
inject_theme_css()

user = require_permission("tasks.view")
render_user_badge_sidebar()
init_db()

st.markdown("# :material/assignment: Pembagian Tugas Analisis Survei")
st.caption(
    "Pengganti dokumen pembagian tugas manual — assign pertanyaan ke anggota tim, "
    "rekomendasi jenis chart otomatis, dan tulis kesimpulan langsung di sini."
)

# Tab setup & assign hanya utk role dgn izin "tasks.assign" (admin/superadmin).
# Cek permission RBAC, bukan role string manual.
is_manager = has_permission(user["role"], "tasks.assign")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning(":material/warning: Belum ada dataset. Silakan upload data terlebih dahulu di halaman **Upload Data**.")
    st.stop()

dataset_name = st.session_state.get("dataset_name", "Unknown")
df = st.session_state.df

if is_manager:
    tab_setup, tab_board, tab_my = st.tabs([
        ":material/build: Setup Pertanyaan", ":material/dashboard: Papan Tugas (Semua)", ":material/person: Tugas Saya"
    ])
else:
    tab_my, = st.tabs([":material/person: Tugas Saya"])
    tab_setup = tab_board = None

# ─────────────────────────────────────────────────────────────
if tab_setup is not None:
    with tab_setup:
        st.markdown("### 1. Deteksi & Registrasi Pertanyaan dari Dataset Aktif")
        st.caption(f"Dataset aktif: **{dataset_name}** ({len(df)} baris, {len(df.columns)} kolom)")

        if st.button(":material/auto_awesome: Deteksi Tipe Pertanyaan & Daftarkan", type="primary", key="detect_questions_btn"):
            questions = []
            for col in df.columns:
                if col.lower() in ("timestamp", "nama lengkap", "nama"):
                    continue  # skip kolom metadata, bukan pertanyaan substantif
                qtype = detect_question_type(df[col])
                questions.append({"column_name": col, "question_type": qtype})

            n = upsert_survey_questions(dataset_name, questions)
            log_action(user["username"], user["role"], "register_questions", f"Deteksi {n} pertanyaan dari dataset '{dataset_name}'")
            st.success(f"Berhasil mendaftarkan {n} pertanyaan dengan rekomendasi chart otomatis!")
            st.rerun()

        st.markdown("---")
        st.markdown("### 2. Assign Pertanyaan ke Anggota Tim")

        questions = list_survey_questions(dataset_name)
        if not questions:
            st.info("Belum ada pertanyaan terdaftar. Klik tombol deteksi di atas dulu.")
        else:
            all_users = [u for u in list_users() if u["active"]]
            user_options = {"(belum ditugaskan)": None}
            user_options.update({f"{u['full_name']} ({u['username']})": u["id"] for u in all_users})

            for q in questions:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.markdown(f"**{q['column_name']}**")
                        st.caption(f"Tipe: `{q['question_type']}` → Chart disarankan: **{q['suggested_chart']}**")
                    with c2:
                        current_assignee_label = "(belum ditugaskan)"
                        for label, uid in user_options.items():
                            if uid == q.get("assigned_to"):
                                current_assignee_label = label
                                break
                        selected = st.selectbox(
                            "Ditugaskan ke", list(user_options.keys()),
                            index=list(user_options.keys()).index(current_assignee_label),
                            key=f"assign_{q['id']}", label_visibility="collapsed",
                        )
                    with c3:
                        if st.button("Simpan", key=f"save_assign_{q['id']}", use_container_width=True):
                            assign_question(q["id"], user_options[selected], user["username"])
                            log_action(user["username"], user["role"], "assign_question", f"'{q['column_name']}' -> {selected}")
                            st.rerun()
                        status_badge = {
                            "belum_dikerjakan": ":material/radio_button_unchecked: Belum dikerjakan",
                            "dikerjakan": ":material/pending: Dikerjakan",
                            "selesai": ":material/check_circle: Selesai",
                        }.get(q.get("status") or "belum_dikerjakan", "")
                        st.caption(status_badge)

# ─────────────────────────────────────────────────────────────
if tab_board is not None:
    with tab_board:
        st.markdown("### Papan Tugas — Semua Anggota")
        questions = list_survey_questions(dataset_name)
        if not questions:
            st.info("Belum ada pertanyaan terdaftar untuk dataset ini.")
        else:
            board_df = pd.DataFrame(questions)[[
                "column_name", "question_type", "suggested_chart",
                "assigned_to_name", "status", "conclusion_text",
            ]].rename(columns={
                "column_name": "Pertanyaan",
                "question_type": "Tipe",
                "suggested_chart": "Chart Disarankan",
                "assigned_to_name": "Ditugaskan Ke",
                "status": "Status",
                "conclusion_text": "Kesimpulan",
            })
            board_df["Ditugaskan Ke"] = board_df["Ditugaskan Ke"].fillna("(belum ditugaskan)")
            board_df["Status"] = board_df["Status"].fillna("belum_dikerjakan")

            n_total = len(board_df)
            n_done = (board_df["Status"] == "selesai").sum()
            n_progress = (board_df["Status"] == "dikerjakan").sum()

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Pertanyaan", n_total)
            m2.metric("Sedang Dikerjakan", int(n_progress))
            m3.metric("Selesai", int(n_done))
            st.progress(n_done / n_total if n_total else 0)

            st.dataframe(board_df, use_container_width=True, height=450)

            csv_bytes = board_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                ":material/download: Unduh Papan Tugas (CSV, pengganti PDF pembagian tugas)",
                data=csv_bytes, file_name=f"pembagian_tugas_{dataset_name}.csv", mime="text/csv",
            )

# ─────────────────────────────────────────────────────────────
with tab_my:
    st.markdown("### Tugas Saya")
    st.caption(
        "Semua pertanyaan yang ditugaskan kepada Anda, lengkap dengan chart & tabel "
        "analisis langsung di sini — tidak perlu pindah ke halaman Visualization dan "
        "mencari kolomnya satu per satu."
    )
    my_assignments = get_my_assignments(user["id"])

    if not my_assignments:
        st.info("Belum ada pertanyaan yang ditugaskan kepada Anda.")
    else:
        # Ringkasan progres di atas — biar langsung kelihatan berapa yang
        # sudah/belum dikerjakan tanpa scroll ke bawah satu-satu.
        n_total_my = len(my_assignments)
        n_done_my = sum(1 for a in my_assignments if (a.get("status") or "belum_dikerjakan") == "selesai")
        n_progress_my = sum(1 for a in my_assignments if (a.get("status") or "belum_dikerjakan") == "dikerjakan")
        mm1, mm2, mm3 = st.columns(3)
        mm1.metric("Total Tugas Saya", n_total_my)
        mm2.metric("Sedang Dikerjakan", n_progress_my)
        mm3.metric("Selesai", n_done_my)
        st.progress(n_done_my / n_total_my if n_total_my else 0)
        st.markdown("---")

        for a in my_assignments:
            with st.container(border=True):
                st.markdown(f"#### {a['column_name']}")
                st.caption(f"Dataset: `{a['dataset_name']}` · Tipe: `{a['question_type']}` · Chart disarankan: **{a['suggested_chart']}**")

                # ── Chart & Tabel langsung di sini (BARU) ──
                # BUG/PERMINTAAN YANG DIPENUHI: sebelumnya tab ini cuma
                # menampilkan status + kolom kesimpulan teks — untuk
                # benar-benar MELIHAT datanya (chart, angka), user harus
                # pindah ke halaman Visualization dan cari kolom yang sama
                # secara manual dari dropdown. Sekarang chart & tabel
                # langsung dirender di sini, memakai dataset yang sedang
                # aktif di session (st.session_state.df) — kalau dataset
                # aktif beda dari dataset saat pertanyaan itu didaftarkan,
                # kasih tahu user supaya upload/pilih dataset yang benar.
                question_type = a.get("question_type")
                if a["dataset_name"] != dataset_name:
                    st.warning(
                        f":material/warning: Pertanyaan ini terdaftar untuk dataset **{a['dataset_name']}**, "
                        f"sedangkan dataset aktif saat ini adalah **{dataset_name}**. "
                        "Upload/pilih ulang dataset yang sesuai untuk melihat chart & tabelnya."
                    )
                elif question_type == "open_text":
                    st.info(
                        ":material/text_fields: Pertanyaan ini bertipe **open text** (jawaban bebas) — "
                        "gunakan tab **Wordcloud** di halaman Visualization untuk analisis kata kunci & wordcloud-nya."
                    )
                elif a["column_name"] not in df.columns:
                    st.warning(f":material/warning: Kolom **{a['column_name']}** tidak ditemukan di dataset aktif.")
                else:
                    chart_options = CHART_OPTIONS_PER_TYPE.get(question_type, ["Bar Chart"])
                    default_chart = DEFAULT_CHART_PER_TYPE.get(question_type, chart_options[0])
                    picked_chart = st.selectbox(
                        "Tipe Chart", chart_options,
                        index=chart_options.index(default_chart) if default_chart in chart_options else 0,
                        key=f"my_chart_type_{a['id']}",
                        label_visibility="collapsed",
                    )

                    built = build_quick_chart(df, a["column_name"], question_type, chart_type=picked_chart, title=a["column_name"])
                    if built["fig"] is None or built["result"] is None or built["result"].empty:
                        st.info("Tidak ada data untuk ditampilkan pada kolom ini.")
                    else:
                        st.plotly_chart(built["fig"], use_container_width=True, config={"displaylogo": False}, key=f"my_fig_{a['id']}")

                        cpng1, cpng2 = st.columns([1, 1])
                        with cpng1:
                            if st.button(":material/photo_camera: Buat Gambar Statis", key=f"my_static_{a['id']}", use_container_width=True):
                                st.session_state[f"my_show_static_{a['id']}"] = True
                        if st.session_state.get(f"my_show_static_{a['id']}"):
                            try:
                                display_result = built["result"].drop(columns=["_text", "_disp_label"], errors="ignore")
                                png_bytes = generate_matplotlib_chart(
                                    chart_type=built["chart_type"], df=built["result"],
                                    val_col=built["val_col"], count_col=built["count_col"],
                                    colors=built["colors"], title=a["column_name"],
                                )
                                render_copy_button(png_bytes, "Copy Chart PNG", key=f"my_copy_chart_{a['id']}")
                                st.image(png_bytes, caption=f"{a['column_name']} (Copyable PNG)")
                            except Exception as e:
                                st.warning(f":material/warning: Gagal membuat gambar statis: {e}")

                        with st.expander(":material/table_chart: Lihat Tabel Data"):
                            display_result = built["result"].drop(columns=["_text", "_disp_label"], errors="ignore")
                            st.dataframe(display_result, use_container_width=True, hide_index=True)
                            try:
                                table_png = table_to_png(display_result, title="")
                                render_copy_button(table_png, "Copy Table PNG", key=f"my_copy_table_{a['id']}")
                            except Exception as e:
                                st.warning(f":material/warning: Gagal membuat gambar tabel: {e}")

                st.markdown("---")

                status_options = ["belum_dikerjakan", "dikerjakan", "selesai"]
                current_status = a.get("status") or "belum_dikerjakan"
                new_status = st.selectbox(
                    "Status pengerjaan", status_options,
                    index=status_options.index(current_status),
                    key=f"my_status_{a['id']}",
                )
                conclusion = st.text_area(
                    "Kesimpulan (isi di sini, tidak perlu dokumen terpisah lagi)",
                    value=a.get("conclusion_text") or "",
                    key=f"my_conclusion_{a['id']}",
                    height=120,
                )

                if st.button(":material/save: Simpan", key=f"my_save_{a['id']}", type="primary"):
                    update_assignment_progress(a["id"], new_status, conclusion)
                    log_action(user["username"], user["role"], "update_assignment", f"'{a['column_name']}' status={new_status}")
                    st.success("Tersimpan!")
                    st.rerun()

render_sidebar_footer()
render_page_footer()
