"""
Chart Builder Utility — Full-Featured Quick-Chart untuk Tugas Saya
====================================================================
Dipakai di halaman Pembagian Tugas (tab "Tugas Saya") supaya anggota tim
bisa memilih SATU pertanyaan (dari dropdown yang HANYA berisi soal yang
ditugaskan ke mereka) lalu melihat & mengatur chart-nya selengkap
halaman Visualization — color scale, tipe chart, label, sort, legend,
custom title, dst — tanpa perlu pindah halaman dan mencari kolom yang
sama secara manual dari dropdown semua kolom dataset.

Logika analisis & chart di sini SENGAJA disalin selaras dengan
pages/4_visualization.py (bukan versi simplified) supaya hasilnya
konsisten persis dengan yang biasa dipakai user di halaman Visualization.
"""

import textwrap
import pandas as pd
import plotly.express as px
import plotly.colors as pc

from utils.pivot_analysis import single_choice_analysis, scale_analysis
from utils.multi_select_analysis import multi_choice_analysis, get_multiple_choice_preview

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
    "Purples":           "⚪ 🟣 ⚫", "Blues":             "⚪ 🔵 ⚫", "Greens":            "⚪ 🟢 ⚫",
    "Pinks":             "⚪ 🔴 ⚫", "Viridis":           "🟣 🟢 🟡", "Plasma":            "🔵 🟣 🟡",
    "Inferno":           "⚫ 🔴 🟡", "Turbo":             "🔵 🟢 🔴", "Sunset":            "⚪ 🔴 ⚫",
    "Teal":              "⚪ 🟢 🔵", "Oranges":           "⚪ 🟠 ⚫", "Reds":              "⚪ 🔴 ⚫",
    "Magma":             "⚫ 🟣 🟡", "Cividis":           "⚫ 🔵 🟡", "Sunset Dark":       "⚫ 🔴 🟠",
    "Ice":               "⚪ 🔵 🔵", "Rainbow":           "🔴 🟢 🔵", "Deep":              "⚫ 🔵 🟢",
    "Electric":          "⚫ 🟠 🟡", "Mint":              "⚪ 🟢 🟢", "Ocean":             "⚫ 🔵 🟢",
    "Darkmint":          "🟢 🟢 ⚫", "Earth":             "🟤 🟢 ⚪", "Yellow-Green-Blue": "🟡 🟢 🔵",
    "Yellow-Orange-Red": "🟡 🟠 🔴", "Purple-Blue-Green": "🟣 🔵 🟢", "Blue-Red":          "🔵 🟣 🔴",
    "Picnic":            "🔵 🔴 🔴", "Portland":          "🔵 🔴 🟡", "Blackbody":         "⚫ 🔴 🟡",
    "Dark Neon":         "⚫ 🟢 🟡", "Sunset Fire":       "⚫ 🔴 🟠", "Cyber Purple":      "⚫ 🟣 🔵",
    "Tropical":          "🔵 🟢 🟠", "Bold Navy":         "🔵 🔵 🟣", "Lava":              "⚫ 🔴 🟠",
    "Forest Dark":       "⚫ 🟢 🟡", "Midnight Blue":     "⚫ 🔵 🟣", "Deep Teal":         "⚫ 🟢 🔵",
    "Crimson":           "⚫ 🔴 🟣",
}

PLOTLY_SCALE_MAP = {
    "Purples": "Purples", "Blues": "Blues", "Greens": "Greens", "Pinks": "RdPu",
    "Viridis": "Viridis", "Plasma": "Plasma", "Inferno": "Inferno", "Turbo": "Turbo",
    "Sunset": "RdGy", "Teal": "Teal", "Oranges": "Oranges", "Reds": "Reds",
    "Magma": "Magma", "Cividis": "Cividis", "Sunset Dark": "Sunset", "Ice": "Ice",
    "Rainbow": "Rainbow", "Deep": "deep", "Electric": "Electric", "Mint": "Mint",
    "Ocean": "ocean", "Darkmint": "darkmint", "Earth": "earth",
    "Yellow-Green-Blue": "YlGnBu", "Yellow-Orange-Red": "YlOrRd", "Purple-Blue-Green": "PuBuGn",
    "Blue-Red": "Bluered", "Picnic": "Picnic", "Portland": "Portland", "Blackbody": "Blackbody",
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

CHART_OPTIONS_PER_TYPE = {
    "single_choice":   ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
    "multiple_choice": ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"],
    "scale":           ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Area Chart", "Line Chart"],
}

DEFAULT_CHART_PER_TYPE = {
    "single_choice": "Pie Chart",
    "multiple_choice": "Horizontal Bar",
    "scale": "Bar Chart",
}


def compute_dynamic_margin(chart_type, labels, margin_b_base=50, px_per_char=7.5, min_l=50, min_b=50):
    """Hitung margin Plotly secara dinamis — sama persis dengan pages/4_visualization.py."""
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


def get_colors(n: int, theme: str = "Purples"):
    if n < 2:
        return [PLOTLY_COLORS[0]]
    try:
        return pc.sample_colorscale(theme, [i / (n - 1) for i in range(n)])
    except Exception:
        return PLOTLY_COLORS[:n]


def analyze_for_task(df: pd.DataFrame, column: str, question_type: str, mc_delimiter: str = ",", mc_main_options=None):
    """
    Jalankan analisis sesuai tipe pertanyaan. Return (result_df, val_col, count_col)
    atau (None, None, None) kalau tipe tidak didukung (open_text/skip — ditangani
    terpisah lewat halaman Wordcloud).
    """
    if column not in df.columns:
        return None, None, None

    if question_type == "single_choice":
        return single_choice_analysis(df, column), "Value", "Count"
    elif question_type == "multiple_choice":
        return multi_choice_analysis(df, column, delimiter=mc_delimiter, main_options=mc_main_options), "Value", "Count"
    elif question_type == "scale":
        return scale_analysis(df, column), "Scale", "Count"
    else:
        return None, None, None


def build_full_chart(
    df: pd.DataFrame,
    column: str,
    question_type: str,
    chart_type: str,
    chart_theme: str = "Purples",
    solid_color: str = None,
    bar_sort: str = "Default",
    show_count: bool = True,
    show_percent: bool = True,
    show_name: bool = False,
    text_position: str = "outside",
    label_size: int = 13,
    label_bold: bool = False,
    show_legend: bool = False,
    legend_cfg: dict = None,
    chart_title: str = None,
    chart_height: int = 500,
    chart_width: int = 0,
    force_light_layout: dict = None,
    mc_delimiter: str = ",",
    mc_main_options=None,
):
    """
    Bangun chart Plotly LENGKAP untuk satu pertanyaan — replika 1:1 dari
    logika di pages/4_visualization.py (tab Charts), supaya opsi yang
    tersedia di "Tugas Saya" sama persis dengan yang biasa dipakai di
    halaman Visualization (color scale, sort, label, legend, dst),
    bukan versi simplified.

    Return dict: {fig, result, val_col, count_col, colors, n_cats}
    """
    result, val_col, count_col = analyze_for_task(df, column, question_type, mc_delimiter, mc_main_options)
    if result is None or result.empty:
        return {"fig": None, "result": None, "val_col": None, "count_col": None, "colors": None, "n_cats": 0}

    chart_title = chart_title or f"{chart_type} - {column}"

    n_cats = len(result)
    colors = get_colors(n_cats, chart_theme)
    total = result[count_col].sum()

    result = result.copy()
    result[val_col] = result[val_col].astype(str)

    def build_text(row):
        parts = []
        if show_name:    parts.append(str(row[val_col]))
        if show_count:   parts.append(str(int(row[count_col])))
        if show_percent: parts.append(f"{row[count_col]/total*100:.1f}%" if total else "0.0%")
        txt = "<br>".join(parts) if parts else None
        return f"<b>{txt}</b>" if txt and label_bold else txt

    result["_text"] = result.apply(build_text, axis=1) if (show_count or show_percent or show_name) else None
    result["_disp_label"] = result[val_col].apply(lambda x: "<br>".join(textwrap.wrap(str(x), width=35)))

    if chart_type in ("Bar Chart", "Horizontal Bar"):
        if bar_sort == "asc":
            result = result.sort_values(count_col, ascending=True)
        elif bar_sort == "desc":
            result = result.sort_values(count_col, ascending=False)

    fig = None
    _margin = dict(t=60, b=50, l=50, r=50)

    if chart_type == "Bar Chart":
        fig = px.bar(result, x=val_col, y=count_col, color=val_col,
                     color_discrete_sequence=[solid_color]*n_cats if solid_color else colors, text="_text")
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        _margin = compute_dynamic_margin("Bar Chart", result[val_col].tolist())
        _margin["b"] = max(_margin.get("b", 50), 120)
    elif chart_type == "Horizontal Bar":
        fig = px.bar(result, x=count_col, y=val_col, orientation="h", color=val_col,
                     color_discrete_sequence=[solid_color]*n_cats if solid_color else colors, text="_text")
        fig.update_yaxes(autorange="reversed", automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        _margin = compute_dynamic_margin("Horizontal Bar", result[val_col].tolist())
        _margin["l"] = max(_margin.get("l", 50), 200)
    elif chart_type == "Pie Chart":
        fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors)
        if show_count or show_percent:
            fig.update_traces(text=result["_text"], textinfo="text",
                               hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>")
        _margin = compute_dynamic_margin("Pie Chart", result[val_col].tolist())
    elif chart_type == "Donut Chart":
        fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors, hole=0.45)
        if show_count or show_percent:
            fig.update_traces(text=result["_text"], textinfo="text",
                               hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>")
        _margin = compute_dynamic_margin("Donut Chart", result[val_col].tolist())
    elif chart_type == "Treemap":
        fig = px.treemap(result, path=[val_col], values=count_col, color=count_col, color_continuous_scale=chart_theme)
        _margin = dict(t=60, b=50, l=50, r=50)
    elif chart_type == "Area Chart":
        fig = px.area(result, x=val_col, y=count_col)
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        _margin = compute_dynamic_margin("Area Chart", result[val_col].tolist())
    elif chart_type == "Line Chart":
        fig = px.line(result, x=val_col, y=count_col, markers=True)
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        _margin = compute_dynamic_margin("Line Chart", result[val_col].tolist())

    if fig:
        # BUG DIPERBAIKI (sama dgn pages/4_visualization.py): Treemap
        # crash ValueError kalau text_position (mis. "outside") diteruskan
        # ke update_traces() -- Treemap Plotly cuma terima enum posisi
        # berbeda ('top left' dst). Skip textposition khusus utk Treemap.
        if chart_type != "Treemap":
            fig.update_traces(textposition=text_position, textfont=dict(size=label_size))
        else:
            fig.update_traces(textfont=dict(size=label_size))
        fig.update_layout(height=chart_height, margin=_margin, showlegend=show_legend, title=chart_title)
        if chart_width > 0:
            fig.update_layout(width=chart_width)
        if show_legend and legend_cfg:
            fig.update_layout(legend=legend_cfg)
        if force_light_layout:
            fig.update_layout(**force_light_layout)

    return {"fig": fig, "result": result, "val_col": val_col, "count_col": count_col, "colors": colors, "n_cats": n_cats}
