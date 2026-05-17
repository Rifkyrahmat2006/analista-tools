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
    # Original
    "Purples", "Blues", "Greens", "Pinks", "Viridis", "Plasma", "Inferno", "Turbo", "Sunset", "Teal",
    "Oranges", "Reds", "Magma", "Cividis", "Sunset Dark", "Ice", "Rainbow", "Deep", "Electric", "Mint",
    "Ocean", "Darkmint", "Earth", "Yellow-Green-Blue", "Yellow-Orange-Red", "Purple-Blue-Green", "Blue-Red", "Picnic", "Portland", "Blackbody",
    # Kontras tinggi — terlihat jelas di background putih
    "Dark Neon", "Sunset Fire", "Cyber Purple", "Tropical", "Bold Navy",
    "Lava", "Forest Dark", "Midnight Blue", "Deep Teal", "Crimson",
]

SCALE_EMOJIS = {
    # Original
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
    # Kontras tinggi
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
    # Original
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
    # Kontras tinggi (custom hex)
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

    chart_theme_display = st.selectbox(
        "Color Scale", 
        COLOR_SCALES, 
        index=0, 
        key="vis_colorscale",
        format_func=lambda x: f"{x} — {SCALE_EMOJIS.get(x, '')}"
    )
    chart_theme = PLOTLY_SCALE_MAP.get(chart_theme_display, chart_theme_display)

    # ── Solid color mode for Bar / Horizontal Bar ──
    use_solid_color = st.checkbox(
        ":material/palette: Warna Solid (Bar Chart)",
        value=False,
        key="use_solid_color",
        help="Aktifkan untuk mewarnai semua batang dengan satu warna solid."
    )
    if use_solid_color:
        SOLID_COLOR_OPTIONS = {
            "Biru Tua (#003f8f)":     "#003f8f",
            "Biru Royal (#4169e1)":   "#4169e1",
            "Biru Langit (#0ea5e9)":  "#0ea5e9",
            "Teal (#0d9488)":         "#0d9488",
            "Hijau Tua (#166534)":    "#166534",
            "Hijau (#16a34a)":        "#16a34a",
            "Hijau Muda (#65a30d)":   "#65a30d",
            "Ungu Tua (#581c87)":     "#581c87",
            "Ungu (#7c3aed)":         "#7c3aed",
            "Indigo (#4338ca)":       "#4338ca",
            "Merah Tua (#991b1b)":    "#991b1b",
            "Merah (#dc2626)":        "#dc2626",
            "Oranye (#ea580c)":       "#ea580c",
            "Amber (#d97706)":        "#d97706",
            "Kuning (#ca8a04)":       "#ca8a04",
            "Pink Tua (#9d174d)":     "#9d174d",
            "Pink (#db2777)":         "#db2777",
            "Abu Tua (#374151)":      "#374151",
            "Abu (#6b7280)":          "#6b7280",
            "Hitam (#111827)":        "#111827",
            "Kustom":                 "custom",
        }
        solid_color_label = st.selectbox(
            "Pilih Warna",
            list(SOLID_COLOR_OPTIONS.keys()),
            key="solid_color_label",
        )
        if SOLID_COLOR_OPTIONS[solid_color_label] == "custom":
            solid_color = st.color_picker("Warna Kustom", value="#4169e1", key="solid_color_custom")
        else:
            solid_color = SOLID_COLOR_OPTIONS[solid_color_label]
        # Preview warna terpilih
        st.markdown(
            f'<div style="width:100%;height:18px;border-radius:6px;background:{solid_color};"></div>',
            unsafe_allow_html=True
        )
    else:
        solid_color = None

    # ── Sort order for Bar / Horizontal Bar ──
    bar_sort = st.radio(
        ":material/sort: Urutan Bar Chart",
        ["Default", "asc", "desc"],
        index=0,
        horizontal=False,
        key="bar_sort",
        help="Hanya berlaku untuk Bar Chart dan Horizontal Bar."
    )

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

        # ── Legend label editor ──
        st.markdown("###### ✏️ Edit Nama Legenda")
        st.caption("Isi untuk mengganti nama label legenda di chart. Kosongkan = gunakan nama asli.")
        if "legend_label_overrides" not in st.session_state:
            st.session_state.legend_label_overrides = {}
    else:
        legend_cfg = {}
        if "legend_label_overrides" not in st.session_state:
            st.session_state.legend_label_overrides = {}

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

    # ── Auto-detect multi-select column ──
    def detect_multiselect(series: pd.Series, threshold: float = 0.20) -> bool:
        """Return True if >threshold fraction of non-null values contain a comma."""
        non_null = series.dropna().astype(str)
        if len(non_null) == 0:
            return False
        frac = non_null.str.contains(",").mean()
        return frac >= threshold

    is_multiselect_detected = detect_multiselect(df[selected_col])

    with type_select:
        type_options = ["single_choice", "multiple_choice", "scale"]
        # Auto-suggest multiple_choice if detected AND user hasn't manually overridden
        saved_type   = st.session_state.get("question_types", {}).get(selected_col)
        if saved_type:
            default_idx = type_options.index(saved_type) if saved_type in type_options else 0
        elif is_multiselect_detected:
            default_idx = 1  # multiple_choice
        else:
            default_idx = 0
        data_type = st.selectbox(
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

    # ── Multi-select detection banner ──
    if is_multiselect_detected and data_type == "single_choice":
        st.warning(
            ":material/warning: **Kolom ini terdeteksi sebagai jawaban pilih-beberapa (multi-select).** "
            "Jawaban dipisah koma sehingga setiap kombinasi dianggap unik. "
            "Ubah **Tipe Data → Multiple Choice** agar setiap opsi dihitung secara terpisah."
        )
    elif is_multiselect_detected and data_type == "multiple_choice":
        st.info(
            ":material/check_circle: **Mode Multi-Select aktif.** "
            "Jawaban dipisah per opsi — setiap pilihan dihitung secara individual."
        )

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
                    return [PLOTLY_COLORS[0]]
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

            # ── Legend label editor: render inputs in sidebar ──
            legend_label_overrides = {}
            if show_legend:
                with st.sidebar:
                    orig_labels = [str(v) for v in result[val_col].tolist()]
                    # Reset widget keys if column changed
                    if st.session_state.get("_legend_col") != selected_col:
                        for _old_lbl in st.session_state.get("_legend_orig_labels", []):
                            _k = f"leg_lbl_{st.session_state.get('_legend_col', '')}_{_old_lbl}"
                            if _k in st.session_state:
                                del st.session_state[_k]
                        st.session_state["_legend_col"] = selected_col
                    st.session_state["_legend_orig_labels"] = orig_labels

                    for lbl in orig_labels:
                        key = f"leg_lbl_{selected_col}_{lbl}"
                        # DO NOT set value= — let Streamlit manage widget state via key
                        st.text_input(
                            f"{lbl}",
                            placeholder=f"Ganti nama '{lbl}'...",
                            key=key,
                        )
                        # Read back what user typed from session_state
                        typed = st.session_state.get(key, "").strip()
                        if typed:
                            legend_label_overrides[lbl] = typed

            # ── Legend layout dict ──
            legend_layout = dict(showlegend=show_legend)
            if show_legend and legend_cfg:
                legend_layout["legend"] = legend_cfg

            # ── Margin: extra bottom space when legend is below ──
            is_bottom_legend = show_legend and legend_cfg.get("y", 0) < 0
            margin_b = 120 if is_bottom_legend else 50

            # ── Apply legend label overrides: rename values in result BEFORE charting ──
            if legend_label_overrides:
                result = result.copy()
                result[val_col] = result[val_col].astype(str).replace(legend_label_overrides)

            # ── Force val_col to string so Plotly treats it as CATEGORICAL ──
            # Without this, numeric values (e.g. 2025, 2024) cause Plotly to
            # render a continuous gradient colorbar instead of discrete legend squares.
            result = result.copy()
            result[val_col] = result[val_col].astype(str)

            # ── Apply sort for Bar / Horizontal Bar ──
            if chart_type in ("Bar Chart", "Horizontal Bar"):
                if bar_sort == "asc":
                    result = result.sort_values(count_col, ascending=False).reset_index(drop=True)
                elif bar_sort == "desc":
                    result = result.sort_values(count_col, ascending=True).reset_index(drop=True)
                # else: Default — keep original order

            # ── Build figure ──
            fig = None

            if chart_type == "Bar Chart":
                bar_colors = [solid_color] * n_cats if solid_color else disc_colors
                fig = px.bar(
                    result, x=val_col, y=count_col,
                    color=val_col, color_discrete_sequence=bar_colors,
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
                bar_colors = [solid_color] * n_cats if solid_color else disc_colors
                fig = px.bar(
                    result, x=count_col, y=val_col,
                    orientation="h",
                    color=val_col, color_discrete_sequence=bar_colors,
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
