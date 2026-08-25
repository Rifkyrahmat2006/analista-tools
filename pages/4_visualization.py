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
from utils.multi_select_analysis import multi_choice_analysis, get_multiple_choice_preview
from utils.export_helpers import table_to_png, render_copy_button
from utils.text_analysis import analyze_text_column, get_top_keywords, generate_wordcloud
from utils.theme import inject_theme_css, get_light_plotly_layout, render_sidebar_footer, render_page_footer
from utils.auth import render_user_badge_sidebar
from utils.permissions import require_permission

st.set_page_config(page_title="Visualization", layout="wide")

inject_theme_css()

require_permission("visualization.view")
render_user_badge_sidebar()

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

WC_SCALE_EMOJIS = {
    "Set2": "🟢 🟠 🔵",
    "Set3": "🟢 🟡 🟣",
    "Pastel1": "🔴 🔵 🟢",
    "Dark2": "🟢 🟠 🟣",
    "Accent": "🟢 🟣 🟠",
    "tab10": "🔵 🟠 🟢",
    "viridis": "🟣 🟢 🟡",
    "plasma": "🔵 🟣 🟡",
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

# render_copy_button() dipindah ke utils/export_helpers.py supaya bisa
# dipakai ulang di halaman lain (Pembagian Tugas / Tugas Saya) tanpa
# duplikasi kode — lihat import di atas.

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
    st.markdown("##### Dimensi Visual")
    chart_width = st.slider("Lebar Chart (0 = Auto Layar)", 0, 2000, 0, step=50)
    chart_height = st.slider("Tinggi Chart (px)", 300, 1500, 500, step=50)
    table_height = st.slider("Tinggi Tabel (px)", 200, 1500, 400, step=50)

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
            # Delimiter dapat dikustomisasi jika jawaban sendiri mengandung koma
            mc_delimiter = st.text_input(
                "Karakter Pemisah (Delimiter)", value=",",
                help="Karakter yang memisahkan tiap jawaban dalam satu sel. Ganti menjadi ';' jika jawaban Anda sendiri mengandung koma."
            )

            # ─ Deteksi otomatis opsi utama (seperti di tab Analysis) ─
            # Ambil opsi yang muncul cukup sering sebagai 'main options'
            # Semua jawaban di luar itu (termasuk isi 'Other:') akan digrup jadi 'Other'
            mc_preview = get_multiple_choice_preview(df[selected_col], delimiter=mc_delimiter)
            auto_main_options = mc_preview.get("main_names", [])

            # Tampilkan info ke pengguna
            with st.expander(":material/tune: Opsi Terdeteksi (klik untuk edit)", expanded=False):
                st.caption("Opsi berikut terdeteksi sebagai pilihan utama. Semua jawaban di luar daftar ini akan digabung menjadi **Other**.")
                # Biarkan user edit opsi utama kalau ada yang ingin ditambah/hapus
                custom_main_str = st.text_area(
                    "Opsi Utama (satu per baris)",
                    value="\n".join(auto_main_options),
                    height=150,
                    key="mc_main_options_edit"
                )
                main_options_final = [o.strip() for o in custom_main_str.split("\n") if o.strip()]

            result = multi_choice_analysis(
                df, selected_col,
                delimiter=mc_delimiter,
                main_options=main_options_final if main_options_final else None
            )
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

            result = result.copy()
            result[val_col] = result[val_col].astype(str)

            # ── Label untuk tooltip / text di batang ──
            def build_text(row):
                parts = []
                if show_name:    parts.append(str(row[val_col]))
                if show_count:   parts.append(str(int(row[count_col])))
                if show_percent: parts.append(f"{row[count_col]/total*100:.1f}%")
                txt = "<br>".join(parts) if parts else None
                return f"<b>{txt}</b>" if txt and label_bold else txt

            result["_text"] = result.apply(build_text, axis=1) if (show_count or show_percent or show_name) else None

            # ── Display label (baris terpisah, TIDAK mengubah val_col) ──
            # Ini dipakai untuk tick axis supaya teks panjang tidak meluber
            import textwrap
            result["_disp_label"] = result[val_col].apply(
                lambda x: "<br>".join(textwrap.wrap(str(x), width=35))
            )

            if chart_type in ("Bar Chart", "Horizontal Bar"):
                if bar_sort == "asc": result = result.sort_values(count_col, ascending=True)
                elif bar_sort == "desc": result = result.sort_values(count_col, ascending=False)

            # Buat mapping val → display_label agar fig bisa pakai ticktext
            label_map = dict(zip(result[val_col], result["_disp_label"]))

            fig = None
            if chart_type == "Bar Chart":
                fig = px.bar(
                    result, x=val_col, y=count_col,
                    color=val_col,
                    color_discrete_sequence=[solid_color]*n_cats if solid_color else colors,
                    text="_text"
                )
                # Ganti tick label dengan versi yang dibungkus
                fig.update_xaxes(
                    type="category", tickangle=-30, automargin=True,
                    ticktext=result["_disp_label"].tolist(),
                    tickvals=result[val_col].tolist()
                )
                _margin = compute_dynamic_margin("Bar Chart", result[val_col].tolist())
                _margin["b"] = max(_margin.get("b", 50), 120)
            elif chart_type == "Horizontal Bar":
                fig = px.bar(
                    result, x=count_col, y=val_col, orientation="h",
                    color=val_col,
                    color_discrete_sequence=[solid_color]*n_cats if solid_color else colors,
                    text="_text"
                )
                fig.update_yaxes(autorange="reversed", automargin=True,
                                 ticktext=result["_disp_label"].tolist(),
                                 tickvals=result[val_col].tolist())
                _margin = compute_dynamic_margin("Horizontal Bar", result[val_col].tolist())
                _margin["l"] = max(_margin.get("l", 50), 200)
            elif chart_type == "Pie Chart":
                fig = px.pie(
                    result, names=val_col, values=count_col,
                    color_discrete_sequence=colors
                )
                # Tampilkan label yang singkat (bungkus) + value jika checkbox aktif
                if show_count or show_percent:
                    fig.update_traces(
                        text=result["_text"],
                        textinfo="text",
                        hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>"
                    )
                _margin = compute_dynamic_margin("Pie Chart", result[val_col].tolist())
            elif chart_type == "Donut Chart":
                fig = px.pie(
                    result, names=val_col, values=count_col,
                    color_discrete_sequence=colors, hole=0.45
                )
                if show_count or show_percent:
                    fig.update_traces(
                        text=result["_text"],
                        textinfo="text",
                        hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>"
                    )
                _margin = compute_dynamic_margin("Donut Chart", result[val_col].tolist())
            elif chart_type == "Treemap":
                fig = px.treemap(result, path=[val_col], values=count_col, color=count_col, color_continuous_scale=chart_theme)
                _margin = dict(t=60, b=50, l=50, r=50)
            elif chart_type == "Area Chart":
                fig = px.area(result, x=val_col, y=count_col)
                fig.update_xaxes(
                    type="category", tickangle=-30, automargin=True,
                    ticktext=result["_disp_label"].tolist(),
                    tickvals=result[val_col].tolist()
                )
                _margin = compute_dynamic_margin("Area Chart", result[val_col].tolist())
            elif chart_type == "Line Chart":
                fig = px.line(result, x=val_col, y=count_col, markers=True)
                fig.update_xaxes(
                    type="category", tickangle=-30, automargin=True,
                    ticktext=result["_disp_label"].tolist(),
                    tickvals=result[val_col].tolist()
                )
                _margin = compute_dynamic_margin("Line Chart", result[val_col].tolist())

            if fig:
                fig.update_traces(textposition=text_position, textfont=dict(size=label_size))
                fig.update_layout(height=chart_height, margin=_margin, showlegend=show_legend)
                if chart_width > 0: fig.update_layout(width=chart_width)
                if show_legend: fig.update_layout(legend=legend_cfg)
                if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
                use_container = chart_width == 0
                st.plotly_chart(fig, use_container_width=use_container, config={"displaylogo": False}, theme=None if force_light_mode else "streamlit")

                if st.button("📸 Tampilkan Gambar Statis (Untuk Copy-Paste ke Word)", key="btn_static_vis", help="Klik untuk membuat versi gambar statis dari grafik yang bisa di-copy paste."):
                    try:
                        from utils.export_helpers import generate_matplotlib_chart
                        png_bytes = generate_matplotlib_chart(
                            chart_type=chart_type, 
                            df=result, 
                            val_col=val_col, 
                            count_col=count_col, 
                            colors=colors, 
                            title=chart_title, 
                            solid_color=solid_color if use_solid_color else None,
                            text_col="_text" if "_text" in result.columns else None
                        )
                        # Tombol "Copy PNG" langsung di sini — BUG YANG
                        # DIPERBAIKI (dilaporkan user): sebelumnya cuma ada
                        # instruksi klik-kanan-manual pada gambar, padahal
                        # render_copy_button() (klik tombol -> langsung ke
                        # clipboard via navigator.clipboard.write) sudah ada
                        # di file ini dan dipakai di tempat lain (Table PNG,
                        # Wordcloud PNG) tapi lupa dipasang di chart utama —
                        # justru fitur yang paling sering dipakai malah masih
                        # manual (klik kanan gambar -> copy image).
                        render_copy_button(png_bytes, "Copy Chart PNG", key="copy_main_chart")
                        st.image(png_bytes, caption=f"{chart_title} (Copyable PNG)")
                    except Exception as e:
                        st.error(f"Gagal mem-generate gambar statis. Error: {e}")

                # ── Tabel Preview ──
                st.markdown("---")
                with st.container(border=True):
                    st.markdown("#### :material/table_chart: Data Table Preview")
                    display_result = result.drop(columns=["_text"], errors="ignore")
                    st.dataframe(display_result, use_container_width=True, hide_index=True, height=table_height)
                    
                    try:
                        table_png = table_to_png(display_result, title="")
                        render_copy_button(table_png, "Copy Table PNG", key="copy_table")
                        with st.expander(":material/image: Tampilkan Gambar (Untuk Copy Manual)"):
                            st.info("Klik kanan pada gambar di bawah dan pilih **Copy Image** atau **Save Image As**.")
                            st.image(table_png)
                    except Exception as e:
                        st.warning(f":material/warning: Gagal membuat gambar tabel: {e}")

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
        selected_wc_col = st.selectbox(":material/edit_document: Pilih Kolom Teks", text_columns, key="wc_col")
        st.markdown("---")
        from utils.wordcloud_ui import render_wordcloud_section
        render_wordcloud_section(df, selected_wc_col, key_prefix="viz_wc", force_light_mode=force_light_mode)

render_sidebar_footer()
render_page_footer()
