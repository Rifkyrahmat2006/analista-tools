import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from io import BytesIO

# ── Legacy imports (for tab_basic — jangan diubah) ──────────────────────────
from utils.nlp_clustering import (
    preprocess_for_clustering,
    get_tfidf_matrix,
    find_optimal_k,
    run_kmeans,
    get_top_keywords as get_cluster_keywords,
    get_representative_docs,
)
from utils.pivot_analysis import single_choice_analysis, scale_analysis, scale_statistics, cross_tabulation, get_single_choice_preview
from utils.multi_select_analysis import multi_choice_analysis, multi_choice_combinations, get_multiple_choice_preview
from utils.text_analysis import analyze_text_column, get_top_keywords
from utils.export_helpers import table_to_png
from utils.question_detection import detect_question_type, analyze_column_features
from utils.theme import inject_theme_css, get_light_plotly_layout, render_sidebar_footer, render_page_footer

# ── New Open-Ended Analysis imports ─────────────────────────────────────────
from utils.open_ended_config import (
    NORMALIZATION_DICT,
    DOMAIN_SURVEY_STOPWORDS,
    MEANINGLESS_PATTERNS,
    AMBIGUOUS_EXACT_MATCHES,
)
from utils.open_ended_preprocessing import (
    validate_responses,
    get_validation_summary,
    preprocess_pipeline,
    detect_duplicate_texts,
    get_valid_texts_for_clustering,
    get_original_texts_for_display,
)
from utils.open_ended_state import (
    init_oe_state,
    reset_oe_analysis,
    reset_oe_full,
    compute_params_hash,
    create_analysis_run,
    create_candidate_groups_from_clustering,
    validate_group,
    merge_groups,
    split_group,
    move_response,
    delete_group,
    mark_group_as_other,
    build_final_mapping,
    compute_theme_frequency,
    run_quality_checks,
    finalize_analysis,
    add_audit_entry,
    get_audit_log_df,
    generate_narrative,
    CandidateGroup,
)
from utils.nlp_clustering import (
    get_tfidf_matrix as get_tfidf_matrix_new,
    evaluate_cluster_range,
    get_recommended_k,
    run_kmeans as run_kmeans_new,
    run_agglomerative,
    run_dbscan,
    get_top_keywords_from_centroids,
    get_top_keywords_for_labels,
    get_top_phrases_per_cluster,
    get_representative_responses,
)
from utils.export_helpers import export_oe_analysis
from utils.open_ended_state import generate_narrative

from utils.oe_question_profiler import profile_question, get_all_modes_for_selectbox, MODE_LABELS
from utils.concept_analysis import run_concept_analysis, get_concept_summary_df, get_cooccurrence_df
from utils.oe_results_builder import build_concept_result, build_thematic_result, build_multilabel_result, result_to_summary_df
from utils.open_ended_config import CONCEPT_FAMILIES

st.set_page_config(page_title="Analysis", layout="wide")

inject_theme_css()

# Initialize open-ended state
init_oe_state()

# Custom Plotly color sequence (to keep brand colors)
PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
LIGHT_LAYOUT = get_light_plotly_layout()

STATUS_COLORS = {
    "Draft": "#94a3b8",
    "Needs Review": "#f59e0b",
    "Validated": "#22c55e",
}

with st.sidebar:
    st.markdown("### :material/print: Export Settings")
    force_light_mode = st.checkbox(
        "Paksa Chart Terang",
        help="Aktifkan agar chart Plotly berlatar putih. Sangat berguna sebelum Anda mengunduh chart (logo kamera) agar hasil download siap cetak."
    )

    if st.button("Reset Pengaturan Kolom", use_container_width=True):
        st.session_state.question_types = {}
        st.rerun()

st.markdown("# :material/trending_up: Analysis")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning(":material/warning: Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

tab_basic, tab_thematic = st.tabs(['Analisis Dasar', 'Analisis Tematik (NLP)'])

# ===========================================================================
# TAB BASIC — TIDAK DIUBAH
# ===========================================================================
with tab_basic:

    # --------------- Question Type Configuration ---------------
    st.markdown("### :material/bar_chart: Hasil Analisis")
    st.caption("Konfigurasi tipe setiap kolom untuk menyesuaikan analisis yang dihasilkan. Tipe terdeteksi otomatis — Anda bisa mengubahkan secara manual.")

    TYPE_OPTIONS = ["skip", "single_choice", "multiple_choice", "scale", "open_text"]

    if "question_types" not in st.session_state:
        st.session_state.question_types = {}

    # Pre-compute detections (cached per dataset to avoid re-running)
    if "detected_types" not in st.session_state or st.session_state.get("_det_id") != id(df):
        st.session_state.detected_types = {}
        st.session_state.detected_features = {}
        for col in df.columns:
            st.session_state.detected_types[col] = detect_question_type(df[col])
            st.session_state.detected_features[col] = analyze_column_features(df[col])
        st.session_state._det_id = id(df)

    # Callback to fix double-render issue on selectbox
    def update_qtype(c_name):
        st.session_state.question_types[c_name] = st.session_state[f"qtype_{c_name}"]

    # Show configuration in a vertical block layout
    search_q = st.text_input(":material/search: Cari Pertanyaan...", placeholder="Ketik kata kunci pertanyaan...", key="search_config")

    # Pre-filter columns based on search
    filtered_cols = [col for col in df.columns if not search_q or search_q.lower() in col.lower()]

    if not filtered_cols:
        st.info("Tidak ada pertanyaan yang cocok dengan pencarian.")
    else:
        # ---------------- Pagination Logic ----------------
        ITEMS_PER_PAGE = 10
        total_pages = max(1, (len(filtered_cols) - 1) // ITEMS_PER_PAGE + 1)

        if "analysis_page_num" not in st.session_state:
            st.session_state.analysis_page_num = 1

        # Ensure current page is valid (e.g. if search narrows results)
        if st.session_state.analysis_page_num > total_pages:
            st.session_state.analysis_page_num = total_pages

        current_page = st.session_state.analysis_page_num

        # Top Pagination Controls
        if total_pages > 1:
            st.markdown("<br>", unsafe_allow_html=True)
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if st.button("Sebelumnya", icon=":material/arrow_back:", disabled=current_page <= 1, use_container_width=True, key="prev_top"):
                    st.session_state.analysis_page_num -= 1
                    st.rerun()
            with pc2:
                st.markdown(f"<p style='text-align: center; margin-top: 10px;'>Halaman <b>{current_page}</b> dari <b>{total_pages}</b> ({len(filtered_cols)} pertanyaan)</p>", unsafe_allow_html=True)
            with pc3:
                if st.button("Selanjutnya", icon=":material/arrow_forward:", disabled=current_page >= total_pages, use_container_width=True, key="next_top"):
                    st.session_state.analysis_page_num += 1
                    st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        # Calculate slice
        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        paginated_cols = filtered_cols[start_idx:end_idx]

        for col_name in paginated_cols:

            suggested = st.session_state.detected_types.get(col_name, "skip")
            current_val = st.session_state.question_types.get(col_name, suggested)
            default_idx = TYPE_OPTIONS.index(current_val) if current_val in TYPE_OPTIONS else 0

            with st.container(border=True):
                # Block style header
                c1, c2 = st.columns([3, 1])

                with c1:
                    st.markdown(f"**{col_name}**")
                with c2:
                    st.selectbox(
                        "Tipe Pertanyaan",
                        options=TYPE_OPTIONS,
                        index=default_idx,
                        key=f"qtype_{col_name}",
                        label_visibility="collapsed",
                        on_change=update_qtype,
                        args=(col_name,)
                    )

                st.markdown("<br>", unsafe_allow_html=True)

                # ----------------- Configuration & Previews -----------------
                if current_val in ["multiple_choice", "single_choice"]:
                    if current_val == "multiple_choice":
                        prev_data = get_multiple_choice_preview(df[col_name])
                    else:
                        prev_data = get_single_choice_preview(df[col_name])

                    ms_key = f"mainopts_{col_name}"
                    hd_key = f"hiddenpts_{col_name}"
                    # Initialize states
                    if ms_key not in st.session_state:
                        st.session_state[ms_key] = prev_data.get("main_names", []).copy()
                    if hd_key not in st.session_state:
                        st.session_state[hd_key] = set()

                    current_mains = st.session_state[ms_key]
                    current_hiddens = st.session_state[hd_key]

                    # Show current Main Options
                    st.caption("Options preview:")
                    counts_dict = prev_data.get("counts", {})
                    for opt in current_mains.copy():
                        r1, r_hide, r_del = st.columns([0.85, 0.05, 0.05])
                        count_val = counts_dict.get(opt, 0)

                        is_hidden = opt in current_hiddens

                        with r1:
                            strike = "~~" if is_hidden else ""
                            st.markdown(f"{strike}● {opt} ({count_val}){strike}")
                        with r_hide:
                            eye_icon = ":material/visibility_off:" if is_hidden else ":material/visibility:"
                            if st.button(" ", icon=eye_icon, help="Sembunyikan Opsi", type="secondary", key=f"hide_{col_name}_{opt}"):
                                if is_hidden:
                                    st.session_state[hd_key].remove(opt)
                                else:
                                    st.session_state[hd_key].add(opt)
                                st.rerun()
                        with r_del:
                            if st.button(" ", icon=":material/delete:", help="Hapus Opsi", type="secondary", key=f"del_{col_name}_{opt}"):
                                st.session_state[ms_key].remove(opt)
                                if opt in st.session_state[hd_key]:
                                    st.session_state[hd_key].remove(opt)
                                st.rerun()

                    # Identify Others
                    other_opts = [o for o in prev_data.get("all", []) if o not in current_mains]
                    other_count = sum(counts_dict.get(o, 0) for o in other_opts)

                    if other_count > 0:
                        or1, or_hide, or_del = st.columns([0.85, 0.05, 0.05])
                        is_other_hidden = "Other" in current_hiddens
                        with or1:
                            strike = "~~" if is_other_hidden else ""
                            st.markdown(f"{strike}◯ **Other** ({other_count}){strike}")
                        with or_hide:
                            eye_icon = ":material/visibility_off:" if is_other_hidden else ":material/visibility:"
                            if st.button(" ", icon=eye_icon, help="Sembunyikan Opsi", type="secondary", key=f"hide_{col_name}_Other"):
                                if is_other_hidden:
                                    st.session_state[hd_key].remove("Other")
                                else:
                                    st.session_state[hd_key].add("Other")
                                st.rerun()
                        with or_del:
                            # Provide an empty column for visual consistency
                            pass

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Interactive 'Other' list
                    if other_opts:
                        with st.expander("Other responses detailed:"):
                            for oth in other_opts:
                                count_val = counts_dict.get(oth, 0)
                                orq1, orq2 = st.columns([0.95, 0.05])
                                with orq1:
                                    st.markdown(f"• {oth} ({count_val})")
                                with orq2:
                                    if st.button(" ", icon=":material/add:", help="Pindahkan ke Opsi Utama", type="secondary", key=f"add_oth_{col_name}_{oth}"):
                                        st.session_state[ms_key].append(oth)
                                        st.rerun()

                    # Add option manual input
                    st.markdown("<br>", unsafe_allow_html=True)
                    c_add1, c_add2 = st.columns([0.8, 0.2])
                    with c_add1:
                        new_opt = st.text_input("Add option", key=f"txt_{col_name}", label_visibility="collapsed", placeholder="Ketik opsi manual yang ingin dipindahkan dari Other...")
                    with c_add2:
                        if st.button("Tambahkan", icon=":material/add_circle:", use_container_width=True, key=f"btn_add_{col_name}"):
                            all_opts = prev_data.get("all", [])
                            if new_opt and new_opt not in current_mains and new_opt in all_opts:
                                st.session_state[ms_key].append(new_opt)
                                st.rerun()
                            elif new_opt and new_opt not in all_opts:
                                st.warning("Opsi tidak ditemukan pada data kolom ini.")

                elif current_val == "scale":
                    st.caption("Distribution Preview:")
                    prev_data = df[col_name].value_counts().sort_index()
                    for val, count in prev_data.items():
                        st.markdown(f"• **{val}** : {count}")

                # Handle Open Text
                elif current_val == "open_text":
                    pass

                st.markdown("---")

                # ----------------- Render Chart Analytics -----------------
                if current_val == "single_choice":
                    main_opts = st.session_state.get(f"mainopts_{col_name}", [])
                    hidden_opts = st.session_state.get(f"hiddenpts_{col_name}", set())
                    result = single_choice_analysis(df, col_name, main_options=main_opts)

                    # Filter hidden
                    result = result[~result['Value'].isin(hidden_opts)]

                    col_table, col_chart = st.columns([1, 2])
                    with col_table:
                        st.markdown("#### :material/table_chart: Tabel Frekuensi")
                        st.dataframe(result, use_container_width=True, hide_index=True)

                    with col_chart:
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

                elif current_val == "scale":
                    result = scale_analysis(df, col_name)
                    stats = scale_statistics(df, col_name)

                    col_stats, col_chart = st.columns([1, 2])
                    with col_stats:
                        st.markdown("#### :material/table_chart: Distribusi")
                        st.dataframe(result, use_container_width=True, hide_index=True)

                        st.markdown("#### :material/bar_chart: Statistik")
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

                elif current_val == "multiple_choice":
                    main_opts = st.session_state.get(f"mainopts_{col_name}", [])
                    hidden_opts = st.session_state.get(f"hiddenpts_{col_name}", set())
                    result = multi_choice_analysis(df, col_name, main_options=main_opts)

                    # Filter hidden
                    result = result[~result['Value'].isin(hidden_opts)]

                    col_table, col_chart = st.columns([1, 2])
                    with col_table:
                        st.markdown("#### :material/table_chart: Frekuensi Jawaban")
                        st.dataframe(result, use_container_width=True, hide_index=True)

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

                elif current_val == "open_text":
                    analysis = analyze_text_column(df, col_name)
                    top_kw = get_top_keywords(analysis["word_freq"], top_n=15)

                    col_stats, col_chart = st.columns([1, 2])
                    with col_stats:
                        st.markdown("#### :material/bar_chart: Statistik Teks")
                        st.metric("Total Respons", analysis["total_responses"])
                        st.metric("Total Kata", analysis["total_words"])
                        st.metric("Kata Unik", analysis["unique_words"])

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

                    st.caption(":material/lightbulb: Untuk wordcloud lengkap, kunjungi tab **:material/cloud: Wordcloud** di halaman **Visualization**")

        # Bottom Pagination Controls (Only if multiple pages exist)
        if total_pages > 1:
            st.markdown("---")
            bc1, bc2, bc3 = st.columns([1, 2, 1])
            with bc1:
                if st.button("Sebelumnya", icon=":material/arrow_back:", disabled=current_page <= 1, use_container_width=True, key="prev_bot"):
                    st.session_state.analysis_page_num -= 1
                    st.rerun()
            with bc2:
                st.markdown(f"<p style='text-align: center; margin-top: 10px;'>Halaman <b>{current_page}</b> dari <b>{total_pages}</b></p>", unsafe_allow_html=True)
            with bc3:
                if st.button("Selanjutnya", icon=":material/arrow_forward:", disabled=current_page >= total_pages, use_container_width=True, key="next_bot"):
                    st.session_state.analysis_page_num += 1
                    st.rerun()


# ===========================================================================
# TAB THEMATIC — SEMI-AUTOMATIC OPEN-ENDED RESPONSE CODING & CATEGORIZATION
# ===========================================================================
with tab_thematic:
    st.markdown("### :material/manage_search: Analisis Tematik Pertanyaan Terbuka")
    st.caption(
        "**Semi-Automatic Open-Ended Response Coding & Categorization** — "
        "Sistem membantu mengidentifikasi kandidat pola jawaban secara otomatis. "
        "**Keputusan substantif (nama tema, kesamaan konsep) sepenuhnya di tangan analis.**"
    )

    text_columns = df.select_dtypes(include=['object']).columns.tolist()

    if not text_columns:
        st.warning("Tidak ada kolom teks dalam dataset ini.")
        st.stop()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: PILIH PERTANYAAN & DATA QUALITY ASSESSMENT
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander(":material/assignment: Langkah 1 — Pilih Pertanyaan & Quality Assessment", expanded=True):
        prev_col = st.session_state.get("oe_target_col")
        target_col = st.selectbox(
            "Pilih Kolom Pertanyaan Terbuka",
            text_columns,
            key="oe_col_selector",
            help="Pilih kolom yang berisi jawaban terbuka untuk dianalisis.",
        )

        # Deteksi perubahan kolom → reset state
        if target_col != prev_col:
            reset_oe_full(reason=f"column_changed_to_{target_col}")
            st.session_state["oe_target_col"] = target_col
            st.session_state["oe_validated_df"] = None

        # Jalankan validasi jika belum ada
        if st.session_state.get("oe_validated_df") is None:
            with st.spinner("Memvalidasi respons..."):
                validated_df = validate_responses(df[target_col])
                validated_df = detect_duplicate_texts(validated_df)
                st.session_state["oe_validated_df"] = validated_df

        validated_df = st.session_state["oe_validated_df"]
        summary = get_validation_summary(validated_df)

        st.markdown("#### :material/bar_chart: Ringkasan Kualitas Data")
        
        # Hitung Classified/Unclassified jika ada candidate groups
        classified_valid = 0
        unclassified_valid = 0
        coverage_pct = 0.0
        if st.session_state.get("oe_candidate_groups"):
            all_mapped_ids = []
            for g in st.session_state["oe_candidate_groups"].values():
                all_mapped_ids.extend(g.response_ids)
            classified_valid = len(set(all_mapped_ids))
            unclassified_valid = summary["valid"] - classified_valid
            coverage_pct = (classified_valid / summary["valid"] * 100) if summary["valid"] > 0 else 0.0

        # Susun metric secara konsisten
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Responses", summary["total"])
        col_m2.metric("✅ Valid", summary["valid"])
        col_m3.metric("⬜ Missing", summary["missing"])
        col_m4.metric("⚠️ Low-Info", summary.get("low_information", summary.get("ambiguous", 0)))
        
        if st.session_state.get("oe_candidate_groups"):
            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            col_c1.metric("📦 Classified Valid", classified_valid)
            col_c2.metric("❓ Unclassified Valid", unclassified_valid)
            col_c3.metric("📊 Coverage", f"{coverage_pct:.1f}%")
            col_c4.metric("❌ Meaningless", summary["meaningless"])
        else:
            st.metric("❌ Meaningless", summary["meaningless"])

        # Duplikasi
        dup_count = validated_df["is_duplicate_text"].sum()
        if dup_count > 0:
            st.info(f":material/content_copy: **{dup_count} respons** memiliki teks identik dengan respons lain. Duplikasi tidak otomatis dihapus — responden yang berbeda dapat memberikan jawaban yang sama.")

        # Tampilkan respons ambigu untuk keputusan analis
        low_info_df = validated_df[
            validated_df["validation_status"].isin(["low_information", "ambiguous"])
        ]
        if not low_info_df.empty:
            with st.container(border=True):
                st.markdown(f"**{len(low_info_df)} Respons Low-Information — Review diperlukan**")
                st.caption("Respons low-information memiliki makna tetapi terlalu umum untuk menentukan tema. Analis dapat memutuskan apakah diikutkan dalam analisis, dijadikan 'Other', atau diabaikan.")

                ambiguous_decisions = st.session_state.get("oe_ambiguous_decisions", {})
                updated_decisions = {}

                for _, row in low_info_df.iterrows():
                    resp_id = row["response_id"]
                    original = row["original_text"]
                    current_dec = ambiguous_decisions.get(resp_id, "ignore")

                    col_txt, col_dec = st.columns([3, 1])
                    with col_txt:
                        st.markdown(f"*\"{original}\"*")
                    with col_dec:
                        decision = st.selectbox(
                            "Keputusan",
                            ["ignore", "valid", "other"],
                            index=["ignore", "valid", "other"].index(current_dec),
                            key=f"ambig_{resp_id}",
                            label_visibility="collapsed",
                        )
                        updated_decisions[resp_id] = decision

                if st.button(":material/save: Simpan Keputusan Respons Ambigu", key="save_ambig"):
                    st.session_state["oe_ambiguous_decisions"] = updated_decisions
                    # Update validation status sesuai keputusan analis
                    for resp_id, decision in updated_decisions.items():
                        mask = validated_df["response_id"] == resp_id
                        if decision == "valid":
                            st.session_state["oe_validated_df"].loc[mask, "validation_status"] = "valid"
                        elif decision == "other":
                            st.session_state["oe_validated_df"].loc[mask, "validation_status"] = "other_decided"
                    st.success("Keputusan disimpan!")
                    st.rerun()

        if summary["valid"] < 2:
            st.error(":material/error: Tidak cukup respons valid untuk dilakukan analisis (minimum 2 respons valid).")
        
        # --- SELEKSI MODE ANALISIS ---
        st.markdown("---")
        st.markdown("#### :material/tune: Pilih Mode Analisis")
        st.caption("Pilih mode analisis yang paling sesuai dengan intent dan struktur pertanyaan survei Anda.")

        if st.session_state.get("oe_analysis_mode") is None:
            st.session_state["oe_analysis_mode"] = "thematic"
            
        current_mode = st.session_state["oe_analysis_mode"]

        # Selector utama di atas
        all_modes = get_all_modes_for_selectbox()
        mode_keys = [m[0] for m in all_modes]
        idx = mode_keys.index(current_mode) if current_mode in mode_keys else 0

        selected_mode = st.selectbox(
            "Mode Analisis Aktif:",
            options=mode_keys,
            format_func=lambda x: MODE_LABELS.get(x, x),
            index=idx,
            key="oe_mode_select_active"
        )

        if selected_mode != current_mode:
            st.session_state["oe_analysis_mode"] = selected_mode
            reset_oe_analysis(reason=f"mode_changed_to_{selected_mode}")
            st.rerun()

        # Render Kartu Penjelasan Semua Mode untuk Transparansi
        st.markdown("##### :material/menu_book: Katalog & Panduan Transparansi Mode Analisis")

        mode_info_dict = {
            "concept": {
                "title": "Concept / Option Analysis",
                "badge": ":material/label: Ekstraksi Konsep",
                "pengertian": "Ekstraksi opsi, metode, bidang, atau kategori spesifik yang berulang.",
                "tujuan": "Memetakan respons bebas menjadi daftar opsi baku (mirip pilihan ganda multi-label).",
                "flow": "Dictionary Extraction ➔ Fuzzy Keyword Matching ➔ Multi-label Mapping (Tanpa Clustering)",
                "contoh_q": "Metode pengembangan diri apa yang efektif? (misal: simulasi, project, dll)",
                "contoh_r": "Simulasi (40%), Project (30%), Workshop (10%)"
            },
            "barrier": {
                "title": "Barrier Analysis",
                "badge": ":material/block: Analisis Hambatan",
                "pengertian": "Pengelompokan kendala, masalah, kesulitan, atau hambatan.",
                "tujuan": "Mengidentifikasi secara sistematis akar permasalahan dan keluhan utama responden.",
                "flow": "Sub-Response Splitting (Kata Hubung) ➔ TF-IDF Vectorization ➔ K-Means Clustering ➔ Auto-Merge & Purge",
                "contoh_q": "Apa saja yang menghambat mahasiswa untuk aktif berorganisasi?",
                "contoh_r": "Keterbatasan Waktu (35%), Kurang Percaya Diri (20%), Masalah Biaya (15%)"
            },
            "reason": {
                "title": "Reason Analysis",
                "badge": ":material/help_outline: Analisis Alasan",
                "pengertian": "Pengelompokan latar belakang, alasan, atau motivasi yang bervariasi.",
                "tujuan": "Memahami faktor pendorong atau penyebab suatu fenomena/pilihan.",
                "flow": "Sub-Response Splitting (Kata Hubung) ➔ TF-IDF Vectorization ➔ K-Means Clustering ➔ Auto-Merge & Purge",
                "contoh_q": "Mengapa Anda jarang menggunakan fasilitas perpustakaan kampus?",
                "contoh_r": "Jarak Rumah Jauh (25%), Koleksi Buku Kurang Lengkap (20%)"
            },
            "recommendation": {
                "title": "Recommendation Analysis",
                "badge": ":material/campaign: Analisis Saran",
                "pengertian": "Pengelompokan usulan, masukan, harapan, atau rekomendasi perbaikan.",
                "tujuan": "Meringkas feedback konstruktif menjadi poin-poin saran yang dapat dieksekusi.",
                "flow": "Sub-Response Splitting (Kata Hubung) ➔ TF-IDF Vectorization ➔ K-Means Clustering ➔ Auto-Merge & Purge",
                "contoh_q": "Apa saran Anda untuk perbaikan layanan kemahasiswaan tahun depan?",
                "contoh_r": "Peningkatan Layanan Digital (40%), Penambahan Kuota Beasiswa (30%)"
            },
            "evaluation": {
                "title": "Evaluation Analysis",
                "badge": ":material/grade: Analisis Evaluasi",
                "pengertian": "Pengelompokan penilaian, impresi, atau evaluasi kualitatif.",
                "tujuan": "Mengetahui aspek spesifik yang disukai atau tidak disukai (sentimen berbasis aspek).",
                "flow": "Aspect Sentiment Extraction ➔ TF-IDF Vectorization ➔ K-Means Clustering ➔ Auto-Merge & Purge",
                "contoh_q": "Bagaimana pendapat Anda tentang program kepemimpinan ini?",
                "contoh_r": "Materi Sangat Relevan (45%), Mentor Kurang Responsif (15%)"
            },
            "thematic": {
                "title": "General Thematic Analysis",
                "badge": ":material/psychology: Analisis Tematik Umum",
                "pengertian": "Pengelompokan opini bebas atau pandangan umum tanpa kerangka asumsi spesifik.",
                "tujuan": "Mengekstrak ide dan tema-tema utama (makro) dari teks panjang yang bervariasi.",
                "flow": "Full Response TF-IDF Vectorization ➔ Benchmark K-Means / HDBSCAN ➔ Macro-Theme Aggregation",
                "contoh_q": "Apa pendapat Anda secara umum mengenai isu lingkungan di kampus?",
                "contoh_r": "Kurangnya Tempat Sampah Daur Ulang (30%), Kebijakan Kampus Kurang Tegas (20%)"
            }
        }

        # Render 6 kartu dalam 3 kolom (2 baris)
        cols = st.columns(3)
        mode_keys_list = list(mode_info_dict.keys())

        for idx_m, m_key in enumerate(mode_keys_list):
            info = mode_info_dict[m_key]
            is_active = (m_key == selected_mode)
            
            card_col = cols[idx_m % 3]
            
            with card_col:
                with st.container(border=True):
                    if is_active:
                        st.markdown(f"**{info['badge']}** &nbsp; <span style='background:#22c55e; color:white; padding:2px 8px; border-radius:10px; font-size:0.5em;'>AKTIF</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{info['badge']}**", unsafe_allow_html=True)
                    
                    st.caption(f"**Pengertian:** {info['pengertian']}<br>**Tujuan:** {info['tujuan']}", unsafe_allow_html=True)
                    st.caption(f":material/account_tree: **Flow:** `{info['flow']}`")
                    st.caption(f"**Cth Tanya:** *\"{info['contoh_q']}\"*<br>**Cth Hasil:** {info['contoh_r']}", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: KONFIGURASI ANALISIS
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander(":material/settings: Langkah 2 — Konfigurasi Analisis", expanded=not st.session_state.get("oe_processing_done", False)):
        cfg_col1, cfg_col2 = st.columns(2)

        with cfg_col1:
            st.markdown("**Preprocessing**")
            use_stemming = st.checkbox("Gunakan Stemming (Sastrawi)", value=True, key="oe_use_stemming",
                                       help="Stem setiap kata untuk menggabungkan variasi bentukan kata.")
            use_domain_sw = st.checkbox("Gunakan Domain Stopwords Survei", value=True, key="oe_use_domain_sw",
                                        help="Filter kata filler survei (semoga, mudah-mudahan, kedepannya, dll).")
            extra_sw_input = st.text_input("Stopwords Tambahan (pisahkan koma)", key="oe_extra_sw",
                                           placeholder="tambahkan, kata, filler, spesifik",
                                           help="Tambahkan kata yang ingin Anda filter secara spesifik untuk dataset ini.")

            import re
            from utils.open_ended_preprocessing import INDONESIAN_BASE_STOPWORDS
            default_context = re.sub(r'[^\w\s]', '', target_col).lower().strip() if target_col else ""
            default_context_words = ", ".join([w for w in default_context.split() if w not in INDONESIAN_BASE_STOPWORDS])
            context_sw_input = st.text_input("Kata Konteks Pertanyaan (Context Words)", 
                                           value=default_context_words,
                                           key="oe_context_sw",
                                           help="Kata dari pertanyaan yang sering diucapkan responden. Akan dievaluasi sebagai konteks, bukan tema.")
            st.caption("Context words & Domain Stopwords akan **dibuang sepenuhnya** dari vocabulary TF-IDF.")

            with st.container(border=True):
                st.markdown("**Domain Stopwords saat ini:**")
                st.caption("(dapat diedit di `utils/open_ended_config.py`)")
                sw_display = ", ".join(sorted(DOMAIN_SURVEY_STOPWORDS)[:30])
                st.caption(sw_display + " ...")

        with cfg_col2:
            current_mode = st.session_state.get("oe_analysis_mode", "thematic")
            is_concept_mode = (current_mode == "concept")

            if is_concept_mode:
                st.markdown("**Concept Extraction Engine**")
                st.info("Mode ini menggunakan dictionary-based concept extraction. Clustering tidak diperlukan.")
                clustering_mode = "Auto (Benchmark 3 Metode)"
                random_state = 42
                max_features = 1500
                algorithm = clustering_mode
            else:
                st.markdown("**Vectorizer & Clustering Engine**")
                clustering_mode = st.radio(
                    "Metode Pengelompokan",
                    ["Auto (Benchmark 3 Metode)", "K-Means (Custom K)", "Manual Coding Only"],
                    horizontal=True,
                    key="oe_clustering_mode",
                    help="Auto akan membandingkan K-Means, Agglomerative, dan DBSCAN. Custom K memungkinkan Anda menentukan jumlah kelompok pasti."
                )

                if clustering_mode == "K-Means (Custom K)":
                    custom_k = st.number_input("Target Jumlah Kelompok (K)", min_value=2, max_value=50, value=10, step=1, key="oe_custom_k")
                else:
                    custom_k = 10

                random_state = st.number_input("Random State", value=42, key="oe_random_state",
                                               help="Untuk reproduksibilitas hasil clustering.")
                max_features = st.number_input("Max TF-IDF Features", value=1500, min_value=100, max_value=5000,
                                               key="oe_max_features",
                                               help="Jumlah maksimum fitur TF-IDF. Lebih besar = lebih akurat tapi lebih lambat.")
                
                algorithm = f"{clustering_mode} (K={custom_k})" if clustering_mode == "K-Means (Custom K)" else clustering_mode

            # Legacy variables compatibility
            eps_val, min_samp_val, manual_k = 0, 0, 0

        # Compute current params hash
        extra_sw_str = st.session_state.get("oe_extra_sw", "")
        current_hash = compute_params_hash(
            col=target_col,
            use_stemming=use_stemming,
            use_domain_sw=use_domain_sw,
            extra_sw=extra_sw_str,
            algorithm=algorithm,
            n_clusters=0,
            random_state=random_state,
            max_features=max_features,
            min_df=0,
        )
        prev_hash = st.session_state.get("oe_last_params_hash")
        params_changed = (prev_hash is not None) and (current_hash != prev_hash) and st.session_state.get("oe_processing_done", False)

        if params_changed:
            st.warning(":material/warning: Parameter berubah. Jalankan ulang analisis untuk membuat Analysis Run baru. Hasil sebelumnya tidak dihapus.")

        if st.button(":material/play_circle: Jalankan Analisis", type="primary", use_container_width=True, key="oe_run_btn"):
            validated_df_curr = st.session_state.get("oe_validated_df")
            if validated_df_curr is None:
                st.error("Validasi respons belum selesai.")
            else:
                valid_count = (validated_df_curr["validation_status"] == "valid").sum()
                if valid_count < 2:
                    st.error("Tidak cukup respons valid (minimum 2).")
                else:
                    with st.spinner("Menjalankan preprocessing dan clustering..."):
                        try:
                            # Reset analysis state (keep validated_df)
                            reset_oe_analysis(reason="new_run")
                            st.session_state["oe_validated_df"] = validated_df_curr

                            # Extra stopwords
                            extra_sw_str = st.session_state.get("oe_extra_sw", "")
                            extra_sw_set = {w.strip().lower() for w in extra_sw_str.split(",") if w.strip()} if extra_sw_str else set()
                            
                            # Context stopwords
                            context_sw_str = st.session_state.get("oe_context_sw", "")
                            context_sw_list = [w.strip() for w in context_sw_str.split(",") if w.strip()]
                            
                            use_domain_sw = st.session_state.get("oe_use_domain_sw", True)
                            use_stemming = st.session_state.get("oe_use_stemming", True)
                            
                            from utils.open_ended_preprocessing import preprocess_pipeline
                            
                            preprocessed_df = preprocess_pipeline(
                                validated_df=validated_df_curr,
                                use_stemming=use_stemming,
                                use_domain_stopwords=use_domain_sw,
                                extra_stopwords=extra_sw_set,
                            )
                            st.session_state["oe_preprocessed_df"] = preprocessed_df
                            
                            current_mode = st.session_state.get("oe_analysis_mode", "thematic")
                            is_concept_mode = (current_mode == "concept")
                            is_multilabel_thematic = current_mode in ["barrier", "reason", "recommendation"]
                            
                            from utils.open_ended_preprocessing import get_valid_texts_for_clustering
                            processed_texts, resp_ids = get_valid_texts_for_clustering(
                                preprocessed_df, 
                                is_multilabel=is_multilabel_thematic
                            )
                            
                            if len(processed_texts) < 2:
                                st.error("Setelah preprocessing, tidak ada teks yang cukup untuk analisis. Coba kurangi domain stopwords.")
                            else:
                                if is_concept_mode:
                                    # --- CONCEPT / MULTI-LABEL ANALYSIS PIPELINE ---
                                    st.session_state["oe_resp_ids_for_clustering"] = resp_ids
                                    
                                    # Setup stopwords
                                    domain_sw_set = DOMAIN_SURVEY_STOPWORDS if use_domain_sw else set()
                                    domain_sw_set = domain_sw_set | extra_sw_set
                                    
                                    concept_res = run_concept_analysis(
                                        texts=processed_texts,
                                        response_ids=resp_ids,
                                        concept_families=CONCEPT_FAMILIES,
                                        normalization_dict=NORMALIZATION_DICT,
                                        stopwords=domain_sw_set,
                                        fallback_to_keywords=True,
                                        top_n=15
                                    )
                                    
                                    st.session_state["oe_concept_result"] = concept_res
                                    st.session_state["oe_processing_done"] = True
                                    st.session_state["oe_candidate_groups"] = {}
                                    st.session_state["oe_is_finalized"] = True # Langsung final untuk concept mode
                                    st.session_state["oe_last_params_hash"] = current_hash
                                    
                                    # Create analysis run record
                                    run_id = create_analysis_run(
                                        question_column=target_col,
                                        dataset_id=st.session_state.get("dataset_name", "unknown"),
                                        preprocessing_params={
                                            "use_stemming": use_stemming,
                                            "use_domain_stopwords": use_domain_sw,
                                            "extra_stopwords": extra_sw_str,
                                        },
                                        vectorizer_params={},
                                        clustering_algorithm="Concept Extraction",
                                        n_clusters=len(concept_res.get("top_concepts", [])),
                                        random_state=42,
                                        quality_metrics={"coverage_pct": concept_res.get("coverage_pct", 0)},
                                        n_valid=valid_count,
                                        n_total=summary["total"]
                                    )
                                    st.success(f":material/check_circle: Analisis selesai! Run ID: **{run_id}**")
                                    st.rerun()

                                else:
                                    # --- THEMATIC / CLUSTERING PIPELINE ---
                                    # Extract context stopwords
                                    context_sw_str = st.session_state.get("oe_context_sw", "")
                                    context_sw_list = [w.strip() for w in context_sw_str.split(",") if w.strip()]
                                    
                                    # Setup domain stopwords for TF-IDF filter
                                    domain_sw_set = DOMAIN_SURVEY_STOPWORDS if use_domain_sw else set()
                                    domain_sw_set = domain_sw_set | extra_sw_set

                                    # TF-IDF
                                    tfidf_matrix, vectorizer = get_tfidf_matrix_new(
                                        processed_texts,
                                        ngram_range=(1, 2) if use_stemming else (1, 1),
                                        max_features=max_features,
                                        context_stopwords=context_sw_list,
                                        domain_stopwords=domain_sw_set
                                    )

                                    if tfidf_matrix is None:
                                        st.error("Vocabulary TF-IDF kosong setelah preprocessing. Coba kurangi stopwords atau gunakan dataset yang lebih besar.")
                                    else:
                                        st.session_state["oe_tfidf_matrix"] = tfidf_matrix
                                        st.session_state["oe_vectorizer"] = vectorizer
                                        st.session_state["oe_resp_ids_for_clustering"] = resp_ids

                                        # Clustering
                                        if clustering_mode == "Manual Coding Only":
                                            st.warning("Manual Coding Mode aktif. Sistem tidak membentuk pengelompokan otomatis.")
                                            st.session_state["oe_clustering_rejected"] = True
                                            st.session_state["oe_candidate_groups"] = {}
                                            st.session_state["oe_benchmark_report"] = None
                                            st.session_state["oe_processing_done"] = True
                                            st.session_state["oe_last_params_hash"] = current_hash
                                            st.rerun()
                                        elif clustering_mode == "K-Means (Custom K)":
                                            from utils.nlp_clustering import run_kmeans, filter_zero_vectors, safe_silhouette
                                            filtered_matrix, valid_ids, zero_ids = filter_zero_vectors(tfidf_matrix, resp_ids)
                                            
                                            if filtered_matrix.shape[0] < custom_k:
                                                st.error(f"Jumlah respons valid ({filtered_matrix.shape[0]}) kurang dari target K ({custom_k}).")
                                                st.stop()
                                                
                                            km_model, labels = run_kmeans(filtered_matrix, k=custom_k, random_state=random_state)
                                            sil = safe_silhouette(filtered_matrix, labels, metric='cosine')
                                            
                                            best_result = {
                                                "method_name": f"K-Means (K={custom_k})",
                                                "model": km_model,
                                                "labels": labels,
                                                "filtered_matrix": filtered_matrix,
                                                "valid_ids": valid_ids,
                                                "zero_ids": zero_ids,
                                                "silhouette": sil,
                                                "n_clusters": custom_k,
                                                "composite_score": 1.0,
                                                "benchmark_report": [{
                                                    "method_name": f"K-Means (K={custom_k})",
                                                    "silhouette": sil,
                                                    "davies_bouldin": 0,
                                                    "composite_score": 1.0,
                                                    "n_clusters": custom_k,
                                                    "n_noise": 0
                                                }]
                                            }
                                        else:
                                            from utils.nlp_clustering import run_clustering_benchmark
                                            best_result = run_clustering_benchmark(tfidf_matrix, resp_ids, random_state=random_state)
                                            
                                        if clustering_mode != "K-Means (Custom K)":
                                            st.session_state["oe_benchmark_report"] = best_result.get("benchmark_report", [])
                                        
                                        if best_result["method_name"] == "REJECTED":
                                            st.warning(f":material/warning: Clustering Ditolak: {best_result['reason']} Sistem beralih ke Manual Coding Mode.")
                                            st.session_state["oe_clustering_rejected"] = True
                                            st.session_state["oe_candidate_groups"] = {}
                                            st.session_state["oe_processing_done"] = True
                                            st.session_state["oe_last_params_hash"] = current_hash
                                            
                                        else:
                                            st.session_state["oe_clustering_rejected"] = False
                                            labels = list(best_result["labels"])
                                            filtered_matrix = best_result["filtered_matrix"]
                                            valid_ids = best_result["valid_ids"]
                                            model = best_result["model"]
                                            method_name = best_result["method_name"]

                                            # Extract domain stopwords for keyword filtering
                                            domain_sw_set = DOMAIN_SURVEY_STOPWORDS if use_domain_sw else set()
                                            domain_sw_set = domain_sw_set | extra_sw_set

                                            # Keywords dan phrases
                                            if "K-Means" in method_name and hasattr(model, 'cluster_centers_'):
                                                keywords_per_cluster = get_top_keywords_from_centroids(
                                                    model, vectorizer, n_words=10, domain_stopwords=domain_sw_set
                                                )
                                            else:
                                                keywords_per_cluster = get_top_keywords_for_labels(
                                                    filtered_matrix, labels, vectorizer, n_words=10, domain_stopwords=domain_sw_set
                                                )

                                            phrases_per_cluster = get_top_phrases_per_cluster(
                                                filtered_matrix, labels, vectorizer, n_phrases=5, domain_stopwords=domain_sw_set
                                            )

                                            # Representative responses
                                            rep_ids_per_cluster = get_representative_responses(
                                                filtered_matrix, labels, valid_ids, n_reps=5, model=model
                                            )

                                            # Buat candidate groups (note: labels and valid_ids length matches)
                                            # We need to simulate cluster_metrics dict for backward compatibility
                                            cluster_metrics_dict = {
                                                l: best_result["silhouette"] for l in set(labels) if l != -1
                                            }

                                            groups, order = create_candidate_groups_from_clustering(
                                                cluster_labels=labels,
                                                response_ids=valid_ids,
                                                top_keywords=keywords_per_cluster,
                                                top_phrases=phrases_per_cluster,
                                                representative_ids=rep_ids_per_cluster,
                                                cluster_metrics=cluster_metrics_dict,
                                            )
                                            
                                            # Evaluasi kohesi dan hitung Quality Score (awal)
                                            from utils.nlp_clustering import compute_cluster_quality_score
                                            for gid, group in groups.items():
                                                q_score, q_reason = compute_cluster_quality_score(
                                                    top_keywords=group.top_keywords,
                                                    top_phrases=group.top_phrases,
                                                    context_stopwords=context_sw_list,
                                                    domain_stopwords=domain_sw_set,
                                                    silhouette=group.silhouette_score,
                                                    size=group.size
                                                )
                                                group.quality_score = q_score
                                                group.quality_reason = q_reason

                                            # --- AUTO MERGE & PURGE ---
                                            from utils.open_ended_state import auto_merge_and_purge_candidate_groups
                                            groups, order = auto_merge_and_purge_candidate_groups(
                                                groups=groups,
                                                tfidf_matrix=filtered_matrix,
                                                resp_ids=valid_ids,
                                                similarity_threshold=0.35
                                            )

                                            st.session_state["oe_candidate_groups"] = groups
                                            st.session_state["oe_group_order"] = order
                                            st.session_state["oe_processing_done"] = True
                                            st.session_state["oe_is_finalized"] = False
                                            st.session_state["oe_last_params_hash"] = current_hash
                                            
                                            from utils.open_ended_state import update_merge_suggestions
                                            update_merge_suggestions()

                                            # Simpan analysis run
                                            run_id = create_analysis_run(
                                                question_column=target_col,
                                                dataset_id=st.session_state.get("dataset_name", "unknown"),
                                                preprocessing_params={
                                                    "use_stemming": use_stemming,
                                                    "use_domain_stopwords": use_domain_sw,
                                                    "extra_stopwords": extra_sw_str,
                                                    "context_stopwords": context_sw_str,
                                                },
                                                vectorizer_params={
                                                    "max_features": max_features,
                                                },
                                                clustering_algorithm=method_name,
                                                n_clusters=best_result["n_clusters"],
                                                random_state=random_state,
                                                quality_metrics={"composite_score": best_result["composite_score"], "silhouette": best_result["silhouette"]},
                                                n_valid=valid_count,
                                                n_total=summary["total"]
                                            )
                                            st.success(f":material/check_circle: Analisis selesai! Run ID: **{run_id}** | {len(groups)} kandidat kelompok dibuat.")
                                            st.rerun()

                        except Exception as e:
                            st.error(f":material/error: Terjadi error: {str(e)}")
                            import traceback
                            with st.container(border=True):
                                st.markdown("**Detail teknis (untuk debugging):**")
                                st.code(traceback.format_exc())

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: CLUSTER EVALUATION METRICS & MANUAL MODE
    # ─────────────────────────────────────────────────────────────────────────
    current_mode = st.session_state.get("oe_analysis_mode", "thematic")
    is_concept_mode = (current_mode == "concept")

    if st.session_state.get("oe_processing_done", False) and not is_concept_mode:
        benchmark_report = st.session_state.get("oe_benchmark_report", [])
        is_rejected = st.session_state.get("oe_clustering_rejected", False)
        
        if benchmark_report:
            with st.expander(":material/analytics: Laporan Auto-Benchmark Clustering (Internal)", expanded=is_rejected):
                st.caption(
                    "Sistem secara otomatis menguji 3 metode berbeda. "
                    "Pemilihan didasarkan pada **Composite Score** tertinggi (kombinasi Silhouette + Penalti Noise & Ukuran)."
                )
                
                bench_df = pd.DataFrame(benchmark_report)
                if not bench_df.empty:
                    # Rename columns for display
                    display_df = bench_df[["method_name", "n_clusters", "n_noise", "silhouette", "noise_ratio", "composite_score"]].copy()
                    display_df.columns = ["Metode", "Total Kelompok", "Noise/Unclassified", "Silhouette", "Rasio Noise", "Composite Score"]
                    
                    # Highlight row with max composite score
                    max_score = display_df["Composite Score"].max()
                    def highlight_best(row):
                        if row["Composite Score"] == max_score:
                            return ['background-color: rgba(102, 126, 234, 0.25)'] * len(row)
                        return [''] * len(row)
                    
                    st.dataframe(display_df.style.apply(highlight_best, axis=1).format({"Silhouette": "{:.3f}", "Rasio Noise": "{:.1%}", "Composite Score": "{:.3f}"}), use_container_width=True, hide_index=True)
                    st.caption(":material/lightbulb: Metode dengan baris berwarna dipilih karena memberikan pemisahan teks terbaik dan rasio noise terkecil.")
        
        if is_rejected:
            st.info(":material/lightbulb: Gunakan fitur **Manual Coding Assistance** di bawah ini untuk membentuk kategori secara rasional berdasarkan kata kunci dominan.")
            # We don't render the candidate groups UI if rejected.
            # Instead, we just let the "Unclassified Responses" section at the bottom handle the manual grouping.
            # But we can also add a quick view of top words here.
            
            validated_df_curr = st.session_state.get("oe_validated_df")
            if validated_df_curr is not None:
                from utils.open_ended_preprocessing import get_valid_texts_for_clustering
                from utils.nlp_clustering import get_tfidf_matrix_new
                
                processed_texts, resp_ids = get_valid_texts_for_clustering(st.session_state["oe_preprocessed_df"])
                if processed_texts:
                    context_sw_str = st.session_state.get("oe_context_sw", "")
                    context_sw_list = [w.strip() for w in context_sw_str.split(",") if w.strip()]
                    extra_sw_str = st.session_state.get("oe_extra_sw", "")
                    extra_sw_set = {w.strip().lower() for w in extra_sw_str.split(",") if w.strip()} if extra_sw_str else set()
                    domain_sw_set = DOMAIN_SURVEY_STOPWORDS if st.session_state.get("oe_use_domain_sw", True) else set()
                    domain_sw_set = domain_sw_set | extra_sw_set
                    
                    tfidf_mat, vec = get_tfidf_matrix_new(
                        processed_texts,
                        ngram_range=(1, 2),
                        max_features=500,
                        context_stopwords=context_sw_list,
                        domain_stopwords=domain_sw_set
                    )
                    
                    if tfidf_mat is not None:
                        feature_names = vec.get_feature_names_out()
                        sum_tfidf = tfidf_mat.sum(axis=0)
                        if sp.issparse(sum_tfidf):
                            sum_tfidf = sum_tfidf.A1
                        else:
                            sum_tfidf = sum_tfidf.flatten()
                        
                        top_indices = sum_tfidf.argsort()[::-1][:20]
                        top_terms = [feature_names[i] for i in top_indices]
                        
                        st.markdown("##### :material/trending_up: Top 20 Kata Kunci Global (sebagai panduan pembuatan kategori)")
                        st.write(", ".join([f"`{t}`" for t in top_terms]))


    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: CANDIDATE GROUP REVIEW & VALIDATION
    # ─────────────────────────────────────────────────────────────────────────
    is_rejected = st.session_state.get("oe_clustering_rejected", False)
    if st.session_state.get("oe_processing_done", False) and not st.session_state.get("oe_is_finalized", False) and not is_rejected and not is_concept_mode:
        groups = st.session_state.get("oe_candidate_groups", {})
        group_order = st.session_state.get("oe_group_order", [])
        preprocessed_df = st.session_state.get("oe_preprocessed_df")
        resp_ids_for_cluster = st.session_state.get("oe_resp_ids_for_clustering", [])

        st.markdown("---")
        st.markdown("### :material/verified_user: Langkah 3 — Validasi Kandidat Kelompok")

        n_determined = len(set([g.final_theme_name for g in groups.values() if g.status == "Validated" and g.final_theme_name and not g.is_other]))
        final_theme_count_text = str(n_determined) if n_determined > 0 else "belum ditentukan"

        st.info(
            f":material/assignment: **Panduan Validasi:**\n"
            f"- **{len(groups)} Candidate Groups** | **Final Theme Count: {final_theme_count_text}**\n"
            f"- Setiap kartu di bawah adalah **Kandidat Kelompok** (hasil eksplorasi algoritmik) — bukan tema final.\n"
            f"- **Kualitas Good**: Ukuran memadai ($\ge$5), punya $\ge$3 keyword esensial dan frasa dominan.\n"
            f"- **Kualitas Needs Review**: Memiliki sinyal tema tapi ukurannya kecil (n=3-4), ATAU frasanya kosong, ATAU keyword minim.\n"
            f"- **Kualitas Low Quality**: Sangat kecil (n$\le$2) ATAU merupakan noise/tanpa frasa sama sekali.\n"
            f"- *Catatan: Badge kualitas ini HANYA evaluasi kekompakan algoritmik, BUKAN kebenaran substantif.* \n"
            f"- Periksa keywords dan contoh respons, lalu isi **Nama Tema Final**.\n"
            f"- Klik **Validasi** untuk mengkonfirmasi. Gunakan Merge, Split, Move, atau Other sesuai kebutuhan.\n"
            f"- Laporan **tidak dapat** dibuat sebelum semua kelompok divalidasi."
        )

        # Build original texts lookup
        orig_texts = {}
        if preprocessed_df is not None:
            orig_texts = get_original_texts_for_display(preprocessed_df, resp_ids_for_cluster)

        # Status summary
        n_validated = sum(1 for g in groups.values() if g.status == "Validated")
        n_total_groups = len(groups)
        progress_pct = int(n_validated / n_total_groups * 100) if n_total_groups > 0 else 0

        prog_col1, prog_col2 = st.columns([3, 1])
        with prog_col1:
            st.progress(progress_pct / 100, text=f"Validasi: {n_validated}/{n_total_groups} kelompok ({progress_pct}%)")
        with prog_col2:
            if n_validated == n_total_groups:
                st.success(":material/check_circle: Semua kelompok tervalidasi!")
            else:
                st.warning(f":material/warning: {n_total_groups - n_validated} kelompok belum divalidasi")

        # MERGE SUGGESTIONS UI
        suggestions = st.session_state.get("oe_merge_suggestions", [])
        # Filter suggestions
        valid_suggestions = [s for s in suggestions if s["group_a"] in groups and s["group_b"] in groups]
        
        if valid_suggestions:
            def on_threshold_change():
                from utils.open_ended_state import update_merge_suggestions
                update_merge_suggestions()
                
            st.markdown("---")
            st.markdown("### :material/compare_arrows: Potensi Penggabungan Kandidat")
            st.caption("Tahap agregasi *Macro-Theme*: Sistem menghitung Cosine Similarity antar-centroid tiap kelompok (100% lokal berbasis TF-IDF) untuk menyarankan penggabungan.")
            
            st.slider("Ambang Batas Kemiripan (Cosine Similarity)", min_value=0.20, max_value=0.60, value=0.35, step=0.01, key="oe_merge_threshold", on_change=on_threshold_change)
            
            # Fetch updated suggestions (it might have changed due to slider, but streamlit rerun handles it)
            suggestions = st.session_state.get("oe_merge_suggestions", [])
            valid_suggestions = [s for s in suggestions if s["group_a"] in groups and s["group_b"] in groups]
            
            high_sim_suggestions = [s for s in valid_suggestions if s["score"] >= st.session_state["oe_merge_threshold"] and not st.session_state.get(f"dismiss_sugg_{s['group_a']}_{s['group_b']}", False)]
            
            if high_sim_suggestions:
                st.info(f"💡 Ditemukan **{len(high_sim_suggestions)}** pasangan candidate group yang memiliki kemiripan tinggi.")
                
                for sugg in high_sim_suggestions:
                    ga = groups[sugg["group_a"]]
                    gb = groups[sugg["group_b"]]
                    
                    with st.container(border=True):
                        st.markdown(f"#### 💡 {ga.candidate_label} ↔ {gb.candidate_label}")
                        st.markdown(f"**Similarity Score: {sugg['score']:.2f}** (Centroid: {sugg.get('centroid_sim', sugg['score']):.2f} | Keyword: {sugg.get('weighted_kw_overlap', 0):.2f} | Phrase: {sugg.get('phrase_sim', 0):.2f})")
                        overlap_display = ", ".join(sugg.get('overlap_keywords', [])[:8])
                        st.markdown(f"**Shared substantive keywords:** {overlap_display if overlap_display else '—'}")
                        phrase_overlap_display = ", ".join(sugg.get('overlap_phrases', [])[:4])
                        if phrase_overlap_display:
                            st.markdown(f"**Shared phrases:** {phrase_overlap_display}")
                        st.markdown(f"**Ukuran gabungan:** {ga.size} + {gb.size} = **{ga.size + gb.size}** respons")
                        reason = sugg.get('reason', '')
                        if reason:
                            st.caption(f"💡 Alasan: {reason}")
                        else:
                            st.caption("Kedua kandidat memiliki kemiripan tinggi. Periksa manual sebelum menggabungkan.")
                        
                        c1, c2, c3 = st.columns([1,1,1])
                        with c1:
                            if st.button("Terima Merge", type="primary", key=f"do_merge_{ga.group_id}_{gb.group_id}"):
                                merge_name = f"Merged: {ga.candidate_label} & {gb.candidate_label}"
                                if ga.final_theme_name: merge_name = ga.final_theme_name
                                elif gb.final_theme_name: merge_name = gb.final_theme_name
                                merge_groups([ga.group_id, gb.group_id], merge_name)
                                st.session_state[f"dismiss_sugg_{ga.group_id}_{gb.group_id}"] = True
                                st.success("Berhasil di-merge!")
                                st.rerun()
                        with c2:
                            if st.button("Tolak / Keep Separate", key=f"keep_{ga.group_id}_{gb.group_id}"):
                                st.session_state[f"dismiss_sugg_{ga.group_id}_{gb.group_id}"] = True
                                st.rerun()
                        with c3:
                            if st.button("Review Manual", key=f"rev_{ga.group_id}_{gb.group_id}"):
                                st.session_state[f"show_rev_{ga.group_id}_{gb.group_id}"] = not st.session_state.get(f"show_rev_{ga.group_id}_{gb.group_id}", False)
                                st.rerun()
                                
                    if st.session_state.get(f"show_rev_{ga.group_id}_{gb.group_id}", False):
                        with st.container(border=True):
                            st.markdown("##### Bandingkan Kandidat")
                            r_col1, r_col2 = st.columns(2)
                            with r_col1:
                                st.markdown(f"**{ga.candidate_label} ({ga.size} respons)**")
                                st.markdown("**Top Keywords:** " + ", ".join(ga.top_keywords))
                                st.markdown("**Top Phrases:** " + ", ".join(ga.top_phrases))
                                st.markdown("**5 Contoh Respons:**")
                                for rid in ga.representative_response_ids[:5]:
                                    orig = orig_texts.get(rid, "")
                                    if orig: st.markdown(f"- *{orig}*")
                                    
                            with r_col2:
                                st.markdown(f"**{gb.candidate_label} ({gb.size} respons)**")
                                st.markdown("**Top Keywords:** " + ", ".join(gb.top_keywords))
                                st.markdown("**Top Phrases:** " + ", ".join(gb.top_phrases))
                                st.markdown("**5 Contoh Respons:**")
                                for rid in gb.representative_response_ids[:5]:
                                    orig = orig_texts.get(rid, "")
                                    if orig: st.markdown(f"- *{orig}*")
                                    
                            st.markdown("**Bandingkan secara saksama di atas.** (Gunakan tombol 'Terima Merge' atau 'Tolak' pada kartu utama).")

        st.markdown("---")

        # MERGE TOOL
        with st.expander(":material/merge_type: Merge Kelompok", expanded=False):
            st.caption("Pilih 2 atau lebih kandidat kelompok yang sebenarnya satu tema, lalu merge.")
            group_labels_map = {gid: f"{g.candidate_label} ({g.size} respons)" for gid, g in groups.items()}
            groups_to_merge = st.multiselect(
                "Pilih kelompok yang akan di-merge",
                options=list(group_labels_map.keys()),
                format_func=lambda x: group_labels_map.get(x, x),
                key="oe_merge_select",
            )
            merge_theme_name = st.text_input("Nama Tema Final Setelah Merge", key="oe_merge_theme_name",
                                              placeholder="Contoh: Keadilan & Transparansi Penilaian")
            if st.button(":material/merge_type: Lakukan Merge", key="oe_merge_btn",
                          disabled=len(groups_to_merge) < 2 or not merge_theme_name.strip()):
                merge_groups(groups_to_merge, merge_theme_name)
                st.success(f"Merge berhasil! Tema baru: **{merge_theme_name}**")
                st.rerun()

        # ── TOP 10 MACRO THEMES SECTION ──────────────────────────────────────
        # Compute macro themes dari candidate groups yang ada
        from utils.open_ended_state import compute_macro_themes, get_top_macro_themes
        tfidf_mat_curr = st.session_state.get("oe_tfidf_matrix")
        resp_ids_curr = st.session_state.get("oe_resp_ids_for_clustering", [])
        macro_themes = compute_macro_themes(
            groups,
            tfidf_matrix=tfidf_mat_curr,
            resp_ids=resp_ids_curr,
            similarity_threshold=0.40,
        )
        top_macro = get_top_macro_themes(macro_themes, n=25)
        # Map group_id ke macro theme label (untuk anotasi kartu)
        group_to_macro_label = {}
        for mt in macro_themes:
            for gid_in_macro in mt["group_ids"]:
                group_to_macro_label[gid_in_macro] = mt["macro_id"]
        
        # IDs yang masuk Top 25
        top_n_group_ids = set()
        for mt in top_macro:
            for gid_in_macro in mt["group_ids"]:
                top_n_group_ids.add(gid_in_macro)

        if len(macro_themes) < len(groups):
            n_aggregated = len(groups) - len(macro_themes)
            st.info(
                f":material/bar_chart: **Macro Theme Aggregation:** {len(groups)} Candidate Groups → "
                f"**{len(macro_themes)} Macro Themes** "
                f"({n_aggregated} kelompok berhasil di-agregasi berdasarkan kemiripan konten). "
                f"Top {min(25, len(macro_themes))} ditampilkan untuk Human Validation di bawah."
            )
        else:
            st.caption(
                f"📊 {len(groups)} Candidate Groups → {len(macro_themes)} Macro Themes "
                f"(belum ada yang dapat diagregasi — kelompok terlalu berbeda)."
            )

        # CANDIDATE GROUP CARDS
        ordered_groups = sorted([(gid, g) for gid, g in groups.items()], key=lambda x: x[1].size, reverse=True)

        # Build top-25 ordered list (berdasarkan macro ranking)
        top_n_gids_ordered = []
        for mt in top_macro:
            # Ambil group terbesar dalam macro dulu
            sorted_in_macro = sorted(mt["group_ids"], key=lambda gid: groups[gid].size if gid in groups else 0, reverse=True)
            top_n_gids_ordered.extend(sorted_in_macro)

        long_tail_gids = [gid for gid, _ in ordered_groups if gid not in top_n_group_ids]

        for i, gid in enumerate(top_n_gids_ordered):
            if gid not in groups:
                continue
            group = groups[gid]
            macro_label = group_to_macro_label.get(gid, "")
            status_color = STATUS_COLORS.get(group.status, "#94a3b8")
            is_other_style = "opacity: 0.65;" if group.is_other else ""

            if i == 0:
                st.markdown(f"### :material/star: Top {min(10, len(macro_themes))} Macro Themes")
                st.caption("Kelompok di bawah ini adalah Macro Themes prioritas untuk Anda validasi. Human Validation hanya diperlukan untuk kelompok-kelompok ini.")

            with st.container(border=True):
                # Format header
                hdr_col1, hdr_col2 = st.columns([4, 1])
                with hdr_col1:
                    macro_badge = f" &nbsp;<span style='font-size:0.55em; background:#667eea; color:white; padding:2px 6px; border-radius:8px;'>{macro_label}</span>" if macro_label else ""
                    st.markdown(f"### {group.candidate_label}{macro_badge} &nbsp; <span style='font-size:0.6em;'>{group.quality_score}</span>", unsafe_allow_html=True)
                with hdr_col2:
                    if group.is_other:
                        st.markdown("<div style='text-align:right;'><span style='background:#94a3b8; color:white; padding:4px 10px; border-radius:12px; font-size:0.8em;'>Other</span></div>", unsafe_allow_html=True)

                if group.quality_reason:
                    if "Low Quality" in group.quality_score or "Needs Review" in group.quality_score:
                        st.warning(group.quality_reason)
                    else:
                        st.caption(group.quality_reason)

                st.caption(f"**Status:** {group.status} | **Ukuran:** {group.size} respons")

                # Header row metadata
                hdr1, hdr2, hdr3 = st.columns([3, 1, 1])
                with hdr1:
                    st.markdown(
                        f"<span style='background:{status_color}; color:white; padding:2px 8px; border-radius:8px; font-size:0.75em;'>{group.status}</span>",
                        unsafe_allow_html=True
                    )
                with hdr3:
                    if st.button(":material/delete:", key=f"del_grp_{gid}", help="Hapus kelompok ini (respons masuk Unclassified)"):
                        delete_group(gid)
                        st.rerun()

                # Keywords & Phrases
                kw_col, ph_col = st.columns(2)
                with kw_col:
                    st.markdown("**Top Keywords:**")
                    if group.top_keywords:
                        st.markdown(" · ".join(f"`{kw}`" for kw in group.top_keywords[:8]))
                    else:
                        st.caption("—")
                with ph_col:
                    st.markdown("**Top Phrases:**")
                    if group.top_phrases:
                        st.markdown(" · ".join(f"`{ph}`" for ph in group.top_phrases[:5]))
                    else:
                        st.caption("—")

                # Representative responses
                shown_count = sum(1 for rid in group.representative_response_ids[:5] if orig_texts.get(rid))
                with st.expander(f":material/format_quote: {shown_count} Contoh Respons Representatif"):
                    shown_count_inner = 0
                    for rep_id in group.representative_response_ids[:5]:
                        original = orig_texts.get(rep_id, "")
                        if original:
                            st.markdown(f"- *\"{original}\"*")
                    if shown_count_inner == 0:
                        st.caption("Tidak ada contoh respons tersedia.")

                # Validation controls dihilangkan dari kartu, sisa tombol eksplorasi
                btn_c1, btn_c2 = st.columns([1, 1])
                with btn_c1:
                    if st.button(":material/open_with: Move Response", key=f"move_open_{gid}",
                                  help="Pindahkan respons tertentu ke kelompok lain", use_container_width=True):
                        st.session_state[f"show_move_{gid}"] = not st.session_state.get(f"show_move_{gid}", False)
                        st.session_state[f"show_merge_card_{gid}"] = False
                        st.rerun()
                with btn_c2:
                    if st.button(":material/merge_type: Merge Kelompok", key=f"merge_open_{gid}", 
                                 help="Gabungkan seluruh kelompok ini dengan kelompok lain", use_container_width=True):
                        st.session_state[f"show_merge_card_{gid}"] = not st.session_state.get(f"show_merge_card_{gid}", False)
                        st.session_state[f"show_move_{gid}"] = False
                        st.rerun()

                # Merge panel
                if st.session_state.get(f"show_merge_card_{gid}", False):
                    with st.container(border=True):
                        st.markdown("**Gabungkan Kelompok Ini dengan Kelompok Lain:**")
                        group_labels_map = {other_gid: f"{other_g.candidate_label} ({other_g.size} respons)" for other_gid, other_g in groups.items() if other_gid != gid}
                        target_merge_gid = st.selectbox("Pilih kelompok tujuan:", options=[""] + list(group_labels_map.keys()), format_func=lambda x: group_labels_map.get(x, "Pilih...") if x else "Pilih...", key=f"target_merge_{gid}")
                        merge_name = st.text_input("Nama Tema Final Setelah Merge (opsional):", key=f"merge_name_{gid}")
                        
                        if st.button(":material/merge_type: Eksekusi Merge", key=f"exec_merge_{gid}", type="primary", disabled=not target_merge_gid):
                            from utils.open_ended_state import merge_groups
                            name_to_use = merge_name.strip() if merge_name.strip() else f"Merged Tema"
                            merge_groups([gid, target_merge_gid], name_to_use)
                            st.success("Merge berhasil!")
                            st.rerun()

                # Move response panel
                if st.session_state.get(f"show_move_{gid}", False):
                    with st.container():
                        st.markdown("**Pindahkan Respons ke Kelompok Lain:**")
                        # Show all responses in this group
                        all_resp_in_group = [
                            (rid, orig_texts.get(rid, f"ID:{rid}"))
                            for rid in group.response_ids[:20]  # limit display
                        ]
                        resp_labels = {str(rid): f"{txt[:60]}..." if len(txt) > 60 else txt
                                       for rid, txt in all_resp_in_group}

                        if resp_labels:
                            selected_resp = st.selectbox(
                                "Pilih respons",
                                options=list(resp_labels.keys()),
                                format_func=lambda x: resp_labels.get(x, x),
                                key=f"move_resp_select_{gid}",
                            )
                            other_groups = {ogid: g.candidate_label for ogid, g in groups.items() if ogid != gid}
                            if other_groups:
                                dest_gid = st.selectbox(
                                    "Pindahkan ke",
                                    options=list(other_groups.keys()),
                                    format_func=lambda x: other_groups.get(x, x),
                                    key=f"move_dest_{gid}",
                                )
                                if st.button("Pindahkan", key=f"move_exec_{gid}"):
                                    try:
                                        rid_val = type(group.response_ids[0])(selected_resp) if group.response_ids else selected_resp
                                    except Exception:
                                        rid_val = selected_resp
                                    move_response(rid_val, gid, dest_gid)
                                    st.session_state[f"show_move_{gid}"] = False
                                    st.rerun()

                # Split tool per group
                with st.expander(":material/call_split: Split Kelompok Ini", expanded=False):
                    st.caption("Tandai respons yang akan masuk Group A. Sisa masuk Group B.")
                    resp_options = [(rid, orig_texts.get(rid, f"ID:{rid}")) for rid in group.response_ids[:30]]
                    resp_labels_split = {str(rid): f"{txt[:70]}..." if len(txt) > 70 else txt
                                         for rid, txt in resp_options}
                    selected_for_a = st.multiselect(
                        "Respons untuk Kelompok A",
                        options=list(resp_labels_split.keys()),
                        format_func=lambda x: resp_labels_split.get(x, x),
                        key=f"split_a_{gid}",
                    )
                    split_name_a = st.text_input("Nama Tema Kelompok A", key=f"split_na_{gid}", placeholder="Nama tema A...")
                    split_name_b = st.text_input("Nama Tema Kelompok B (sisa)", key=f"split_nb_{gid}", placeholder="Nama tema B...")

                    if st.button(":material/call_split: Lakukan Split", key=f"split_exec_{gid}",
                                  disabled=not selected_for_a or not split_name_a.strip() or not split_name_b.strip()):
                        # Convert str keys back ke original type
                        try:
                            a_ids = [type(group.response_ids[0])(x) for x in selected_for_a] if group.response_ids else selected_for_a
                        except Exception:
                            a_ids = selected_for_a
                        split_group(gid, a_ids, split_name_a, split_name_b)
                        st.rerun()

                    st.divider()
                    st.markdown("**Auto Split (K-Means k=2)** — memecah kelompok secara otomatis berdasarkan pola teks.")
                    if st.button(":material/auto_awesome: Lakukan Auto Split", key=f"auto_split_exec_{gid}", disabled=len(group.response_ids) < 2):
                        if preprocessed_df is not None:
                            subset_df = preprocessed_df[preprocessed_df['response_id'].isin(group.response_ids)]
                            if len(subset_df) >= 2:
                                from sklearn.feature_extraction.text import TfidfVectorizer
                                from sklearn.cluster import KMeans
                                tfidf = TfidfVectorizer(max_features=100)
                                mat = tfidf.fit_transform(subset_df['processed_text'].fillna(""))
                                km = KMeans(n_clusters=2, random_state=42)
                                lbls = km.fit_predict(mat)
                                auto_a_ids = subset_df['response_id'].values[lbls == 0].tolist()
                                split_group(gid, auto_a_ids, f"{group.candidate_label} - A", f"{group.candidate_label} - B")
                                st.rerun()

        # ─────────────────────────────────────────────────────────────────────
        # LONG TAIL SECTION
        # ─────────────────────────────────────────────────────────────────────
        if long_tail_gids:
            st.markdown("---")
            st.markdown("### :material/more_horiz: Kelompok Long Tail (di luar Top 25 Macro Themes)")
            st.info(
                f"**{len(long_tail_gids)} kelompok** di luar Top 25. "
                "Kelompok ini akan otomatis dijadikan **Other** saat Anda menggunakan Form Penamaan Massal. "
                "Anda masih dapat memindah (*Move*) respons dari sini ke kelompok Top 25 sebelum finalisasi."
            )
            with st.expander(f"Lihat {len(long_tail_gids)} Kelompok Long Tail", expanded=False):
                for l_gid in long_tail_gids:
                    if l_gid not in groups:
                        continue
                    l_group = groups[l_gid]
                    st.markdown(f"- **{l_group.candidate_label}** ({l_group.size} respons) — Keywords: {', '.join(l_group.top_keywords[:5]) if l_group.top_keywords else '—'}")

        # ─────────────────────────────────────────────────────────────────────
        # FORM PENAMAAN MASSAL
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### :material/drive_file_rename_outline: Form Penamaan Massal (Top Macro Themes)")
        st.info(
            f"Berikan nama untuk **Top {min(25, len(macro_themes))} Macro Themes** di bawah ini. "
            "Saat Anda klik simpan, seluruh kelompok yang tersisa di Long Tail akan otomatis dijadikan kategori 'Other'."
        )

        with st.container(border=True):
            # Gunakan top_n_gids_ordered (macro-ranked) bukan ordered_groups
            bulk_gids = [gid for gid in top_n_gids_ordered if gid in groups]
            bulk_names = {}
            for i, gid in enumerate(bulk_gids):
                group = groups[gid]
                c_lbl, c_inp = st.columns([1, 2])
                with c_lbl:
                    kw_str = ", ".join(group.top_keywords[:4]) if group.top_keywords else "Tanpa Keyword"
                    st.markdown(f"**{i+1}. {group.candidate_label}** ({group.size} respons)<br/><span style='font-size:0.8em; color:gray;'>{kw_str}</span>", unsafe_allow_html=True)
                with c_inp:
                    bulk_names[gid] = st.text_input(
                        f"Nama Tema {i+1}", 
                        value=group.final_theme_name, 
                        key=f"bulk_theme_{gid}", 
                        label_visibility="collapsed",
                        placeholder="Ketik nama final (WAJIB DIISI)..."
                    )
            
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("Simpan & Validasi Massal", type="primary", use_container_width=True):
                # Validasi kosong
                has_error = False
                for gid in bulk_names:
                    name = bulk_names[gid].strip()
                    if not name:
                        st.error(f"⚠️ Nama tema untuk **{groups[gid].candidate_label}** tidak boleh kosong!")
                        has_error = True
                
                if has_error:
                    st.stop()

                # Validasi Top Macro Themes
                for gid in bulk_names:
                    name = bulk_names[gid].strip()
                    validate_group(gid, name)

                # Sisanya (Long Tail) jadikan Other
                for l_gid in long_tail_gids:
                    if l_gid in groups and not groups[l_gid].is_other and groups[l_gid].status != "Validated":
                        mark_group_as_other(l_gid)

                # Tangani Unmapped Valid Responses
                # Cari respons valid yang belum ada di kelompok manapun, lalu jadikan satu kelompok 'Other'
                preprocessed_df = st.session_state.get("oe_preprocessed_df")
                if preprocessed_df is not None:
                    valid_df = preprocessed_df[preprocessed_df["validation_status"] == "valid"]
                    valid_ids = set(valid_df["response_id"].tolist())
                    
                    mapped_ids = set()
                    for g in groups.values():
                        mapped_ids.update(g.response_ids)
                    
                    unmapped_ids = list(valid_ids - mapped_ids)
                    if unmapped_ids:
                        import uuid
                        from utils.open_ended_state import CandidateGroup, add_audit_entry
                        
                        new_gid = f"GRP_UNCLASS_{uuid.uuid4().hex[:6].upper()}"
                        new_group = CandidateGroup(
                            group_id=new_gid,
                            candidate_label="Unclassified Responses (Noise)",
                            final_theme_name="Tema Lainnya",
                            response_ids=unmapped_ids,
                            top_keywords=[],
                            top_phrases=[],
                            representative_response_ids=unmapped_ids[:5],
                            cluster_id=-1,
                            status="Validated",
                            is_other=True
                        )
                        new_group.size = len(unmapped_ids)
                        groups[new_gid] = new_group
                        st.session_state["oe_group_order"].append(new_gid)
                        
                        add_audit_entry(
                            action="auto_group",
                            entity_type="system",
                            entity_id="unclassified",
                            old_value=None,
                            new_value=f"Mengelompokkan otomatis {len(unmapped_ids)} respons yang tidak terklasifikasi menjadi kategori 'Tema Lainnya'."
                        )

                st.success("Seluruh kelompok berhasil divalidasi dan sisa respons tak terklasifikasi telah dipindahkan ke 'Tema Lainnya'!")
                st.rerun()

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5: QUALITY CHECKS & FINALIZATION GATE
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### :material/fact_check: Langkah 4 — Quality Check & Finalisasi")

        all_resp_ids = []
        for g in groups.values():
            all_resp_ids.extend(g.response_ids)
        valid_count = (preprocessed_df["validation_status"] == "valid").sum() if preprocessed_df is not None else 0
        mapped_count = len(all_resp_ids)
        coverage_pct = (mapped_count / valid_count * 100) if valid_count > 0 else 0
        unclassified_count = valid_count - mapped_count
        
        st.info(f"📊 **Data Coverage: {coverage_pct:.1f}%**\n\n{mapped_count} dari {valid_count} respons valid telah dipetakan ke dalam kelompok. {unclassified_count} respons valid belum memiliki kategori (Unclassified Valid).")

        errors, warnings_list = run_quality_checks()

        if warnings_list:
            for w in warnings_list:
                st.warning(f":material/warning: {w}")

        if errors:
            for e in errors:
                st.error(f":material/error: {e}")
            
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("⚡ Otomatis Validasi Sisa Kelompok & Masukkan ke 'Tema Lainnya'", key="quick_resolve_unvalidated", type="primary"):
                for g in groups.values():
                    if g.status != "Validated" or not g.final_theme_name.strip():
                        g.final_theme_name = g.final_theme_name.strip() or "Tema Lainnya"
                        g.status = "Validated"
                        g.is_other = True
                st.success("Seluruh kelompok tersisa berhasil divalidasi sebagai Tema Lainnya!")
                st.rerun()

            st.error("**Finalisasi tidak dapat dilakukan** karena ada masalah di atas yang harus diselesaikan terlebih dahulu.")
            can_finalize = False
        else:
            can_finalize = True
            st.success(":material/check_circle: Semua quality check lolos. Analisis siap untuk difinalisasi.")

        if st.button(
            ":material/lock: Finalisasi Analisis",
            type="primary",
            use_container_width=True,
            disabled=not can_finalize,
            key="oe_finalize_btn",
            help="Klik untuk membekukan mapping final dan menghitung statistik. Export akan diaktifkan setelahnya.",
        ):
            final_mapping = build_final_mapping()
            preprocessed_df_curr = st.session_state.get("oe_preprocessed_df")
            summary_df = finalize_analysis(final_mapping, preprocessed_df_curr)
            st.success(":material/lock: Analisis difinalisasi! Statistik final dihitung dari validated mapping.")
            st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: FINAL RESULTS — hanya setelah finalisasi
    # ─────────────────────────────────────────────────────────────────────────
    if st.session_state.get("oe_is_finalized", False):
        st.markdown("---")
        
        current_mode = st.session_state.get("oe_analysis_mode", "thematic")
        is_concept_mode = (current_mode == "concept")

        if is_concept_mode:
            st.markdown(f"### :material/insert_chart: Hasil Analisis: {MODE_LABELS.get(current_mode, current_mode)}")
            concept_res = st.session_state.get("oe_concept_result")
            if not concept_res:
                st.warning("Tidak ada hasil analisis konsep tersedia.")
            else:
                # Build standard result
                std_result = build_multilabel_result(
                    concept_analysis_result=concept_res,
                    question_col=target_col,
                    mode=current_mode
                )
                summary_df = result_to_summary_df(std_result)
                
                valid_count = std_result["total_valid"]
                st.caption(f"📊 Total respons valid: **{valid_count}** | Metode ekstraksi: {concept_res.get('mode', 'dictionary')} | Coverage: {concept_res.get('coverage_pct', 0)}%")
                
                with st.container():
                    st.markdown(f"#### Distribusi {std_result['item_label']}")
                    fig_final = px.bar(
                        summary_df,
                        y=std_result['item_label'],
                        x="Jumlah Respons",
                        orientation="h",
                        text="% Responden",
                        color="Jumlah Respons",
                        color_continuous_scale="Purples",
                        title=f"Distribusi {std_result['top_label']}",
                    )
                    fig_final.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                    fig_final.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        coloraxis_showscale=False,
                        margin=dict(t=50, b=20, l=20, r=80),
                    )
                    if force_light_mode:
                        fig_final.update_layout(**LIGHT_LAYOUT)
                    st.plotly_chart(fig_final, use_container_width=True,
                                    config={"toImageButtonOptions": {"filename": f"{current_mode}_distribution", "scale": 2}},
                                    theme=None if force_light_mode else "streamlit")
                
                coocc_df = get_cooccurrence_df(concept_res)
                
                c_tbl1, c_tbl2 = st.columns(2)
                with c_tbl1:
                    st.markdown(f"#### Tabel Ringkasan {std_result['item_label']}")
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                with c_tbl2:
                    if not coocc_df.empty:
                        st.markdown("#### Top Co-occurrences (Muncul Bersamaan)")
                        st.dataframe(coocc_df, use_container_width=True, hide_index=True)
                    else:
                        st.markdown("#### Top Co-occurrences")
                        st.caption("Tidak ada konsep yang muncul secara bersamaan.")
                
                # Setup variables for export
                final_mapping = concept_res.get("response_concept_map", {})
                preprocessed_df_final = st.session_state.get("oe_preprocessed_df")
                candidate_groups_final = {}
                
        else:
            st.markdown("### :material/insert_chart: Langkah 5 — Visualisasi & Hasil Analisis Final")
            
            final_mapping = st.session_state.get("oe_final_mapping", {})
            summary_df = st.session_state.get("oe_final_theme_summary")
            preprocessed_df_final = st.session_state.get("oe_preprocessed_df")
            candidate_groups_final = st.session_state.get("oe_candidate_groups", {})

            if summary_df is None or summary_df.empty:
                st.warning("Tidak ada data final tersedia.")
            else:
                # Statistik
                valid_count = (preprocessed_df_final["validation_status"] == "valid").sum() if preprocessed_df_final is not None else 0
                st.caption(f"📊 Total respons valid: **{valid_count}** | Denominator untuk persentase: {valid_count}")

                # ── COLOR THEME SELECTION ──
                color_options = ["Purples", "Blues", "Greens", "Reds", "Oranges", "Plasma", "Viridis", "Inferno", "Magma", "Tealgrn"]
                selected_color = st.selectbox("Pilih Tema Warna Bar Chart:", color_options, index=0)

                # Distribution chart
                with st.container():
                    st.markdown("#### Hasil Akhir (Grafik & Tabel)")
                    
                    fig_final = px.bar(
                        summary_df,
                        y="Tema",
                        x="Jumlah",
                        orientation="h",
                        text="Persentase",
                        color="Jumlah",
                        color_continuous_scale=selected_color,
                        title="Distribusi Frekuensi Tema",
                    )
                    fig_final.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                    fig_final.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        coloraxis_showscale=False,
                        margin=dict(t=50, b=20, l=20, r=80),
                    )
                    if force_light_mode:
                        fig_final.update_layout(**LIGHT_LAYOUT)

                    st.plotly_chart(fig_final, use_container_width=True,
                                    config={"toImageButtonOptions": {"filename": "theme_distribution", "scale": 2}},
                                    theme=None if force_light_mode else "streamlit")

                    # Tabel ringkasan tema
                    st.markdown("#### Tabel Ringkasan Tema Final")
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                    
                    if st.button("📸 Tampilkan Gambar Statis (Untuk Copy-Paste ke Word)", help="Klik untuk membuat versi gambar statis dari grafik yang bisa di-copy paste."):
                        st.info("💡 **Tips:** Klik kanan pada gambar grafik di bawah ini, lalu pilih **'Copy image'** dan Paste langsung di Microsoft Word atau presentasi Anda.")
                        try:
                            import matplotlib.pyplot as plt
                            import io
                            
                            # Buat figure
                            fig, ax = plt.subplots(figsize=(10, 6))
                            df_sorted = summary_df.sort_values("Jumlah", ascending=True)
                            
                            # Warna
                            bar_color = "#6366f1" if force_light_mode else "#818cf8"
                            bg_color = "white" if force_light_mode else "#0e1117"
                            text_color = "black" if force_light_mode else "white"
                            
                            fig.patch.set_facecolor(bg_color)
                            ax.set_facecolor(bg_color)
                            
                            bars = ax.barh(df_sorted["Tema"], df_sorted["Jumlah"], color=bar_color)
                            
                            for bar, pct in zip(bars, df_sorted["Persentase"]):
                                ax.text(bar.get_width() + (df_sorted["Jumlah"].max()*0.01), bar.get_y() + bar.get_height()/2, 
                                        f"{pct:.1f}%", va='center', ha='left', fontsize=10, color=text_color)
                                        
                            ax.set_title("Distribusi Frekuensi Tema", fontsize=14, pad=20, color=text_color)
                            ax.set_xlabel("Jumlah Respons", fontsize=12, color=text_color)
                            ax.tick_params(colors=text_color)
                            
                            ax.spines['top'].set_visible(False)
                            ax.spines['right'].set_visible(False)
                            ax.spines['bottom'].set_color(text_color)
                            ax.spines['left'].set_color(text_color)
                            
                            plt.tight_layout()
                            
                            buf = io.BytesIO()
                            fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
                            buf.seek(0)
                            
                            st.image(buf, caption="Grafik Distribusi Tema (Copyable PNG)")
                            plt.close(fig)
                            
                            st.markdown("---")
                            st.markdown("##### Tabel Copy-Paste (Plain HTML)")
                            st.caption("Blok/Sorot seluruh tabel di bawah ini dengan kursor, tekan Ctrl+C, lalu Ctrl+V di Word.")
                            st.table(summary_df)
                            
                        except Exception as e:
                            st.error(f"Gagal mem-generate gambar statis lewat Matplotlib. Error: {e}")

            # Tabel pemetaan respons
            with st.expander(":material/table_chart: Tabel Pemetaan Respons Lengkap"):
                if preprocessed_df_final is not None:
                    mapping_display = []
                    for _, row in preprocessed_df_final.iterrows():
                        resp_id = row["response_id"]
                        mapping_display.append({
                            "Response ID": resp_id,
                            "Respons Asli": row.get("original_text", ""),
                            "Status Validasi": row.get("validation_status", ""),
                            "Tema Final": ", ".join(t) if isinstance(t := final_mapping.get(resp_id, "—"), list) else t,
                        })
                    st.dataframe(pd.DataFrame(mapping_display), use_container_width=True, hide_index=True, height=350)

            # Analysis Runs info
            with st.expander(":material/history: Analysis Runs"):
                runs = st.session_state.get("oe_analysis_runs", [])
                if runs:
                    run_rows = [r.to_dict() for r in runs]
                    st.dataframe(pd.DataFrame(run_rows), use_container_width=True, hide_index=True)
                else:
                    st.caption("Tidak ada run tersimpan.")

            # Audit Log
            with st.expander(":material/receipt_long: Audit Trail"):
                audit_df = get_audit_log_df()
                if not audit_df.empty:
                    st.dataframe(audit_df, use_container_width=True, hide_index=True, height=250)
                else:
                    st.caption("Belum ada entri audit.")

        # Tombol untuk memulai analisis baru
        st.markdown("---")
        if st.button(":material/refresh: Mulai Analisis Baru (Parameter Baru)", key="oe_new_run"):
            reset_oe_analysis(reason="user_started_new_run")
            st.session_state["oe_is_finalized"] = False
            st.session_state["oe_processing_done"] = False
            st.rerun()


st.markdown('---')
st.success(':material/check_circle: Konfigurasi tersimpan.')

# Sidebar
with st.sidebar:
    st.markdown('---')
    if 'df' in st.session_state and st.session_state.df is not None:
        st.success(f":material/check_circle: **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")
        st.markdown('---')
        st.markdown('**Kolom Terkonfigurasi:**')
        configured_cols = {k: v for k, v in st.session_state.question_types.items() if v != 'skip'}
        for col_name, q_type in configured_cols.items():
            st.caption(f'• {col_name}: {q_type}')

    # Analysis run info
    runs = st.session_state.get("oe_analysis_runs", [])
    if runs:
        st.markdown('---')
        st.caption(f"🔬 OE Analysis Runs: {len(runs)}")
        latest = runs[-1]
        st.caption(f"Run ID: `{latest.run_id}` | {latest.clustering_algorithm} K={latest.n_clusters}")
        
        current_groups_count = len(st.session_state.get("oe_candidate_groups", {}))
        if current_groups_count > 0 and current_groups_count != latest.n_clusters:
            st.caption(f"*(UI menampilkan {current_groups_count} Candidate Group akibat efek Merge/Split/Noise)*")

render_sidebar_footer()
render_page_footer()
