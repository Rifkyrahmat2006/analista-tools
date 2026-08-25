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
    QUESTION_TYPE_TO_CHART, update_question_type_chart,
)
from utils.question_detection import detect_question_type
from utils.chart_builder import (
    CHART_OPTIONS_PER_TYPE, DEFAULT_CHART_PER_TYPE, COLOR_SCALES, SCALE_EMOJIS,
    PLOTLY_SCALE_MAP, build_full_chart,
)
from utils.export_helpers import table_to_png, render_copy_button, generate_matplotlib_chart, df_to_xlsx_bytes
from utils.multi_select_analysis import get_multiple_choice_preview
from utils.theme import get_light_plotly_layout
from utils.wordcloud_ui import render_wordcloud_section
from utils.colorscale_hover import get_all_scale_preview_colors, render_colorscale_hover_preview
from utils.ai_generate import generate_conclusion_draft, build_data_summary, build_opentext_summary

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
        st.caption(
            "Tipe & Chart terisi otomatis dari hasil deteksi -- sesuaikan lagi lewat dropdown "
            "kalau deteksi otomatis kurang tepat untuk pertanyaan tertentu."
        )

        questions = list_survey_questions(dataset_name)
        if not questions:
            st.info("Belum ada pertanyaan terdaftar. Klik tombol deteksi di atas dulu.")
        else:
            all_users = [u for u in list_users() if u["active"]]
            user_options = {"(belum ditugaskan)": None}
            user_options.update({f"{u['full_name']} ({u['username']})": u["id"] for u in all_users})

            # PERMINTAAN USER: dropdown Tipe Pertanyaan -- deteksi otomatis
            # tetap jadi nilai default (index awal), tapi bisa dikoreksi
            # manual kalau kurang tepat (mis. kolom numerik yg sebenarnya
            # open_text, atau sebaliknya). "skip" sengaja tidak
            # ditampilkan sebagai pilihan -- kalau memang mau di-skip,
            # cukup jangan di-assign ke siapapun (soal skip tidak relevan
            # utk fitur pembagian tugas/chart).
            TYPE_OPTIONS = ["single_choice", "multiple_choice", "scale", "open_text"]
            TYPE_LABELS = {
                "single_choice": "Single Choice", "multiple_choice": "Multiple Choice",
                "scale": "Scale", "open_text": "Open Text",
            }

            # Tampilkan toast SEKALI setelah rerun dari klik Simpan --
            # lihat penjelasan lengkap di bawah tombol Simpan kenapa toast
            # tidak bisa langsung dipanggil sebelum st.rerun().
            _pending_toast = st.session_state.pop("_setup_save_toast", None)
            if _pending_toast:
                st.toast(_pending_toast, icon=":material/check_circle:")

            for q in questions:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1.6, 1.6, 2])
                    with c1:
                        st.markdown(f"**{q['column_name']}**")
                        status_badge = {
                            "belum_dikerjakan": ":material/radio_button_unchecked: Belum dikerjakan",
                            "dikerjakan": ":material/pending: Dikerjakan",
                            "selesai": ":material/check_circle: Selesai",
                        }.get(q.get("status") or "belum_dikerjakan", "")
                        st.caption(status_badge)
                    with c2:
                        current_type = q.get("question_type") if q.get("question_type") in TYPE_OPTIONS else TYPE_OPTIONS[0]
                        picked_type = st.selectbox(
                            "Tipe", TYPE_OPTIONS,
                            index=TYPE_OPTIONS.index(current_type),
                            key=f"qtype_{q['id']}", label_visibility="collapsed",
                            format_func=lambda x: TYPE_LABELS.get(x, x),
                        )
                    with c3:
                        if picked_type == "open_text":
                            # Open text SELALU Wordcloud -- tidak ada
                            # pilihan chart lain yg relevan (sama seperti
                            # halaman Visualization & Tugas Saya).
                            st.selectbox(
                                "Chart", ["Wordcloud"], index=0,
                                key=f"qchart_disabled_{q['id']}", label_visibility="collapsed", disabled=True,
                            )
                            picked_chart = "Wordcloud"
                        else:
                            chart_options = CHART_OPTIONS_PER_TYPE.get(picked_type, ["Bar Chart"])
                            # Chart tersimpan sebelumnya mungkin dari
                            # QUESTION_TYPE_TO_CHART (format lama, mis.
                            # "Pie / Bar Chart") -- BUKAN salah satu opsi
                            # persis di CHART_OPTIONS_PER_TYPE, jadi fallback
                            # ke default chart tipe itu kalau tidak match persis.
                            default_chart = DEFAULT_CHART_PER_TYPE.get(picked_type, chart_options[0])
                            current_chart = q.get("suggested_chart") if q.get("suggested_chart") in chart_options else default_chart
                            picked_chart = st.selectbox(
                                "Chart", chart_options,
                                index=chart_options.index(current_chart),
                                key=f"qchart_{q['id']}", label_visibility="collapsed",
                            )
                    with c4:
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

                    if st.button(":material/save: Simpan", key=f"save_assign_{q['id']}", use_container_width=True):
                        update_question_type_chart(q["id"], picked_type, picked_chart)
                        assign_question(q["id"], user_options[selected], user["username"])
                        log_action(
                            user["username"], user["role"], "assign_question",
                            f"'{q['column_name']}' -> tipe={picked_type}, chart={picked_chart}, assignee={selected}",
                        )
                        # PERMINTAAN USER: notifikasi konfirmasi tersimpan.
                        # PENTING: st.toast() dipanggil SEBELUM st.rerun()
                        # akan LANGSUNG HILANG krn st.rerun() membongkar
                        # seluruh DOM halaman saat ini (toast Streamlit
                        # adalah elemen UI biasa, bukan notifikasi browser
                        # native yg independen dari render) -- makanya
                        # simpan pesannya ke session_state dulu, lalu
                        # tampilkan toast di render BERIKUTNYA (blok
                        # _pending_toast di atas loop for ini), supaya
                        # toast benar-benar sempat terlihat user.
                        st.session_state["_setup_save_toast"] = f"'{q['column_name']}' tersimpan!"
                        st.rerun()



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
        "Pilih satu pertanyaan yang ditugaskan kepada Anda, atur chart-nya selengkap "
        "halaman Visualization (color scale, tipe chart, label, dst) — tapi dropdown-nya "
        "HANYA berisi soal yang Anda kerjakan, tidak perlu mencari dari semua kolom dataset."
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

        # ── Dropdown pilih SATU pertanyaan — HANYA yang ditugaskan ke user ──
        # PERMINTAAN USER: bukan tampilkan semua sekaligus (versi
        # sebelumnya), tapi model seperti halaman Visualization: pilih
        # dulu satu kolom dari dropdown, baru chart & pengaturannya
        # muncul. Bedanya dengan Visualization: dropdown ini HANYA berisi
        # soal yang di-assign ke user ini, bukan semua kolom dataset.
        status_icon = {"belum_dikerjakan": "⭕", "dikerjakan": "🟡", "selesai": "✅"}
        assignment_labels = {
            f"{status_icon.get(a.get('status') or 'belum_dikerjakan', '')} {a['column_name']}": a
            for a in my_assignments
        }
        picked_label = st.selectbox(
            ":material/assignment: Pilih Pertanyaan Tugas Anda",
            list(assignment_labels.keys()),
            key="my_task_picker",
        )
        a = assignment_labels[picked_label]

        st.caption(f"Dataset: `{a['dataset_name']}` · Tipe: `{a['question_type']}` · Chart disarankan: **{a['suggested_chart']}**")
        st.markdown("---")

        question_type = a.get("question_type")

        # ── Guard kasus tepi (bukan crash, tampilkan pesan jelas) ──
        if a["dataset_name"] != dataset_name:
            st.warning(
                f":material/warning: Pertanyaan ini terdaftar untuk dataset **{a['dataset_name']}**, "
                f"sedangkan dataset aktif saat ini adalah **{dataset_name}**. "
                "Upload/pilih ulang dataset yang sesuai untuk melihat chart & tabelnya."
            )
        elif question_type == "open_text":
            # PERMINTAAN USER: wordcloud untuk pertanyaan open_text
            # langsung di sini, tidak perlu pindah ke halaman
            # Visualization -> tab Wordcloud -> cari kolom yang sama lagi.
            if a["column_name"] not in df.columns:
                st.warning(f":material/warning: Kolom **{a['column_name']}** tidak ditemukan di dataset aktif.")
            else:
                st.markdown(f"### :material/cloud: Wordcloud — {a['column_name']}")
                render_wordcloud_section(df, a["column_name"], key_prefix=f"my_wc_{a['id']}")

                # PERMINTAAN USER: tombol generate draft kesimpulan dengan
                # AI dipindah jadi SATU lokasi saja, tepat di atas textarea
                # Kesimpulan (lihat bagian form status/kesimpulan di bawah)
                # -- bukan di sini lagi. Di sini kita cuma SIMPAN bahan
                # (data_summary) ke session_state kalau wordcloud sudah
                # di-generate, supaya tombol di bawah tahu ada bahan siap
                # pakai. top_kw ini agregat kata kunci, BUKAN jawaban
                # mentah individual mahasiswa (aman dikirim ke API AI
                # pihak ketiga, lihat utils/ai_generate.py).
                top_kw_key = f"my_wc_{a['id']}_last_top_kw"
                if top_kw_key in st.session_state:
                    st.session_state[f"my_ai_summary_{a['id']}"] = (
                        build_opentext_summary(st.session_state[top_kw_key]),
                        question_type,
                    )
                else:
                    st.session_state.pop(f"my_ai_summary_{a['id']}", None)
                    st.info(":material/info: Klik **Generate Wordcloud** di atas dulu agar tombol Generate Draft Kesimpulan dengan AI (di bawah) bisa dipakai.")
        elif a["column_name"] not in df.columns:
            st.warning(f":material/warning: Kolom **{a['column_name']}** tidak ditemukan di dataset aktif.")
        else:
            # ── Layout 2 kolom (settings kiri, tampilan kanan) — sama
            # seperti pola wordcloud, biar konsisten & user tidak perlu
            # scroll panjang buka-tutup expander untuk lihat hasil.
            col_config, col_preview = st.columns([1, 2])

            with col_config:
                st.markdown("#### :material/settings: Pengaturan Chart")
                chart_options = CHART_OPTIONS_PER_TYPE.get(question_type, ["Bar Chart"])
                # BUG DIPERBAIKI (dilaporkan user): sebelumnya default
                # chart di sini SELALU pakai DEFAULT_CHART_PER_TYPE
                # (hardcode per tipe, mis. "Pie Chart" utk single_choice),
                # TIDAK PERNAH membaca a["suggested_chart"] yg sudah
                # di-set manual admin di Setup Pertanyaan -- jadi walau
                # admin sudah ganti chart disarankan "Fakultas" jadi "Bar
                # Chart" di sana, tab Tugas Saya tetap paksa balik ke Pie
                # Chart (default single_choice). Sekarang: kalau
                # suggested_chart tersimpan valid utk tipe soal ini,
                # PAKAI itu sebagai default; fallback ke DEFAULT_CHART_PER_TYPE
                # HANYA kalau belum pernah di-set / tidak valid lagi
                # (mis. tipe soal berubah tapi suggested_chart lama sudah
                # tidak cocok dgn opsi tipe baru).
                fallback_default = DEFAULT_CHART_PER_TYPE.get(question_type, chart_options[0])
                default_chart = a.get("suggested_chart") if a.get("suggested_chart") in chart_options else fallback_default
                picked_chart = st.selectbox(
                    "Tipe Chart", chart_options,
                    index=chart_options.index(default_chart) if default_chart in chart_options else 0,
                    key=f"my_chart_type_{a['id']}",
                )
                chart_theme_display = st.selectbox(
                    "Color Scale", COLOR_SCALES, index=0,
                    key=f"my_colorscale_{a['id']}",
                    format_func=lambda x: f"{SCALE_EMOJIS.get(x, '●')} {x}",
                )
                chart_theme = PLOTLY_SCALE_MAP.get(chart_theme_display, chart_theme_display)
                bar_sort = st.radio(":material/sort: Urutan", ["Default", "asc", "desc"], index=0,
                                     key=f"my_sort_{a['id']}", horizontal=True)

                st.markdown("---")
                use_solid_color = st.checkbox(":material/format_paint: Warna Solid (Bar Chart)", value=False, key=f"my_solid_ck_{a['id']}")
                solid_color = st.color_picker("Pilih Warna", value="#4169e1", key=f"my_solid_{a['id']}") if use_solid_color else None

                st.markdown("---")
                st.caption("Label")
                show_count   = st.checkbox("Nilai", value=True, key=f"my_showcount_{a['id']}")
                show_percent = st.checkbox("Persen", value=True, key=f"my_showpercent_{a['id']}")
                show_name    = st.checkbox("Nama", value=False, key=f"my_showname_{a['id']}")
                text_position = st.radio("Posisi Label", ["outside", "inside", "auto"], index=0, horizontal=True, key=f"my_textpos_{a['id']}")
                label_size = st.slider("Ukuran Font", 8, 28, 13, step=1, key=f"my_labelsize_{a['id']}")
                label_bold = st.checkbox("Bold", value=False, key=f"my_labelbold_{a['id']}")

                st.markdown("---")
                show_legend = st.checkbox("Tampilkan Legenda", value=False, key=f"my_legend_ck_{a['id']}")
                if show_legend:
                    legend_pos = st.selectbox(
                        "Posisi Legenda", ["Right", "Bottom", "Top", "Left"], index=0, key=f"my_legend_pos_{a['id']}",
                    )
                    LEGEND_MAP = {
                        "Right":  dict(x=1.02, y=1, xanchor="left", yanchor="top"),
                        "Bottom": dict(x=0.5, y=-0.2, xanchor="center", yanchor="top", orientation="h"),
                        "Top":    dict(x=0.5, y=1.1, xanchor="center", yanchor="bottom", orientation="h"),
                        "Left":   dict(x=-0.2, y=1, xanchor="right", yanchor="top"),
                    }
                    legend_cfg = LEGEND_MAP[legend_pos]
                else:
                    legend_pos = "Right"
                    legend_cfg = {}

                custom_title = st.text_input("Override Judul", value="", placeholder=f"Contoh: {a['column_name']}", key=f"my_title_{a['id']}")
                chart_height = st.slider("Tinggi Chart (px)", 300, 1500, 500, step=50, key=f"my_height_{a['id']}")
                force_light_mode = st.checkbox("Paksa Latar Terang (siap cetak)", key=f"my_light_{a['id']}")

                mc_delimiter = ","
                mc_main_options = None
                if question_type == "multiple_choice":
                    st.markdown("---")
                    mc_delimiter = st.text_input(
                        "Karakter Pemisah (Delimiter)", value=",", key=f"my_delim_{a['id']}",
                        help="Ganti menjadi ';' jika jawaban Anda sendiri mengandung koma."
                    )
                    mc_preview = get_multiple_choice_preview(df[a["column_name"]], delimiter=mc_delimiter)
                    auto_main_options = mc_preview.get("main_names", [])
                    with st.expander(":material/tune: Opsi Terdeteksi (klik untuk edit)", expanded=False):
                        st.caption("Opsi berikut terdeteksi sebagai pilihan utama. Semua jawaban di luar daftar ini akan digabung menjadi **Other**.")
                        custom_main_str = st.text_area(
                            "Opsi Utama (satu per baris)", value="\n".join(auto_main_options),
                            height=150, key=f"my_mc_options_{a['id']}",
                        )
                        mc_main_options = [o.strip() for o in custom_main_str.split("\n") if o.strip()] or None

            chart_title = custom_title if custom_title.strip() else f"{picked_chart} - {a['column_name']}"
            force_light_layout = get_light_plotly_layout() if force_light_mode else None

            built = build_full_chart(
                df, a["column_name"], question_type, chart_type=picked_chart,
                chart_theme=chart_theme, solid_color=solid_color, bar_sort=bar_sort,
                show_count=show_count, show_percent=show_percent, show_name=show_name,
                text_position=text_position, label_size=label_size, label_bold=label_bold,
                show_legend=show_legend, legend_cfg=legend_cfg, chart_title=chart_title,
                chart_height=chart_height, force_light_layout=force_light_layout,
                mc_delimiter=mc_delimiter, mc_main_options=mc_main_options,
            )

            with col_preview:
                if built["fig"] is None or built["result"] is None or built["result"].empty:
                    st.info("Tidak ada data untuk ditampilkan pada kolom ini.")
                else:
                    st.markdown(f"### :material/analytics: {chart_title}")
                    st.plotly_chart(
                        built["fig"], use_container_width=True, config={"displaylogo": False},
                        theme=None if force_light_mode else "streamlit", key=f"my_fig_{a['id']}",
                    )
                    # PERMINTAAN USER: hover pada opsi Color Scale di
                    # dropdown -> chart langsung berubah warna secara
                    # instan (client-side), tanpa perlu klik dulu. Lihat
                    # utils/colorscale_hover.py utk detail cara kerja +
                    # batasan (Treemap/Area/Line di-skip, cuma
                    # Bar/Horizontal Bar/Pie/Donut yg didukung).
                    scale_preview_colors = get_all_scale_preview_colors(built["n_cats"], PLOTLY_SCALE_MAP)
                    render_colorscale_hover_preview(
                        scale_preview_colors, picked_chart, built["colors"],
                        key=f"my_hover_{a['id']}",
                    )

                    # PERMINTAAN USER: tombol generate draft kesimpulan
                    # dengan AI dipindah jadi SATU lokasi saja, tepat di
                    # atas textarea Kesimpulan (lihat bagian form status/
                    # kesimpulan di bawah) -- bukan di sini lagi. Di sini
                    # kita cuma SIMPAN bahan (data_summary, hasil agregat
                    # value/count/percent dari build_full_chart(), BUKAN
                    # dataframe mentah/jawaban individual) ke session_state
                    # supaya tombol di bawah tahu ada bahan siap pakai.
                    display_result_for_ai = built["result"].drop(columns=["_text", "_disp_label"], errors="ignore")
                    st.session_state[f"my_ai_summary_{a['id']}"] = (
                        build_data_summary(display_result_for_ai, built["val_col"], built["count_col"]),
                        question_type,
                    )

                    if st.button("📸 Tampilkan Gambar Statis (Untuk Copy-Paste ke Word)", key=f"my_static_btn_{a['id']}"):
                        try:
                            display_result = built["result"].drop(columns=["_text", "_disp_label"], errors="ignore")
                            png_bytes = generate_matplotlib_chart(
                                chart_type=picked_chart, df=built["result"],
                                val_col=built["val_col"], count_col=built["count_col"],
                                colors=built["colors"],
                                # PERMINTAAN USER: gambar statis TIDAK pakai
                                # judul secara default -- title cuma diisi
                                # kalau user mengisi "Override Judul"
                                # (custom_title non-kosong). Sebelumnya di
                                # sini pakai chart_title, yg selalu berisi
                                # fallback spt "Pie Chart - Fakultas" kalau
                                # custom_title kosong -- itu yg bikin judul
                                # selalu muncul.
                                title=custom_title.strip(),
                                solid_color=solid_color if use_solid_color else None,
                                text_col="_text" if "_text" in built["result"].columns else None,
                                # BUG DIPERBAIKI (dilaporkan user): gambar
                                # statis sebelumnya tidak pernah ikut
                                # menampilkan legenda walau chart interaktif
                                # (Plotly) di atasnya sudah ada legendanya.
                                show_legend=show_legend,
                                legend_pos=legend_pos,
                            )
                            render_copy_button(png_bytes, "Copy Chart PNG", key=f"my_copy_chart_{a['id']}")
                            st.image(png_bytes, caption=f"{chart_title} (Copyable PNG)")
                        except Exception as e:
                            st.error(f"Gagal mem-generate gambar statis. Error: {e}")

                    st.markdown("---")
                    with st.container(border=True):
                        st.markdown("#### :material/table_chart: Data Table Preview")
                        display_result = built["result"].drop(columns=["_text", "_disp_label"], errors="ignore")
                        st.dataframe(display_result, use_container_width=True, hide_index=True)
                        try:
                            table_png = table_to_png(display_result, title="")
                            render_copy_button(table_png, "Copy Table PNG", key=f"my_copy_table_{a['id']}")
                            with st.expander(":material/image: Tampilkan Gambar (Untuk Copy Manual)"):
                                st.info("Klik kanan pada gambar di bawah dan pilih **Copy Image** atau **Save Image As**.")
                                st.image(table_png)
                        except Exception as e:
                            st.warning(f":material/warning: Gagal membuat gambar tabel: {e}")

                    st.markdown("### :material/download: Ekspor Data")
                    xlsx_data = df_to_xlsx_bytes(display_result)
                    st.download_button(
                        label=":material/table: Download Tabel (XLSX)",
                        data=xlsx_data,
                        file_name=f"{a['column_name']}_analisis.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"my_xlsx_{a['id']}",
                    )

        st.markdown("---")

        status_options = ["belum_dikerjakan", "dikerjakan", "selesai"]
        current_status = a.get("status") or "belum_dikerjakan"
        new_status = st.selectbox(
            "Status pengerjaan", status_options,
            index=status_options.index(current_status),
            key=f"my_status_{a['id']}",
        )
        # PENTING (pitfall Streamlit yang mudah terlewat): kalau widget
        # dgn `key` tertentu SUDAH PERNAH dirender sebelumnya di sesi ini,
        # parameter `value=` pada render BERIKUTNYA diabaikan Streamlit —
        # widget akan selalu pakai nilai dari session_state[key] miliknya
        # sendiri, BUKAN value= yang baru kita kasih. Fix: set
        # session_state[key] SECARA LANGSUNG SEBELUM widget dibuat.
        conclusion_key = f"my_conclusion_{a['id']}"
        if conclusion_key not in st.session_state:
            st.session_state[conclusion_key] = a.get("conclusion_text") or ""

        # PITFALL KEDUA (ditemukan lewat testing browser sungguhan): kalau
        # tombol "Generate dengan AI" ditaruh SETELAH text_area (sesuai
        # permintaan user: tombol di BAWAH textarea), maka pada saat tombol
        # diklik widget text_area SUDAH ter-instantiated di run itu -->
        # `st.session_state[conclusion_key] = text` LANGSUNG di sini akan
        # crash StreamlitAPIException ("cannot be modified after the widget
        # ... is instantiated"). Fix: simpan draft ke key SEMENTARA lalu
        # st.rerun() -- di run BERIKUTNYA (baris "if conclusion_key not in
        # st.session_state" TIDAK relevan lagi, ganti jadi override
        # eksplisit dari draft sementara) widget belum ter-instantiated
        # sama sekali, jadi aman ditulis.
        pending_draft_key = f"my_ai_pending_draft_{a['id']}"
        if pending_draft_key in st.session_state:
            st.session_state[conclusion_key] = st.session_state.pop(pending_draft_key)

        conclusion = st.text_area(
            "Kesimpulan (isi di sini, tidak perlu dokumen terpisah lagi)",
            key=conclusion_key,
            height=120,
        )

        ai_summary_key = f"my_ai_summary_{a['id']}"
        if ai_summary_key in st.session_state:
            if st.button(":material/auto_awesome: Generate Draft Kesimpulan dengan AI", key=f"my_ai_gen_{a['id']}"):
                data_summary, ai_question_type = st.session_state[ai_summary_key]
                with st.spinner("Menyusun draft narasi..."):
                    success, text = generate_conclusion_draft(a["column_name"], data_summary, ai_question_type)
                if success:
                    st.session_state[pending_draft_key] = text
                    st.success("Draft berhasil dibuat di atas! Cek & edit sebelum Simpan.")
                    st.rerun()
                else:
                    st.error(f":material/error: {text}")

        if st.button(":material/save: Simpan", key=f"my_save_{a['id']}", type="primary"):
            update_assignment_progress(a["id"], new_status, conclusion)
            log_action(user["username"], user["role"], "update_assignment", f"'{a['column_name']}' status={new_status}")
            st.success("Tersimpan!")
            st.rerun()

render_sidebar_footer()
render_page_footer()
