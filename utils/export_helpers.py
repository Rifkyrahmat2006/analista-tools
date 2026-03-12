"""
Export Utility
Helpers for exporting tables as PNG for download.
"""

import io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def table_to_png(df: pd.DataFrame, title: str = "", max_rows: int = 30) -> bytes:
    """
    Render a pandas DataFrame as a styled table PNG using matplotlib.
    """
    display_df = df.head(max_rows)
    n_rows, n_cols = display_df.shape

    # Calculate figure size
    col_width = max(2.0, min(3.5, 18.0 / n_cols))
    fig_width = max(6, col_width * n_cols + 1)
    fig_height = max(2.5, 0.45 * n_rows + 1.5)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold", color="#e0e0e0", y=0.98)

    fig.patch.set_facecolor("#0e1117")

    # Create table
    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        loc="center",
        cellLoc="center",
    )

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.4)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#3a3a5c")
        if row == 0:
            # Header row
            cell.set_facecolor("#667eea")
            cell.set_text_props(color="white", fontweight="bold", fontsize=11)
        else:
            # Data rows - alternating colors
            if row % 2 == 0:
                cell.set_facecolor("#1e1e2e")
            else:
                cell.set_facecolor("#252540")
            cell.set_text_props(color="#e0e0e0")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
