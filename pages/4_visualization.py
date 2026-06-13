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

COLOR_SCALES = [
    "Purples", "Blues", "Greens", "Pinks", "Viridis", "Plasma", "Inferno", "Turbo", "Sunset", "Teal",
    "Oranges", "Reds", "Magma", "Cividis", "Sunset Dark", "Ice", "Rainbow", "Deep", "Electric", "Mint",
    "Ocean", "Darkmint", "Earth", "Yellow-Green-Blue", "Yellow-Orange-Red", "Purple-Blue-Green", "Blue-Red", "Picnic", "Portland", "Blackbody",
    "Dark Neon", "Sunset Fire", "Cyber Purple", "Tropical", "Bold Navy",
    "Lava", "Forest Dark", "Midnight Blue", "Deep Teal", "Crimson",
]

SCALE_EMOJIS = {
    "Purples":           "⚪ 🟣 ⚫",
    "Blues":             "⚪ 🔵 ⚫",
    "Greens":            "⚪ 🟢 ⚫",
    "Pinks":             "⚪ 🔴 ⚫",
    "Viridis":           "🟣 🟢 🟡",
    "Plasma":            "🔵 🟣 🟡",
    "Inferno":           "⚫ 🔴 🟡",
    "Turbo":             "🔵 🟢 🔴",
    "Sunset":            "⚪ 🔴 ⚫",
    "Teal":              "⚪ 🟢 🔵",
    "Oranges":           "⚪ 🟠 ⚫",
    "Reds":              "⚪ 🔴 ⚫",
    "Magma":             "⚫ 🟣 🟡",
    "Cividis":           "⚫ 🔵 🟡",
    "Sunset Dark":       "⚫ 🔴 🟠",
    "Ice":               "⚪ 🔵 🔵",
    "Rainbow":           "🔴 🟢 🔵",
    "Deep":              "⚫ 🔵 🟢",
    "Electric":          "⚫ 🟠 🟡",
    "Mint":              "⚪ 🟢 🟢",
    "Ocean":             "⚫ 🔵 🟢",
    "Darkmint":          "🟢 🟢 ⚫",
    "Earth":             "🟤 🟢 ⚪",
    "Yellow-Green-Blue": "🟡 🟢 🔵",
    "Yellow-Orange-Red": "🟡 🟠 🔴",
    "Purple-Blue-Green": "🟣 🔵 🟢",
    "Blue-Red":          "🔵 🟣 🔴",
    "Picnic":            "🔵 🔴 🔴",
    "Portland":          "🔵 🔴 🟡",
    "Blackbody":         "⚫ 🔴 🟡",
    "Dark Neon":         "⚫ 🟢 🟡",
    "Sunset Fire":       "⚫ 🔴 🟠",
    "Cyber Purple":      "⚫ 🟣 🔵",
    "Tropical":          "🔵 🟢 🟠",
    "Bold Navy":         "🔵 🔵 🟣",
    "Lava":              "⚫ 🔴 🟠",
    "Forest Dark":       "⚫ 🟢 🟡",
    "Midnight Blue":     "⚫ 🔵 🟣",
    "Deep Teal":         "⚫ 🟢 🔵",
    "Crimson":           "⚫ 🔴 🟣",
}

# Map display names to Plotly colorscale names
PLOTLY_SCALE_MAP = {
    "Purples":           "Purples",
    "Blues":             "Blues",
    "Greens":            "Greens",
    "Pinks":             "RdPu",
    "Viridis":           "Viridis",
    "Plasma":            "Plasma",
    "Inferno":           "Inferno",
    "Turbo":             "Turbo",
    "Sunset":            "RdGy",
    "Teal":              "Teal",
    "Oranges":           "Oranges",
    "Reds":              "Reds",
    "Magma":             "Magma",
    "Cividis":           "Cividis",
    "Sunset Dark":       "Sunset",
    "Ice":               "Ice",
    "Rainbow":           "Rainbow",
    "Deep":              "deep",
    "Electric":          "Electric",
    "Mint":              "Mint",
    "Ocean":             "ocean",
    "Darkmint":          "darkmint",
    "Earth":             "earth",
    "Yellow-Green-Blue": "YlGnBu",
    "Yellow-Orange-Red": "YlOrRd",
    "Purple-Blue-Green": "PuBuGn",
    "Blue-Red":          "Bluered",
    "Picnic":            "Picnic",
    "Portland":          "Portland",
    "Blackbody":         "Blackbody",
    "Dark Neon":    [[0, "#0a0a0a"], [0.33, "#00ff88"], [0.66, "#00ccff"], [1, "#ffff00"]],
    "Sunset Fire":  [[0, "#0d0000"], [0.33, "#8b0000"], [0.66, "#ff4500"], [1, "#ff8c00"]],
    "Cyber Purple": [[0, "#0a000f"], [0.33, "#4a0080"], [0.66, "#9b30ff"], [1, "#00bfff"]],
    "Tropical":     [[0, "#003366"], [0.33, "#006699"], [0.66, "#00cc99"], [1, "#ff6600"]],
    "Bold Navy":    [[0, "#000033"], [0.33, "#003399"], [0.66, "#0066ff"], [1, "#9933ff"]],
    "Lava":         [[0, "#1a0000"], [0.33, "#cc0000"], [0.66, "#ff6600"], [1, "#ffcc00"]],
    "Forest Dark":  [[0, "#001a00"], [0.33, "#006600"], [0.66, "#33cc33"], [1, "#99ff00"]],
    "Midnight Blue": [[0, "#000011"], [0.33, "#000066"], [0.66, "#0033cc"], [1, "#6699ff"]],
    "Deep Teal":    [[0, "#001111"], [0.33, "#004444"], [0.66, "#008888"], [1, "#00ddcc"]],
    "Crimson":      [[0, "#0f0005"], [0.33, "#660022"], [0.66, "#cc0044"], [1, "#ff66aa"]],
}

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()

def render_copy_button(png_bytes: bytes, label: str = "Copy PNG", key: str = "copy"):
    import base64
    import streamlit.components.v1 as components
    b64_img = base64.b64encode(png_bytes).decode('utf-8')
    safe_key = key.replace(" ", "_").lower()
    html_code = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600&display=swap');
    body {{ margin: 0; padding: 0; display: flex; justify-content: flex-start; }}
    button {{
        background-color: transparent;
        border: 1px solid rgba(124, 143, 247, 0.5);
        color: #7c8ff7;
        padding: 0.4rem 1rem;
        border-radius: 6px;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.1s ease;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }}
    button:hover {{ border-color: #7c8ff7; background-color: rgba(124, 143, 247, 0.15); }}
    .icon {{ width: 16px; height: 16px; fill: currentColor; }}
    </style>
    <button id="btn_{safe_key}" onclick="copyImg_{safe_key}()">
        <svg class="icon" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
        <span id="txt_{safe_key}">{label}</span>
    </button>
    <script>
    async function copyImg_{safe_key}() {{
        const btn = document.getElementById('btn_{safe_key}');
        try {{
            const res = await fetch('data:image/png;base64,{b64_img}');
            const blob = await res.blob();
            const item = new ClipboardItem({{ [blob.type]: blob }});
            await navigator.clipboard.write([item]);
            
            btn.style.color = '#10b981';
            btn.style.borderColor = '#10b981';
            btn.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg> Copied!';
        }} catch(e) {{
            console.error(e);
            btn.innerHTML = '❌ Gagal (Gunakan Download)';
        }}
        setTimeout(() => {{
            btn.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg> {label}';
            btn.style.color = '#7c8ff7';
            btn.style.borderColor = 'rgba(124, 143, 247, 0.5)';
        }}, 2000);
    }}
    </script>
    """
    components.html(html_code, height=35)

def compute_dynamic_margin(
    chart_type: str,
    labels: list,
    margin_b_base: int = 50,
    px_per_char: float = 7.5,
    min_l: int = 50,
    min_b: int = 50,
) -> dict:
    """Hitung margin Plotly secara dinamis."""
    max_len = max((len(str(lbl)) for lbl in labels), default=0)
    if chart_type == "Horizontal Bar":
        l = max(min_l, int(max_len * px_per_char))
        return dict(t=60, b=margin_b_base, l=l, r=60)
    elif chart_type in ("Bar Chart", "Area Chart", "Line Chart"):
        b = max(min_b, int(max_len * px_per_char * 0.5))
        return dict(t=60, b=b, l=60, r=50)
    else:
        pad = max(30, int(max_len * px_per_char * 0.3))
        return dict(t=60, b=margin_b_base + pad, l=50 + pad, r=50 + pad)

st.markdown("# :material/bar_chart: Visualization")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning(":material/warning: Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# ──────────────────────────────────────────────────
# SIDEBAR SETTINGS
# ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### :material/palette: Pengaturan Visual")

    chart_theme_display = st.selectbox(
        "Color Scale", 
        COLOR_SCALES, 
        index=0, 
        key="vis_colorscale",
        format_func=lambda x: f"{SCALE_EMOJIS.get(x, '●')} {x}"
    )
    chart_theme = PLOTLY_SCALE_MAP.get(chart_theme_display, chart_theme_display)

    use_solid_color = st.checkbox(":material/format_paint: Warna Solid (Bar Chart)", value=False)
    solid_color = st.color_picker("Pilih Warna", value="#4169e1") if use_solid_color else None

    bar_sort = st.radio(":material/sort: Urutan Bar", ["Default", "asc", "desc"], index=0)
    chart_height = st.slider("Tinggi Chart (px)", 300, 1000, 500, step=50)

    st.markdown("##### Label")
    lbl_c1, lbl_c2, lbl_c3 = st.columns(3)
    show_count   = lbl_c1.checkbox("Nilai", value=True)
    show_percent = lbl_c2.checkbox("Persen", value=True)
    show_name    = lbl_c3.checkbox("Nama", value=False)

    text_position = st.radio("Posisi Label", ["outside", "inside", "auto"], index=0, horizontal=True)

    lbl_sz_col, lbl_bd_col = st.columns([2, 1])
    label_size = lbl_sz_col.slider("Ukuran Font", 8, 28, 13, step=1)
    label_bold = lbl_bd_col.checkbox("Bold", value=False)

    show_legend = st.checkbox("Tampilkan Legenda", value=False)
    if show_legend:
        legend_pos = st.selectbox("Posisi", ["Right", "Bottom", "Top", "Left"], index=0)
        LEGEND_MAP = {
            "Right":  dict(x=1.02, y=1, xanchor="left", yanchor="top"),
            "Bottom": dict(x=0.5, y=-0.2, xanchor="center", yanchor="top", orientation="h"),
            "Top":    dict(x=0.5, y=1.1, xanchor="center", yanchor="bottom", orientation="h"),
            "Left":   dict(x=-0.2, y=1, xanchor="right", yanchor="top"),
        }
        legend_cfg = LEGEND_MAP[legend_pos]
    else:
        legend_cfg = {}

    custom_title = st.text_input("Override Judul", value="", placeholder="Contoh: Distribusi Jawaban")

    st.markdown("### :material/print: Export Settings")
    force_light_mode = st.checkbox("Paksa Latar Terang", help="Putihkan latar belakang untuk siap cetak.")

EXPORT_LAYOUT = get_light_plotly_layout()

# ──────────────────────────────────────────────────
# TAB NAVIGATION
# ──────────────────────────────────────────────────
tab_charts, tab_wordcloud = st.tabs([":material/insights: Charts", ":material/cloud: Wordcloud"])

# ══════════════════════════════════════════════════
# TAB 1: CHARTS
# ══════════════════════════════════════════════════
with tab_charts:
    st.markdown("### :material/settings_input_component: Pilih Kolom")
    col_select, type_select, chart_select = st.columns(3)

    with col_select:
        selected_col = st.selectbox("Kolom", df.columns.tolist(), key="vis_col")

    def detect_multiselect(series: pd.Series, threshold: float = 0.20) -> bool:
        non_null = series.dropna().astype(str)
        return non_null.str.contains(",").mean() >= threshold if len(non_null) > 0 else False

    is_multiselect = detect_multiselect(df[selected_col])

    with type_select:
        type_options = ["single_choice", "multiple_choice", "scale"]
        default_idx  = 1 if is_multiselect else 0
        data_type = st.selectbox("Tipe Data", type_options, index=default_idx, format_func=lambda x: x.replace("_", " ").title())

    with chart_select:
        chart_options = {
            "single_choice":  ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
            "multiple_choice":["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
            "scale":          ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Area Chart", "Line Chart"],
        }
        chart_type = st.selectbox("Tipe Chart", chart_options.get(data_type, ["Bar Chart"]))

    if st.button(":material/refresh: Refresh"): st.rerun()
    st.markdown("---")

    if selected_col:
        if data_type == "single_choice":
            result = single_choice_analysis(df, selected_col)
            val_col, count_col = "Value", "Count"
        elif data_type == "multiple_choice":
            result = multi_choice_analysis(df, selected_col)
            val_col, count_col = "Value", "Count"
        elif data_type == "scale":
            result = scale_analysis(df, selected_col)
            val_col, count_col = "Scale", "Count"
        else: result = None

        if result is not None and not result.empty:
            chart_title = custom_title if custom_title.strip() else f"{chart_type} - {selected_col}"
            st.markdown(f"### :material/analytics: {chart_title}")

            def get_colors(n):
                if n < 2: return [PLOTLY_COLORS[0]]
                try: return pc.sample_colorscale(chart_theme, [i / (n - 1) for i in range(n)])
                except: return PLOTLY_COLORS[:n]

            n_cats = len(result)
            colors = get_colors(n_cats)

            total = result[count_col].sum()
            def build_text(row):
                parts = []
                if show_name:    parts.append(str(row[val_col]))
                if show_count:   parts.append(str(int(row[count_col])))
                if show_percent: parts.append(f"{row[count_col]/total*100:.1f}%")
                txt = "<br>".join(parts) if parts else None
                return f"<b>{txt}</b>" if txt and label_bold else txt

            result = result.copy()
            result["_text"] = result.apply(build_text, axis=1) if (show_count or show_percent or show_name) else None
            result[val_col] = result[val_col].astype(str)

            if chart_type in ("Bar Chart", "Horizontal Bar"):
                if bar_sort == "asc": result = result.sort_values(count_col, ascending=True)
                elif bar_sort == "desc": result = result.sort_values(count_col, ascending=False)

            fig = None
            if chart_type == "Bar Chart":
                fig = px.bar(result, x=val_col, y=count_col, color=val_col, color_discrete_sequence=[solid_color]*n_cats if solid_color else colors, text="_text")
                fig.update_xaxes(type="category", tickangle=-45, automargin=True)
                _margin = compute_dynamic_margin("Bar Chart", result[val_col].tolist())
            elif chart_type == "Horizontal Bar":
                fig = px.bar(result, x=count_col, y=val_col, orientation="h", color=val_col, color_discrete_sequence=[solid_color]*n_cats if solid_color else colors, text="_text")
                fig.update_yaxes(autorange="reversed", automargin=True)
                _margin = compute_dynamic_margin("Horizontal Bar", result[val_col].tolist())
            elif chart_type == "Pie Chart":
                fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors)
                _margin = compute_dynamic_margin("Pie Chart", result[val_col].tolist())
            elif chart_type == "Donut Chart":
                fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors, hole=0.45)
                _margin = compute_dynamic_margin("Donut Chart", result[val_col].tolist())
            elif chart_type == "Treemap":
                fig = px.treemap(result, path=[val_col], values=count_col, color=count_col, color_continuous_scale=chart_theme)
                _margin = dict(t=60, b=50, l=50, r=50)
            elif chart_type == "Area Chart":
                fig = px.area(result, x=val_col, y=count_col)
                fig.update_xaxes(type="category", tickangle=-45, automargin=True)
                _margin = compute_dynamic_margin("Area Chart", result[val_col].tolist())
            elif chart_type == "Line Chart":
                fig = px.line(result, x=val_col, y=count_col, markers=True)
                fig.update_xaxes(type="category", tickangle=-45, automargin=True)
                _margin = compute_dynamic_margin("Line Chart", result[val_col].tolist())

            if fig:
                fig.update_traces(textposition=text_position, textfont=dict(size=label_size))
                fig.update_layout(height=chart_height, margin=_margin, showlegend=show_legend)
                if show_legend: fig.update_layout(legend=legend_cfg)
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
                st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False}, theme=None if force_light_mode else "streamlit")

                try:
                    fig_exp = go.Figure(fig)
                    fig_exp.update_layout(paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#1a1a2e"), width=1400)
                    png = fig_exp.to_image(format="png", scale=2)
                    render_copy_button(png, "Copy Chart PNG", key="copy_chart")
                except: pass

                # ── Tabel Preview ──
                st.markdown("---")
                with st.container(border=True):
                    st.markdown("#### :material/table_chart: Data Table Preview")
                    display_result = result.drop(columns=["_text"], errors="ignore")
                    st.dataframe(display_result, use_container_width=True, hide_index=True)
                    
                    try:
                        table_png = table_to_png(display_result, title="")
                        render_copy_button(table_png, "Copy Table PNG", key="copy_table")
                    except: pass

                # ── Export Section ──
                st.markdown("### :material/download: Ekspor Data")
                xlsx_data = df_to_xlsx(display_result)
                st.download_button(
                    label=":material/table: Download Tabel (XLSX)",
                    data=xlsx_data,
                    file_name=f"{selected_col}_analisis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

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
            colormap = st.selectbox(":material/palette: Skema Warna", ["Set2", "Set3", "Pastel1", "Dark2", "Accent", "tab10", "viridis", "plasma"], key="wc_colormap")
            bg_color = st.color_picker("Background Color", value="#FFFFFF", key="wc_bgcolor")
            st.markdown("---")
            extra_stopwords_input = st.text_area(":material/block: Stopwords Tambahan", placeholder="dll, dsb, yg, tdk", key="wc_stopwords")
            generate_btn = st.button(":material/rocket_launch: Generate Wordcloud", type="primary", use_container_width=True)

        with col_preview:
            if generate_btn and selected_wc_col:
                with st.spinner("Menganalisis teks..."):
                    extra_sw = {w.strip().lower() for w in extra_stopwords_input.split(",") if w.strip()}
                    analysis  = analyze_text_column(df, selected_wc_col, extra_stopwords=extra_sw)
                    word_freq = analysis["word_freq"]
                    top_kw    = get_top_keywords(word_freq, top_n=top_n)

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Respons", analysis["total_responses"])
                c2.metric("Total Kata", analysis["total_words"])
                c3.metric("Kata Unik", analysis["unique_words"])

                if word_freq:
                    wc = generate_wordcloud(word_freq, width=1000, height=500, background_color=bg_color, colormap=colormap, max_words=max_words)
                    if wc:
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
                                data=img_bytes, 
                                file_name=f"wordcloud_{selected_wc_col}.png", 
                                mime="image/png", 
                                use_container_width=True
                            )
                        with c_dl2:
                            render_copy_button(img_bytes, "Copy Wordcloud PNG", key="copy_wc")

                    st.markdown("### :material/key: Top Keywords")
                    fig_kw = px.bar(top_kw, x="Frequency", y="Keyword", orientation="h", color="Frequency", color_continuous_scale="Purples", text="Frequency")
                    fig_kw.update_layout(yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20), height=max(300, top_n * 25), coloraxis_showscale=False)
                    if force_light_mode: fig_kw.update_layout(**EXPORT_LAYOUT)
                    st.plotly_chart(fig_kw, use_container_width=True, theme=None if force_light_mode else "streamlit")

                    try:
                        fig_kw_exp = go.Figure(fig_kw)
                        fig_kw_exp.update_layout(paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#1a1a2e"), width=1400)
                        kw_png = fig_kw_exp.to_image(format="png", scale=2)
                        render_copy_button(kw_png, "Copy Chart PNG", key="copy_kw_chart")
                    except: pass

                    with st.expander(":material/table_chart: Lihat Tabel Kata"):
                        st.dataframe(top_kw, use_container_width=True, hide_index=True)
                else:
                    st.warning("Tidak ada kata yang ditemukan.")
            else:
                st.info(":material/arrow_back: Pilih kolom teks dan klik **Generate Wordcloud**.")

render_sidebar_footer()
render_page_footer()
