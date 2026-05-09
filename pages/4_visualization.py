import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as pc
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pivot_analysis import single_choice_analysis, scale_analysis
from utils.multi_select_analysis import multi_choice_analysis
from utils.export_helpers import table_to_png
from utils.text_analysis import analyze_text_column, get_top_keywords, generate_wordcloud
from utils.theme import inject_theme_css, get_light_plotly_layout, render_sidebar_footer, render_page_footer

st.set_page_config(page_title="Visualization", layout="wide")

inject_theme_css()

PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]

COLOR_SCALES = ["Purples", "Blues", "Greens", "Pinks", "Viridis", "Plasma", "Inferno", "Turbo", "Sunset", "Teal"]

# Key gradient colors per scale for preview swatches
COLOR_SCALE_PREVIEWS = {
    "Purples": ["#f2f0f7", "#9e9ac8", "#54278f"],
    "Blues":   ["#deebf7", "#6baed6", "#08519c"],
    "Greens":  ["#e5f5e0", "#74c476", "#006d2c"],
    "Pinks":   ["#fce4ec", "#f48fb1", "#880e4f"],
    "Viridis": ["#440154", "#31688e", "#35b779", "#fde725"],
    "Plasma":  ["#0d0887", "#cc4778", "#f89540", "#f0f921"],
    "Inferno": ["#000004", "#bc3754", "#f98e09", "#fcffa4"],
    "Turbo":   ["#30123b", "#28bbec", "#a1fc3d", "#fb8022"],
    "Sunset":  ["#f7f7f7", "#f4a582", "#d6604d", "#4d4d4d"],
    "Teal":    ["#d0f0f0", "#66c2c2", "#007474"],
}

# Map display names to Plotly colorscale names
PLOTLY_SCALE_MAP = {
    "Purples": "Purples",
    "Blues":   "Blues",
    "Greens":  "Greens",
    "Pinks":   "RdPu",
    "Viridis": "Viridis",
    "Plasma":  "Plasma",
    "Inferno": "Inferno",
    "Turbo":   "Turbo",
    "Sunset":  "RdGy",
    "Teal":    "Teal",
}


def render_color_preview(scale_name: str):
    """Render a horizontal gradient swatch for the selected color scale."""
    colors = COLOR_SCALE_PREVIEWS.get(scale_name, ["#888"])
    dots = "".join([
        f'<span style="display:inline-block;width:16px;height:16px;border-radius:50%;'
        f'background:{c};margin:0 3px;vertical-align:middle;border:1px solid rgba(255,255,255,0.15);"></span>'
        for c in colors
    ])
    st.markdown(
        f'<div style="padding:4px 2px 8px 2px;">{dots}'
        f'<span style="font-size:0.75rem;opacity:0.6;margin-left:6px;">{scale_name}</span></div>',
        unsafe_allow_html=True
    )


def df_to_xlsx(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


st.markdown("# :material/bar_chart: Visualization")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning(":material/warning: Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# ──────────────────────────────────────────────────
# SIDEBAR SETTINGS
# ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### :material/palette: Pengaturan Visualisasi")

    chart_theme_display = st.selectbox("Color Scale", COLOR_SCALES, index=0, key="vis_colorscale")
    chart_theme = PLOTLY_SCALE_MAP.get(chart_theme_display, chart_theme_display)
    render_color_preview(chart_theme_display)

    chart_height = st.slider("Tinggi Chart", 300, 800, 500, step=50)

    st.markdown("##### Label pada Chart")
    lbl_c1, lbl_c2, lbl_c3 = st.columns(3)
    with lbl_c1:
        show_count   = st.checkbox("Nilai",      value=True,  key="lbl_count")
    with lbl_c2:
        show_percent = st.checkbox("Persen (%)", value=True,  key="lbl_pct")
    with lbl_c3:
        show_name    = st.checkbox("Nama Opsi",  value=False, key="lbl_name")

    label_pos = st.radio(
        "Posisi Label",
        ["Luar", "Dalam", "Auto"],
        index=0, horizontal=True,
    )
    label_pos_map = {"Luar": "outside", "Dalam": "inside", "Auto": "auto"}
    text_position = label_pos_map[label_pos]

    lbl_sz_col, lbl_bd_col = st.columns([2, 1])
    with lbl_sz_col:
        label_size = st.slider("Ukuran Font", 8, 28, 13, step=1, key="lbl_size")
    with lbl_bd_col:
        label_bold = st.checkbox("Bold", value=False, key="lbl_bold")

    show_legend = st.checkbox("Tampilkan Legenda", value=False)
    if show_legend:
        legend_pos_options = [
            "Kanan Atas", "Kanan Bawah", "Kiri Atas", "Kiri Bawah",
            "Bawah Tengah", "Atas Tengah",
        ]
        legend_pos = st.selectbox("Posisi Legenda", legend_pos_options, index=0)
        LEGEND_CONFIGS = {
            "Kanan Atas":    dict(x=1.0,  y=1.0,   xanchor="right",  yanchor="top"),
            "Kanan Bawah":   dict(x=1.0,  y=0.0,   xanchor="right",  yanchor="bottom"),
            "Kiri Atas":     dict(x=0.0,  y=1.0,   xanchor="left",   yanchor="top"),
            "Kiri Bawah":    dict(x=0.0,  y=0.0,   xanchor="left",   yanchor="bottom"),
            "Bawah Tengah":  dict(x=0.5,  y=-0.18, xanchor="center", yanchor="top",    orientation="h"),
            "Atas Tengah":   dict(x=0.5,  y=1.05,  xanchor="center", yanchor="bottom", orientation="h"),
        }
        legend_cfg = LEGEND_CONFIGS[legend_pos]
    else:
        legend_cfg = {}

    st.markdown("##### Judul Chart")
    custom_title = st.text_input("Override Judul (kosongkan = default)", value="", placeholder="Contoh: Distribusi Jawaban")

    st.markdown("### :material/print: Export Settings")
    force_light_mode = st.checkbox(
        "Paksa Chart Terang",
        help="Aktifkan agar chart Plotly berlatar putih untuk hasil download siap cetak."
    )

    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f":material/check_circle: **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")

EXPORT_LAYOUT = get_light_plotly_layout()

# ──────────────────────────────────────────────────
# TAB NAVIGATION
# ──────────────────────────────────────────────────
tab_charts, tab_wordcloud = st.tabs([
    ":material/bar_chart: Charts",
    ":material/cloud: Wordcloud",
])

# ══════════════════════════════════════════════════
# TAB 1: CHARTS
# ══════════════════════════════════════════════════
with tab_charts:

    # ── Kolom & tipe selectors ──
    st.markdown("### :material/push_pin: Pilih Kolom dan Tipe Chart")
    col_select, type_select, chart_select = st.columns(3)

    with col_select:
        selected_col = st.selectbox("Kolom", df.columns.tolist(), key="vis_col")

    with type_select:
        type_options = ["single_choice", "multiple_choice", "scale"]
        default_type = st.session_state.get("question_types", {}).get(selected_col)
        default_idx  = type_options.index(default_type) if default_type in type_options else 0
        data_type    = st.selectbox(
            "Tipe Data", type_options, index=default_idx,
            format_func=lambda x: x.replace("_", " ").title(),
            key="vis_dtype",
        )

    with chart_select:
        chart_options = {
            "single_choice":  ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
            "multiple_choice":["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
            "scale":          ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Area Chart", "Line Chart"],
        }
        chart_type = st.selectbox("Tipe Chart", chart_options.get(data_type, ["Bar Chart"]), key="vis_chart")

    # ── Refresh button ──
    btn_col, _ = st.columns([1, 4])
    with btn_col:
        if st.button(":material/refresh: Refresh Chart", use_container_width=True):
            st.rerun()

    st.markdown("---")

    # ── Rename column headers ──
    with st.expander(":material/edit: Nama Kolom Tabel & Export", expanded=False):
        hdr1, hdr2 = st.columns(2)
        with hdr1:
            header_val   = st.text_input("Nama Kolom Kategori", value="Jawaban", key="hdr_val")
        with hdr2:
            header_count = st.text_input("Nama Kolom Jumlah",   value="Jumlah",  key="hdr_count")

    # ── Compute data ──
    if selected_col:
        if data_type == "single_choice":
            main_opts   = st.session_state.get(f"mainopts_{selected_col}", None)
            hidden_opts = st.session_state.get(f"hiddenpts_{selected_col}", set())
            result      = single_choice_analysis(df, selected_col, main_options=main_opts)
            if hasattr(result, "empty") and not result.empty:
                result = result[~result["Value"].isin(hidden_opts)]
            val_col, count_col = "Value", "Count"

        elif data_type == "multiple_choice":
            main_opts   = st.session_state.get(f"mainopts_{selected_col}", None)
            hidden_opts = st.session_state.get(f"hiddenpts_{selected_col}", set())
            result      = multi_choice_analysis(df, selected_col, main_options=main_opts)
            if hasattr(result, "empty") and not result.empty:
                result = result[~result["Value"].isin(hidden_opts)]
            val_col, count_col = "Value", "Count"

        elif data_type == "scale":
            result = scale_analysis(df, selected_col)
            val_col, count_col = "Scale", "Count"

        else:
            result = None

        if result is not None and not result.empty:

            # Renamed copy for display & export
            result_display = result.rename(columns={val_col: header_val, count_col: header_count})
            display_val_col   = header_val
            display_count_col = header_count

            chart_title = custom_title if custom_title.strip() else f"{chart_type} — {selected_col}"
            st.markdown(f"### :material/bar_chart: {chart_title}")

            fig = None

            # ── Helper: sample N discrete colors from selected colorscale ──
            def get_scale_colors(n):
                if n < 2:
                    return [COLOR_SCALE_PREVIEWS.get(chart_theme_display, ["#667eea"])[0]]
                try:
                    samples = pc.sample_colorscale(
                        chart_theme,
                        [i / (n - 1) for i in range(n)]
                    )
                    return samples
                except Exception:
                    return PLOTLY_COLORS[:n]

            n_cats = len(result)
            disc_colors = get_scale_colors(n_cats)

            # ── Helper: build text column for bar charts ──
            total = result[count_col].sum()
            def build_bar_text(row):
                parts = []
                if show_name:    parts.append(str(row[val_col]))
                if show_count:   parts.append(str(int(row[count_col])))
                if show_percent: parts.append(f"{row[count_col]/total*100:.1f}%")
                txt = "<br>".join(parts) if parts else None
                if txt and label_bold:
                    txt = f"<b>{txt}</b>"
                return txt

            has_bar_text = show_count or show_percent or show_name
            if has_bar_text:
                result = result.copy()
                result["_text"] = result.apply(build_bar_text, axis=1)
                text_arg = "_text"
            else:
                text_arg = None

            # ── Pie/donut textinfo ──
            pie_parts = []
            if show_name:    pie_parts.append("label")
            if show_count:   pie_parts.append("value")
            if show_percent: pie_parts.append("percent")
            pie_textinfo = "+".join(pie_parts) if pie_parts else "none"

            # ── Legend layout dict ──
            legend_layout = dict(showlegend=show_legend)
            if show_legend and legend_cfg:
                legend_layout["legend"] = legend_cfg

            # ── Margin: extra bottom space when legend is below ──
            is_bottom_legend = show_legend and legend_cfg.get("y", 0) < 0
            margin_b = 120 if is_bottom_legend else 50

            # ── Build figure ──
            if chart_type == "Bar Chart":
                fig = px.bar(
                    result, x=val_col, y=count_col,
                    color=val_col, color_discrete_sequence=disc_colors,
                    text=text_arg,
                    title=chart_title if custom_title.strip() else None,
                )
                if has_bar_text:
                    fig.update_traces(
                        textposition=text_position,
                        textfont=dict(size=label_size, weight=700 if label_bold else 400),
                    )
                fig.update_layout(
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
                fig.update_xaxes(type="category")

            elif chart_type == "Horizontal Bar":
                fig = px.bar(
                    result, x=count_col, y=val_col,
                    orientation="h",
                    color=val_col, color_discrete_sequence=disc_colors,
                    text=text_arg,
                    title=chart_title if custom_title.strip() else None,
                )
                if has_bar_text:
                    fig.update_traces(
                        textposition=text_position,
                        textfont=dict(size=label_size, weight=700 if label_bold else 400),
                    )
                fig.update_layout(
                    yaxis=dict(autorange="reversed", title=None),
                    height=chart_height, margin=dict(t=60, b=margin_b),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

            elif chart_type == "Pie Chart":
                fig = px.pie(
                    result, names=val_col, values=count_col,
                    color_discrete_sequence=disc_colors,
                    title=chart_title if custom_title.strip() else None,
                )
                fig.update_traces(
                    textinfo=pie_textinfo,
                    textposition="outside" if text_position == "outside" else "inside",
                    textfont=dict(size=label_size, weight=700 if label_bold else 400),
                )
                fig.update_layout(
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

            elif chart_type == "Donut Chart":
                fig = px.pie(
                    result, names=val_col, values=count_col,
                    color_discrete_sequence=disc_colors, hole=0.45,
                    title=chart_title if custom_title.strip() else None,
                )
                fig.update_traces(
                    textinfo=pie_textinfo,
                    textposition="outside" if text_position == "outside" else "inside",
                    textfont=dict(size=label_size, weight=700 if label_bold else 400),
                )
                fig.update_layout(
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

            elif chart_type == "Treemap":
                fig = px.treemap(
                    result, path=[val_col], values=count_col,
                    color=count_col, color_continuous_scale=chart_theme,
                    title=chart_title if custom_title.strip() else None,
                )
                fig.update_layout(
                    coloraxis_showscale=False,
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

            elif chart_type == "Area Chart":
                fig = px.area(
                    result, x=val_col, y=count_col,
                    color_discrete_sequence=disc_colors,
                    title=chart_title if custom_title.strip() else None,
                )
                fig.update_layout(
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
                fig.update_xaxes(type="category")

            elif chart_type == "Line Chart":
                fig = px.line(
                    result, x=val_col, y=count_col,
                    markers=True, color_discrete_sequence=disc_colors,
                    title=chart_title if custom_title.strip() else None,
                )
                fig.update_layout(
                    height=chart_height, margin=dict(t=60, b=margin_b, l=50, r=50),
                    **legend_layout,
                )
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
                fig.update_xaxes(type="category")

            # ── Render chart ──
            if fig:
                chart_config = {
                    "toImageButtonOptions": {
                        "filename": f"{selected_col}_{chart_type.replace(' ', '_').lower()}",
                        "width": 1400,
                        "height": chart_height,
                        "scale": 2,
                        "format": "png",
                    },
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["sendDataToCloud"],
                }
                st.plotly_chart(
                    fig, use_container_width=True, config=chart_config,
                    theme=None if force_light_mode else "streamlit"
                )

                # ── Tabel Preview ──
                with st.expander(":material/table_chart: Lihat & Edit Tabel Data", expanded=True):
                    st.dataframe(result_display, use_container_width=True, hide_index=True)

                # ── Export Section ──
                st.markdown("---")
                st.markdown("### :material/download: Ekspor")

                col_exp1, col_exp2, col_exp3 = st.columns(3)

                # 1. Download XLSX
                with col_exp1:
                    try:
                        xlsx_bytes = df_to_xlsx(result_display)
                        st.download_button(
                            ":material/table: Download Tabel (XLSX)",
                            data=xlsx_bytes,
                            file_name=f"{selected_col}_analisis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"XLSX error: {e}")

                # 2. Download Chart PNG
                with col_exp2:
                    try:
                        # Force white background for export
                        fig_export = go.Figure(fig)
                        fig_export.update_layout(
                            paper_bgcolor="white",
                            plot_bgcolor="white",
                            font_color="#1a1a2e",
                        )
                        png_bytes = fig_export.to_image(
                            format="png", width=1400, height=chart_height, scale=2
                        )
                        st.download_button(
                            ":material/image: Download Chart (PNG)",
                            data=png_bytes,
                            file_name=f"{selected_col}_chart.png",
                            mime="image/png",
                            use_container_width=True,
                        )
                    except Exception:
                        st.warning("Install `kaleido` untuk Download Chart PNG: `pip install kaleido`")

                # 3. Download Table PNG
                with col_exp3:
                    try:
                        tbl_title = f"{selected_col} — {data_type.replace('_',' ').title()}"
                        table_png = table_to_png(result_display, title=tbl_title)
                        st.download_button(
                            ":material/image: Download Tabel (PNG)",
                            data=table_png,
                            file_name=f"{selected_col}_tabel.png",
                            mime="image/png",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Tabel PNG error: {e}")

        else:
            st.warning(":material/warning: Tidak ada data untuk ditampilkan.")

# ══════════════════════════════════════════════════
# TAB 2: WORDCLOUD
# ══════════════════════════════════════════════════
with tab_wordcloud:
    st.markdown("### :material/cloud: Wordcloud Generator")

    text_columns = df.select_dtypes(include=["object"]).columns.tolist()

    if not text_columns:
        st.warning(":material/warning: Tidak ada kolom teks dalam dataset.")
    else:
        col_config, col_preview = st.columns([1, 2])

        with col_config:
            st.markdown("#### :material/settings: Pengaturan")

            selected_wc_col = st.selectbox(":material/edit_document: Pilih Kolom Teks", text_columns, key="wc_col")

            st.markdown("---")

            max_words = st.slider("Jumlah Kata Maksimum", 20, 200, 100, step=10, key="wc_maxwords")
            top_n     = st.slider("Top Keywords", 5, 50, 20, key="wc_topn")

            colormap = st.selectbox(
                ":material/palette: Skema Warna",
                ["Set2", "Set3", "Pastel1", "Dark2", "Accent", "tab10", "viridis", "plasma", "inferno", "cool"],
                key="wc_colormap",
            )

            bg_color = st.color_picker("Background Color", value="#0e1117", key="wc_bgcolor")

            st.markdown("---")

            extra_stopwords_input = st.text_area(
                ":material/block: Stopwords Tambahan",
                placeholder="Masukkan kata yang ingin diabaikan, pisahkan dengan koma.\nContoh: dll, dsb, yg, tdk",
                height=100,
                key="wc_stopwords",
            )
            extra_stopwords = set()
            if extra_stopwords_input:
                extra_stopwords = {w.strip().lower() for w in extra_stopwords_input.split(",") if w.strip()}

            generate_btn = st.button(
                ":material/rocket_launch: Generate Wordcloud",
                type="primary", use_container_width=True, key="wc_generate"
            )

        with col_preview:
            if generate_btn and selected_wc_col:
                with st.spinner("Menganalisis teks..."):
                    analysis  = analyze_text_column(df, selected_wc_col, extra_stopwords=extra_stopwords)
                    word_freq = analysis["word_freq"]
                    top_kw    = get_top_keywords(word_freq, top_n=top_n)

                c1, c2, c3 = st.columns(3)
                for c, (val, lbl) in zip(
                    [c1, c2, c3],
                    [
                        (analysis["total_responses"], "Total Respons"),
                        (analysis["total_words"],     "Total Kata"),
                        (analysis["unique_words"],    "Kata Unik"),
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
                    wc = generate_wordcloud(
                        word_freq, width=1000, height=500,
                        background_color=bg_color, colormap=colormap, max_words=max_words,
                    )

                    if wc:
                        fig_wc, ax = plt.subplots(figsize=(12, 6))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        fig_wc.patch.set_facecolor(bg_color)
                        plt.tight_layout(pad=0)
                        st.pyplot(fig_wc, use_container_width=True)
                        plt.close(fig_wc)

                        buf = BytesIO()
                        wc.to_image().save(buf, format="PNG")
                        buf.seek(0)
                        st.download_button(
                            ":material/download: Download Wordcloud (PNG)",
                            data=buf,
                            file_name=f"wordcloud_{selected_wc_col}.png",
                            mime="image/png",
                            use_container_width=True,
                        )

                    st.markdown("### :material/key: Top Keywords")

                    fig_kw = px.bar(
                        top_kw, x="Frequency", y="Keyword",
                        orientation="h",
                        color="Frequency", color_continuous_scale="Purples",
                        text="Frequency",
                    )
                    fig_kw.update_layout(
                        yaxis=dict(autorange="reversed"),
                        margin=dict(t=20, b=20),
                        height=max(300, top_n * 25),
                        coloraxis_showscale=False,
                    )
                    if force_light_mode:
                        fig_kw.update_layout(**EXPORT_LAYOUT)
                    fig_kw.update_traces(textposition="outside")
                    wc_cfg = {"toImageButtonOptions": {"filename": f"{selected_wc_col}_keywords", "scale": 2}, "displaylogo": False}
                    st.plotly_chart(fig_kw, use_container_width=True, config=wc_cfg,
                                    theme=None if force_light_mode else "streamlit")

                    with st.expander(":material/table_chart: Lihat Tabel Kata"):
                        st.dataframe(top_kw, use_container_width=True, hide_index=True)
                        try:
                            xlsx_kw = df_to_xlsx(top_kw)
                            st.download_button(
                                ":material/table: Download Keywords (XLSX)",
                                data=xlsx_kw,
                                file_name=f"keywords_{selected_wc_col}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                        except Exception:
                            csv_kw = top_kw.to_csv(index=False)
                            st.download_button(
                                ":material/description: Download Keywords (CSV)",
                                data=csv_kw,
                                file_name=f"keywords_{selected_wc_col}.csv",
                                mime="text/csv",
                            )
                else:
                    st.warning(":material/warning: Tidak ada kata yang ditemukan setelah cleaning.")

            elif not generate_btn:
                st.markdown("")
                st.markdown("")
                st.info(":material/arrow_back: Pilih kolom teks dan klik **Generate Wordcloud** untuk memulai analisis.")

render_sidebar_footer()
render_page_footer()
