"""
Export Utility
Helpers for exporting tables as PNG for download and open-ended analysis to XLSX.
Always renders in LIGHT theme for print-readiness.
"""

import io
import re
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def normalize_color(c):
    """
    Konversi warna dari format Plotly ('rgb(r,g,b)', 'rgba(r,g,b,a)') ke hex
    yang bisa diterima matplotlib.

    BUG YANG DIPERBAIKI (dilaporkan user — fitur "Copy PNG" di halaman
    Visualization selalu gagal untuk color scale tertentu, mis. Viridis):
    plotly.colors.sample_colorscale() mengembalikan warna dalam bentuk
    string 'rgb(68, 1, 84)', BUKAN hex. matplotlib versi yang dipakai di
    sini (3.11.1) TIDAK menerima format string itu untuk parameter
    color=/facecolor= pada beberapa jenis plot (bar/pie) -> melempar
    ValueError "'facecolor' or 'color' argument must be a valid color or
    sequence of colors", yang di generate_matplotlib_chart() sebelumnya
    cuma di-catch generik jadi pesan error tidak jelas ke user, atau di
    tempat lain (fig_kw_exp) di-swallow total oleh `except: pass` — user
    klik "Copy PNG" dan TIDAK TERJADI APA-APA tanpa penjelasan.

    Warna yang sudah valid untuk matplotlib (hex '#rrggbb', nama warna
    'red', 'blue', dst) diteruskan apa adanya — fungsi ini idempotent.
    """
    if not isinstance(c, str):
        return c
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", c)
    if not m:
        return c  # sudah hex / nama warna valid / bentuk lain — biarkan
    r, g, b = (max(0, min(255, float(v))) for v in m.groups()[:3])
    return "#{:02x}{:02x}{:02x}".format(int(round(r)), int(round(g)), int(round(b)))


def normalize_colors(colors):
    """Terapkan normalize_color() ke tiap elemen list/tuple warna. None/falsy diteruskan apa adanya."""
    if not colors:
        return colors
    return [normalize_color(c) for c in colors]


def render_copy_button(png_bytes: bytes, label: str = "Copy PNG", key: str = "copy"):
    """
    Render tombol "Copy PNG" yang langsung menyalin gambar ke clipboard
    (klik tombol -> navigator.clipboard.write, tidak perlu klik-kanan
    manual pada gambar). Dipindah ke sini dari pages/4_visualization.py
    supaya bisa dipakai ulang di halaman lain (mis. Pembagian Tugas /
    Tugas Saya) tanpa import lintas-halaman Streamlit (yang akan
    menjalankan ulang seluruh kode UI halaman itu — tidak aman).

    CATATAN (lihat juga skill/README project): tombol ini butuh halaman
    dimuat via HTTPS — navigator.clipboard API diblokir browser di
    halaman HTTP biasa (non-secure context). Kalau tombol selalu gagal
    dengan pesan "Gunakan Download", cek dulu address bar browser ada
    ikon gembok/HTTPS, bukan soal kode di sini.
    """
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


def table_to_png(df: pd.DataFrame, title: str = "", max_rows: int = 30) -> bytes:
    """
    Render a pandas DataFrame as a styled table PNG using matplotlib.
    Always uses light theme (white background, dark text) for print-readiness.
    """
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]

    display_df = df.head(max_rows)
    n_rows, n_cols = display_df.shape

    # Calculate proportional column widths based on max string length
    raw_col_widths = []
    for col in display_df.columns:
        max_len = max(
            display_df[col].astype(str).map(len).max() if not display_df.empty else 0,
            len(str(col))
        )
        raw_col_widths.append(max_len)
    
    total_len = sum(raw_col_widths)
    if total_len == 0: total_len = 1
    
    # Add padding and ensure a minimum width proportion
    col_widths = [max(0.08, (w + 4) / (total_len + n_cols * 4)) for w in raw_col_widths]
    # Normalize to sum to 1.0
    sum_widths = sum(col_widths)
    col_widths = [w / sum_widths for w in col_widths]

    # Calculate figure size (wider for more text)
    fig_width = max(8.0, total_len * 0.15)
    # Refined height calculation for "auto height" feel
    # Each row with scale 1.6 takes roughly 0.35 - 0.4 inches
    fig_height = 0.4 * (n_rows + 1) # +1 for header row

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    if title:
        fig.suptitle(title, fontsize=15, fontweight="bold", color="#1a1a2e", y=0.98, fontfamily="serif")
        # Increase height slightly if title exists
        fig.set_figheight(fig_height + 0.8)

    fig.patch.set_facecolor("#ffffff")

    # Create table
    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        loc="center",
        cellLoc="center",
        colWidths=col_widths
    )

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.6)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d0d0e0")
        if row == 0:
            # Header row — purple accent
            cell.set_facecolor("#667eea")
            cell.set_text_props(color="white", fontweight="bold", fontsize=12, fontfamily="serif")
        else:
            # Data rows — alternating light colors
            if row % 2 == 0:
                cell.set_facecolor("#f5f7fa")
            else:
                cell.set_facecolor("#ffffff")
            cell.set_text_props(color="#1a1a2e", fontfamily="serif")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def export_oe_analysis(
    preprocessed_df,
    candidate_groups: dict,
    final_mapping: dict,
    theme_summary_df,
    audit_log_df,
    analysis_run_info: dict,
) -> bytes:
    """
    Export hasil analisis pertanyaan terbuka yang sudah difinalisasi ke multi-sheet XLSX.

    Sheets yang dihasilkan:
        1. responses        — pemetaan response → tema final
        2. candidate_groups — ringkasan kandidat kelompok
        3. theme_summary    — frekuensi dan persentase tema
        4. analysis_config  — parameter analisis run
        5. audit_log        — riwayat semua perubahan analis

    PENTING: Hanya memanfaatkan final_mapping (sumber kebenaran tervalidasi),
    BUKAN cluster labels awal.
    """
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:

        # --- Sheet 1: responses ---
        if preprocessed_df is not None and not preprocessed_df.empty:
            resp_rows = []
            for _, row in preprocessed_df.iterrows():
                resp_id = row["response_id"]
                theme_val = final_mapping.get(resp_id, "Unclassified")
                if isinstance(theme_val, list):
                    theme_val = ", ".join(theme_val)
                    
                resp_rows.append({
                    "response_id": resp_id,
                    "original_response": row.get("original_text", ""),
                    "cleaned_response": row.get("cleaned_text", ""),
                    "validation_status": row.get("validation_status", ""),
                    "final_theme": theme_val,
                })
            pd.DataFrame(resp_rows).to_excel(writer, index=False, sheet_name="responses")
        else:
            pd.DataFrame(columns=["response_id", "original_response", "cleaned_response",
                                   "validation_status", "final_theme"]).to_excel(
                writer, index=False, sheet_name="responses"
            )

        # --- Sheet 2: candidate_groups ---
        cg_rows = []
        for group_id, group in candidate_groups.items():
            cg_rows.append({
                "group_id": group_id,
                "candidate_label": group.candidate_label,
                "final_theme_name": group.final_theme_name,
                "size": group.size,
                "status": group.status,
                "is_other": group.is_other,
                "top_keywords": ", ".join(group.top_keywords[:8]),
                "top_phrases": ", ".join(group.top_phrases[:5]),
                "silhouette_score": round(group.silhouette_score, 4),
            })
        pd.DataFrame(cg_rows).to_excel(writer, index=False, sheet_name="candidate_groups")

        # --- Sheet 3: theme_summary ---
        if theme_summary_df is not None and not theme_summary_df.empty:
            theme_summary_df.to_excel(writer, index=False, sheet_name="theme_summary")
        else:
            pd.DataFrame(columns=["Tema", "Jumlah", "Persentase"]).to_excel(
                writer, index=False, sheet_name="theme_summary"
            )

        # --- Sheet 4: analysis_config ---
        if analysis_run_info:
            config_rows = [{"parameter": k, "value": str(v)} for k, v in analysis_run_info.items()]
            pd.DataFrame(config_rows).to_excel(writer, index=False, sheet_name="analysis_config")

        # --- Sheet 5: audit_log ---
        if audit_log_df is not None and not audit_log_df.empty:
            audit_log_df.to_excel(writer, index=False, sheet_name="audit_log")
        else:
            pd.DataFrame(columns=["timestamp", "action", "entity_type", "entity_id",
                                   "old_value", "new_value", "user"]).to_excel(
                writer, index=False, sheet_name="audit_log"
            )

    buf.seek(0)
    return buf.getvalue()

def generate_matplotlib_chart(chart_type, df, val_col, count_col, colors, title, solid_color=None, text_col=None,
                               show_legend=False, legend_pos="Right"):
    """
    Generate a static matplotlib chart based on the selected plot type for easy copy-pasting.

    show_legend/legend_pos: BUG DIPERBAIKI (dilaporkan user) -- gambar
    statis (PNG copy-paste) sebelumnya TIDAK PERNAH menggambar legenda
    sama sekali, walau di chart interaktif Plotly legenda muncul kalau
    checkbox "Tampilkan Legenda" dicentang. Untuk chart kategorikal (tiap
    kategori/opsi punya warna sendiri: Bar/Horizontal Bar/Pie/Donut/
    Treemap), legenda direplikasi via proxy Patch per label+warna --
    matplotlib TIDAK otomatis membuat legend per-bar seperti Plotly
    (semua ax.bar() dalam satu panggilan dianggap 1 "series").
    Area/Line Chart dilewati (cuma 1 garis/area, tidak ada per-kategori
    warna utk dilegenda-kan -- sama seperti perilaku Plotly aslinya).
    """
    plt.rcParams["font.family"] = "sans-serif"
    fig, ax = plt.subplots(figsize=(10, 6))

    # Normalisasi warna dari format Plotly ('rgb(r,g,b)') ke hex — lihat
    # docstring normalize_color() untuk detail bug yang diperbaiki.
    colors = normalize_colors(colors)
    solid_color = normalize_color(solid_color) if solid_color else solid_color

    bg_color = "white"
    text_color = "black"
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    # Pre-process labels
    labels = df[val_col].astype(str).tolist()
    plot_labels = labels
    if text_col and text_col in df.columns:
        plot_labels = []
        for txt in df[text_col]:
            if pd.isna(txt) or not txt:
                plot_labels.append("")
            else:
                plot_labels.append(str(txt).replace("<b>", "").replace("</b>", "").replace("<br>", "\n"))

    is_categorical_chart = chart_type in ["Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart", "Treemap"]

    if chart_type in ["Bar Chart", "Horizontal Bar"]:
        bar_colors = [solid_color] * len(df) if solid_color else colors
        if chart_type == "Bar Chart":
            bars = ax.bar(labels, df[count_col], color=bar_colors)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right", color=text_color)
            if text_col and text_col in df.columns:
                for bar, txt in zip(bars, plot_labels):
                    if txt:
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (df[count_col].max()*0.01), 
                                txt, ha='center', va='bottom', fontsize=9, color=text_color)
        else:
            bars = ax.barh(labels, df[count_col], color=bar_colors)
            if text_col and text_col in df.columns:
                for bar, txt in zip(bars, plot_labels):
                    if txt:
                        txt_line = txt.replace("\n", " ")
                        ax.text(bar.get_width() + (df[count_col].max()*0.01), bar.get_y() + bar.get_height()/2, 
                                txt_line, ha='left', va='center', fontsize=9, color=text_color)
    elif chart_type in ["Pie Chart", "Donut Chart"]:
        wedgeprops = dict(width=0.4, edgecolor='w') if chart_type == "Donut Chart" else dict(edgecolor='w')
        ax.pie(df[count_col], labels=plot_labels, colors=colors, wedgeprops=wedgeprops, textprops={'fontsize': 9, 'color': text_color})
    elif chart_type == "Area Chart":
        ax.fill_between(labels, df[count_col], color=colors[0] if colors else "#6366f1", alpha=0.6)
        ax.plot(labels, df[count_col], color=colors[0] if colors else "#6366f1", linewidth=2)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", color=text_color)
    elif chart_type == "Line Chart":
        ax.plot(labels, df[count_col], color=colors[0] if colors else "#6366f1", marker='o', linewidth=2)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", color=text_color)
    if chart_type == "Treemap":
        bars = ax.barh(labels, df[count_col], color=colors)
        treemap_note = "(Fallback to Bar Chart)"
        ax.set_title(f"{title} {treemap_note}" if title else treemap_note, fontsize=14, pad=20, color=text_color)
    elif title:
        # PERMINTAAN USER: gambar statis (PNG copy-paste) TIDAK pakai
        # judul secara default -- title cuma digambar kalau caller kasih
        # nilai non-kosong (caller mengisi ini HANYA saat user mengisi
        # "Override Judul" di panel pengaturan, lihat pages/4_visualization.py
        # & pages/6_pembagian_tugas.py: title=custom_title jika diisi,
        # else title="" -- BUKAN chart_title default spt "Bar Chart - Fakultas").
        ax.set_title(title, fontsize=14, pad=20, color=text_color)

    if show_legend and is_categorical_chart and colors:
        from matplotlib.patches import Patch
        legend_colors = [solid_color] * len(labels) if (solid_color and chart_type in ["Bar Chart", "Horizontal Bar"]) else colors
        legend_handles = [Patch(facecolor=c, label=lbl) for c, lbl in zip(legend_colors, labels)]
        # Posisi legenda meniru pilihan "Right/Bottom/Top/Left" di Plotly
        # (lihat legend_pos di pages/4_visualization.py & 6_pembagian_tugas.py).
        LEGEND_POS_MAP = {
            "Right":  dict(loc="center left", bbox_to_anchor=(1.02, 0.5)),
            "Bottom": dict(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=min(len(labels), 4)),
            "Top":    dict(loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=min(len(labels), 4)),
            "Left":   dict(loc="center right", bbox_to_anchor=(-0.02, 0.5)),
        }
        legend_kwargs = LEGEND_POS_MAP.get(legend_pos, LEGEND_POS_MAP["Right"])
        legend = ax.legend(handles=legend_handles, fontsize=9, **legend_kwargs)
        legend.get_frame().set_facecolor(bg_color)
        for text in legend.get_texts():
            text.set_color(text_color)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(text_color)
    ax.spines['left'].set_color(text_color)
    ax.tick_params(colors=text_color)
    
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Convert DataFrame ke Excel bytes. Dipakai di halaman Visualization & Pembagian Tugas."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()

