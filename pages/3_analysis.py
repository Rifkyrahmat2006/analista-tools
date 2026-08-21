import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from io import BytesIO
from utils.nlp_clustering import (
    preprocess_for_clustering,
    get_tfidf_matrix,
    find_optimal_k,
    run_kmeans,
    get_top_keywords as get_cluster_keywords,
    get_representative_docs
)

from utils.pivot_analysis import single_choice_analysis, scale_analysis, scale_statistics, cross_tabulation, get_single_choice_preview
from utils.multi_select_analysis import multi_choice_analysis, multi_choice_combinations, get_multiple_choice_preview
from utils.text_analysis import analyze_text_column, get_top_keywords
from utils.export_helpers import table_to_png
from utils.question_detection import detect_question_type, analyze_column_features
from utils.theme import inject_theme_css, get_light_plotly_layout, render_sidebar_footer, render_page_footer

st.set_page_config(page_title="Analysis", layout="wide")

inject_theme_css()

# Custom Plotly color sequence (to keep brand colors)
PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
LIGHT_LAYOUT = get_light_plotly_layout()

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


with tab_thematic:
    text_columns = df.select_dtypes(include=['object']).columns.tolist()
    # ──────────────────────────────────────────────────
    # STATE MANAGEMENT
    # ──────────────────────────────────────────────────
    if "thematic_results" not in st.session_state:
        st.session_state.thematic_results = None
    if "cluster_labels" not in st.session_state:
        st.session_state.cluster_labels = {}
    if "final_df" not in st.session_state:
        st.session_state.final_df = None

    def reset_thematic_state():
        st.session_state.thematic_results = None
        st.session_state.cluster_labels = {}
        st.session_state.final_df = None

    # ──────────────────────────────────────────────────
    # 1. SETUP & PARAMETERS
    # ──────────────────────────────────────────────────
    with st.expander(":material/settings: 1. Konfigurasi Analisis", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            target_col = st.selectbox("Pilih Kolom Teks", text_columns, on_change=reset_thematic_state)

            st.markdown("#### Clustering Parameters")
            k_method = st.radio("Metode Jumlah Cluster (K)", ["Auto (Silhouette Score)", "Manual"], horizontal=True, on_change=reset_thematic_state)
            if k_method == "Manual":
                manual_k = st.number_input("Jumlah Cluster (K)", min_value=2, max_value=20, value=5, on_change=reset_thematic_state)
            else:
                manual_k = None

        with col2:
            st.markdown("#### Text Preprocessing")
            use_stemming = st.checkbox("Gunakan Stemming (Sastrawi)", value=False, on_change=reset_thematic_state)
            use_bigram = st.checkbox("Gunakan Bigram (2-kata)", value=False, on_change=reset_thematic_state)
            extra_sw = st.text_input("Stopwords Tambahan (pisahkan dengan koma)", placeholder="dan, atau, dsb", on_change=reset_thematic_state)

        if st.button(":material/play_circle: Jalankan Analisis Tematik", type="primary", use_container_width=True):
            with st.spinner("Memproses NLP dan Clustering secara lokal..."):
                texts = df[target_col].dropna().tolist()
                original_indices = df[target_col].dropna().index

                # 1. Preprocess
                sw_set = {w.strip().lower() for w in extra_sw.split(",")} if extra_sw else set()
                processed = preprocess_for_clustering(texts, use_stemming=use_stemming, extra_stopwords=sw_set)

                # 2. TF-IDF
                tfidf_matrix, vectorizer = get_tfidf_matrix(processed, use_bigram=use_bigram)

                if tfidf_matrix is None:
                    st.error("Teks terlalu pendek atau hanya berisi stopwords setelah dibersihkan. Tidak bisa dilanjutkan.")
                else:
                    # 3. Clustering
                    if k_method == "Auto (Silhouette Score)":
                        opt_k, scores = find_optimal_k(tfidf_matrix)
                        if opt_k < 2: opt_k = 2
                        k = opt_k
                        st.info(f"Auto-detect: Jumlah cluster optimal adalah **{k}**.")
                    else:
                        k = manual_k

                    kmeans, labels = run_kmeans(tfidf_matrix, k)

                    # 4. Extract insights
                    top_kw = get_cluster_keywords(kmeans, vectorizer, n_words=8)
                    reps = get_representative_docs(tfidf_matrix, kmeans, texts, n_docs=3)

                    # Save to state
                    st.session_state.thematic_results = {
                        "col": target_col,
                        "k": k,
                        "labels": labels,
                        "top_kw": top_kw,
                        "reps": reps,
                        "texts": texts,
                        "indices": original_indices
                    }

                    # Initialize default cluster labels
                    st.session_state.cluster_labels = {i: f"Cluster {i+1}" for i in range(k)}
                    st.session_state.final_df = None

    # ──────────────────────────────────────────────────
    # 2. REVIEW & VALIDATION (Human-in-the-loop)
    # ──────────────────────────────────────────────────
    if st.session_state.thematic_results is not None:
        res = st.session_state.thematic_results
        k = res["k"]

        st.markdown("---")
        st.markdown("### :material/verified_user: 2. Validasi & Beri Nama Tema")
        st.caption("Hasil clustering otomatis di bawah ini belum final. Silakan periksa keyword dan contoh jawabannya, lalu beri **Nama Tema** yang sesuai maknanya.")

        # Store updated labels
        updated_labels = {}

        # Render Cluster Cards
        cols = st.columns(3)
        for i in range(k):
            col_idx = i % 3
            with cols[col_idx]:
                with st.container(border=True):
                    # Custom label input
                    default_lbl = st.session_state.cluster_labels.get(i, f"Cluster {i+1}")
                    new_lbl = st.text_input(f"Nama Tema {i+1}", value=default_lbl, key=f"lbl_{i}")
                    updated_labels[i] = new_lbl

                    st.markdown(f"**Top Keywords:** `{', '.join(res['top_kw'][i])}`")

                    with st.expander("Contoh Respons"):
                        for r in res['reps'][i]:
                            st.markdown(f"- *\"{r}\"*")

        # Button to apply names and generate final results
        if st.button(":material/save: Simpan Nama Tema & Hasilkan Laporan", type="primary"):
            st.session_state.cluster_labels = updated_labels

            # Create mapping
            label_map = {i: updated_labels[i] for i in range(k)}

            # Map back to dataframe
            final_df = df.copy()
            final_df["Tema_Final"] = "Unclassified / Blank"

            # Assign clusters to the indices that were valid
            for idx, cluster_id in zip(res["indices"], res["labels"]):
                final_df.loc[idx, "Tema_Final"] = label_map[cluster_id]

            st.session_state.final_df = final_df
            st.rerun()

    # ──────────────────────────────────────────────────
    # 3. FINAL RESULTS & VISUALIZATION
    # ──────────────────────────────────────────────────
    if st.session_state.final_df is not None:
        st.markdown("---")
        st.markdown("### :material/insert_chart: 3. Hasil Analisis Tematik")

        f_df = st.session_state.final_df

        # Calculate frequencies
        theme_counts = f_df["Tema_Final"].value_counts().reset_index()
        theme_counts.columns = ["Tema", "Frekuensi"]
        theme_counts["Persentase"] = (theme_counts["Frekuensi"] / len(f_df)) * 100

        col_chart, col_narrative = st.columns([2, 1])

        with col_chart:
            fig = px.bar(
                theme_counts, 
                y="Tema", 
                x="Frekuensi", 
                orientation="h",
                text="Frekuensi",
                color="Frekuensi",
                color_continuous_scale="Purples",
                title="Distribusi Tema"
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col_narrative:
            st.markdown("#### Narasi Otomatis")

            # Generate narrative
            if len(theme_counts) > 0:
                top_theme = theme_counts.iloc[0]
                narrative = f"Berdasarkan hasil analisis respons terbuka, tema **'{top_theme['Tema']}'** merupakan tema dengan frekuensi tertinggi, yaitu sebanyak **{top_theme['Frekuensi']} respons** ({top_theme['Persentase']:.1f}%). "

                if len(theme_counts) > 1:
                    second = theme_counts.iloc[1]
                    narrative += f"Selanjutnya, tema **'{second['Tema']}'** ditemukan pada **{second['Frekuensi']} respons** ({second['Persentase']:.1f}%). "

                if len(theme_counts) > 2:
                    third = theme_counts.iloc[2]
                    narrative += f"Secara umum, hasil pengelompokan menunjukkan bahwa respons responden banyak menyoroti aspek **'{top_theme['Tema']}'**, **'{second['Tema']}'**, dan **'{third['Tema']}'**."

                st.info(narrative)

        st.markdown("#### Tabel Pemetaan Respons")
        st.dataframe(f_df[[st.session_state.thematic_results["col"], "Tema_Final"]], use_container_width=True, height=300)

        # Export
        def df_to_xlsx(d: pd.DataFrame) -> bytes:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                d.to_excel(writer, index=False, sheet_name="Data with Themes")
                theme_counts.to_excel(writer, index=False, sheet_name="Theme Summary")
            return buf.getvalue()

        st.download_button(
            label=":material/download: Download Hasil (XLSX)",
            data=df_to_xlsx(f_df),
            file_name="thematic_analysis_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )


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

render_sidebar_footer()
render_page_footer()
