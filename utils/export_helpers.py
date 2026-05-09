"""
Export Utility
Helpers for exporting tables as PNG for download.
Always renders in LIGHT theme for print-readiness.
"""

import io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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
    fig_width = max(8.0, total_len * 0.12)
    fig_height = max(2.5, 0.45 * n_rows + 1.5)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    if title:
        fig.suptitle(title, fontsize=15, fontweight="bold", color="#1a1a2e", y=0.98, fontfamily="serif")

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
