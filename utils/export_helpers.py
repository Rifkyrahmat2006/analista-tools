"""
Export Utility
Helpers for exporting tables as PNG for download and open-ended analysis to XLSX.
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
