"""
Chart Builder Utility — Reusable Quick-Chart Generator
=======================================================
Dipakai di halaman Pembagian Tugas (tab "Tugas Saya") supaya anggota tim
bisa langsung LIHAT chart & analisis untuk tiap pertanyaan yang
ditugaskan kepada mereka, TANPA harus pindah ke halaman Visualization
dan mencari kolomnya satu per satu secara manual.

Ekstraksi dari logika chart di pages/4_visualization.py, disederhanakan
jadi 1 fungsi yang langsung menghasilkan (result_df, fig) dari
(df, column, question_type) — dipakai di kedua halaman supaya hasil
chart konsisten dan tidak ada duplikasi logika analisis.
"""

import textwrap
import pandas as pd
import plotly.express as px
import plotly.colors as pc

from utils.pivot_analysis import single_choice_analysis, scale_analysis
from utils.multi_select_analysis import multi_choice_analysis, get_multiple_choice_preview

DEFAULT_COLOR_THEME = "Purples"

# Chart default per tipe pertanyaan — dipilih otomatis, TANPA perlu user
# klik-klik memilih dulu (beda dengan halaman Visualization yang punya
# banyak opsi kustomisasi; di sini prioritasnya "langsung lihat semua").
DEFAULT_CHART_PER_TYPE = {
    "single_choice": "Pie Chart",
    "multiple_choice": "Horizontal Bar",
    "scale": "Bar Chart",
}

CHART_OPTIONS_PER_TYPE = {
    "single_choice": ["Pie Chart", "Donut Chart", "Bar Chart", "Horizontal Bar", "Treemap"],
    "multiple_choice": ["Horizontal Bar", "Bar Chart", "Pie Chart", "Donut Chart", "Treemap"],
    "scale": ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Area Chart", "Line Chart"],
}


def get_colors(n: int, theme: str = DEFAULT_COLOR_THEME):
    if n < 2:
        return [pc.sample_colorscale(theme, [0.6])[0]]
    try:
        return pc.sample_colorscale(theme, [i / (n - 1) for i in range(n)])
    except Exception:
        return px.colors.qualitative.Plotly[:n]


def analyze_for_task(df: pd.DataFrame, column: str, question_type: str) -> tuple:
    """
    Jalankan analisis sesuai tipe pertanyaan. Return (result_df, val_col, count_col)
    atau (None, None, None) kalau tipe tidak didukung untuk chart cepat
    (mis. 'open_text' — itu ditangani terpisah lewat wordcloud, 'skip' —
    memang sengaja dilewati saat deteksi tipe pertanyaan).
    """
    if column not in df.columns:
        return None, None, None

    if question_type == "single_choice":
        result = single_choice_analysis(df, column)
        return result, "Value", "Count"
    elif question_type == "multiple_choice":
        result = multi_choice_analysis(df, column, delimiter=",")
        return result, "Value", "Count"
    elif question_type == "scale":
        result = scale_analysis(df, column)
        return result, "Scale", "Count"
    else:
        return None, None, None


def build_quick_chart(
    df: pd.DataFrame,
    column: str,
    question_type: str,
    chart_type: str = None,
    chart_theme: str = DEFAULT_COLOR_THEME,
    title: str = None,
    height: int = 420,
):
    """
    Bangun chart Plotly cepat untuk satu pertanyaan, siap tampil langsung
    (dipakai di tab "Tugas Saya" — tidak perlu pindah ke halaman
    Visualization untuk lihat 1 chart per pertanyaan yang ditugaskan).

    Return dict:
        {
            "fig": plotly Figure atau None (kalau tipe tidak didukung / data kosong),
            "result": DataFrame hasil analisis (untuk tabel & export PNG),
            "val_col": nama kolom kategori,
            "count_col": nama kolom hitungan,
            "colors": list warna yang dipakai (utk generate_matplotlib_chart nanti),
            "chart_type": tipe chart yang dipakai,
        }
    """
    result, val_col, count_col = analyze_for_task(df, column, question_type)
    if result is None or result.empty:
        return {"fig": None, "result": None, "val_col": None, "count_col": None, "colors": None, "chart_type": None}

    chart_type = chart_type or DEFAULT_CHART_PER_TYPE.get(question_type, "Bar Chart")
    title = title or column

    result = result.copy()
    result[val_col] = result[val_col].astype(str)
    n_cats = len(result)
    colors = get_colors(n_cats, chart_theme)
    total = result[count_col].sum()

    result["_text"] = result.apply(
        lambda row: f"{int(row[count_col])} ({row[count_col]/total*100:.1f}%)" if total else str(int(row[count_col])),
        axis=1,
    )
    result["_disp_label"] = result[val_col].apply(lambda x: "<br>".join(textwrap.wrap(str(x), width=35)))

    fig = None
    margin = dict(t=50, b=50, l=50, r=50)

    if chart_type == "Bar Chart":
        fig = px.bar(result, x=val_col, y=count_col, color=val_col, color_discrete_sequence=colors, text="_text")
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        margin["b"] = 120
    elif chart_type == "Horizontal Bar":
        fig = px.bar(result, x=count_col, y=val_col, orientation="h", color=val_col,
                     color_discrete_sequence=colors, text="_text")
        fig.update_yaxes(autorange="reversed", automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
        margin["l"] = 180
    elif chart_type == "Pie Chart":
        fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors)
        fig.update_traces(text=result["_text"], textinfo="text",
                           hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>")
    elif chart_type == "Donut Chart":
        fig = px.pie(result, names=val_col, values=count_col, color_discrete_sequence=colors, hole=0.45)
        fig.update_traces(text=result["_text"], textinfo="text",
                           hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>")
    elif chart_type == "Treemap":
        fig = px.treemap(result, path=[val_col], values=count_col, color=count_col, color_continuous_scale=chart_theme)
    elif chart_type == "Area Chart":
        fig = px.area(result, x=val_col, y=count_col)
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())
    elif chart_type == "Line Chart":
        fig = px.line(result, x=val_col, y=count_col, markers=True)
        fig.update_xaxes(type="category", tickangle=-30, automargin=True,
                          ticktext=result["_disp_label"].tolist(), tickvals=result[val_col].tolist())

    if fig:
        fig.update_traces(textposition="outside" if chart_type in ("Bar Chart", "Horizontal Bar") else "inside")
        fig.update_layout(height=height, margin=margin, showlegend=False, title=title)

    return {
        "fig": fig, "result": result, "val_col": val_col, "count_col": count_col,
        "colors": colors, "chart_type": chart_type,
    }
