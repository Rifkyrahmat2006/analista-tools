import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pivot_analysis import single_choice_analysis, scale_analysis
from utils.multi_select_analysis import multi_choice_analysis
from utils.export_helpers import table_to_png
from utils.theme import inject_theme_css, get_light_plotly_layout

st.set_page_config(page_title="Visualization", page_icon="📊", layout="wide")

inject_theme_css()

PLOTLY_COLORS = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe",
                 "#43e97b", "#fa709a", "#fee140", "#a18cd1"]
COLOR_SCALES = ["Purples", "Blues", "Greens", "Reds", "Viridis", "Plasma", "Inferno", "Turbo"]

st.markdown("# 📊 Visualization")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("⚠️ Belum ada dataset. Silakan upload data terlebih dahulu.")
    st.stop()

df = st.session_state.df

# --------------- Settings ---------------
with st.sidebar:
    st.markdown("### 🎨 Pengaturan Visualisasi")
    chart_theme = st.selectbox("Color Scale", COLOR_SCALES, index=0)
    chart_height = st.slider("Tinggi Chart", 300, 800, 500, step=50)
    show_values = st.checkbox("Tampilkan Nilai", value=True)

    st.markdown("### 🖨️ Export Settings")
    force_light_mode = st.checkbox(
        "Paksa Chart Terang", 
        help="Aktifkan agar chart Plotly berlatar putih. Sangat berguna sebelum Anda mengunduh chart (logo kamera) agar hasil download siap cetak."
    )

    st.markdown("---")
    if "df" in st.session_state and st.session_state.df is not None:
        st.success(f"✅ **{st.session_state.get('dataset_name', 'Unknown')}**")
        st.caption(f"{st.session_state.df.shape[0]} baris × {st.session_state.df.shape[1]} kolom")

EXPORT_LAYOUT = get_light_plotly_layout()

# --------------- Column Selection ---------------
st.markdown("### 📌 Pilih Kolom dan Tipe Chart")

col_select, type_select, chart_select = st.columns(3)

with col_select:
    selected_col = st.selectbox("Kolom", df.columns.tolist())

with type_select:
    data_type = st.selectbox(
        "Tipe Data",
        ["single_choice", "multiple_choice", "scale"],
        format_func=lambda x: x.replace("_", " ").title(),
    )

with chart_select:
    chart_options = {
        "single_choice": ["Bar Chart", "Pie Chart", "Donut Chart", "Treemap"],
        "multiple_choice": ["Horizontal Bar", "Bar Chart", "Treemap"],
        "scale": ["Bar Chart", "Area Chart", "Line Chart"],
    }
    chart_type = st.selectbox("Tipe Chart", chart_options.get(data_type, ["Bar Chart"]))

st.markdown("---")

# --------------- Generate Visualization ---------------
if selected_col:
    # Get analysis data based on type
    if data_type == "single_choice":
        result = single_choice_analysis(df, selected_col)
        val_col, count_col = "Value", "Count"
    elif data_type == "multiple_choice":
        result = multi_choice_analysis(df, selected_col)
        val_col, count_col = "Value", "Count"
    elif data_type == "scale":
        result = scale_analysis(df, selected_col)
        val_col, count_col = "Scale", "Count"
    else:
        result = None

    if result is not None and not result.empty:
        st.markdown(f"### 📊 {chart_type} — {selected_col}")

        text_arg = count_col if show_values else None

        if chart_type == "Bar Chart":
            fig = px.bar(
                result, x=val_col, y=count_col,
                color=val_col, color_discrete_sequence=PLOTLY_COLORS,
                text=text_arg,
            )
            if show_values:
                fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False, height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
            fig.update_xaxes(type="category")

        elif chart_type == "Horizontal Bar":
            fig = px.bar(
                result, x=count_col, y=val_col,
                orientation="h",
                color=count_col, color_continuous_scale=chart_theme,
                text=text_arg,
            )
            if show_values:
                fig.update_traces(textposition="outside")
            fig.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"), height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

        elif chart_type == "Pie Chart":
            fig = px.pie(
                result, names=val_col, values=count_col,
                color_discrete_sequence=PLOTLY_COLORS,
            )
            fig.update_layout(height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
            fig.update_traces(textinfo="label+percent+value" if show_values else "label+percent")

        elif chart_type == "Donut Chart":
            fig = px.pie(
                result, names=val_col, values=count_col,
                color_discrete_sequence=PLOTLY_COLORS,
                hole=0.45,
            )
            fig.update_layout(height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
            fig.update_traces(textinfo="label+percent+value" if show_values else "label+percent")

        elif chart_type == "Treemap":
            fig = px.treemap(
                result, path=[val_col], values=count_col,
                color=count_col, color_continuous_scale=chart_theme,
            )
            fig.update_layout(coloraxis_showscale=False, height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)

        elif chart_type == "Area Chart":
            fig = px.area(
                result, x=val_col, y=count_col,
                color_discrete_sequence=PLOTLY_COLORS,
            )
            fig.update_layout(height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
            fig.update_xaxes(type="category")

        elif chart_type == "Line Chart":
            fig = px.line(
                result, x=val_col, y=count_col,
                markers=True,
                color_discrete_sequence=PLOTLY_COLORS,
            )
            fig.update_layout(height=chart_height, margin=dict(t=50, b=50, l=50, r=50))
            if force_light_mode: fig.update_layout(**EXPORT_LAYOUT)
            fig.update_xaxes(type="category")

        else:
            fig = None

        if fig:
            # Custom filename for Plotly's built-in PNG download button
            chart_config = {
                "toImageButtonOptions": {
                    "filename": f"{selected_col}_{chart_type.replace(' ', '_').lower()}",
                    "width": 1200,
                    "height": chart_height,
                    "scale": 2,
                },
            }
            st.plotly_chart(fig, use_container_width=True, config=chart_config, theme=None if force_light_mode else "streamlit")

            # Export options
            st.markdown("---")
            st.markdown("### 📥 Ekspor")

            col_exp1, col_exp2, col_exp3 = st.columns(3)

            with col_exp1:
                csv_data = result.to_csv(index=False)
                st.download_button(
                    "📄 Download Data (CSV)",
                    data=csv_data,
                    file_name=f"{selected_col}_analysis.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with col_exp2:
                html_data = fig.to_html(include_plotlyjs="cdn")
                st.download_button(
                    "📊 Download Chart (HTML)",
                    data=html_data,
                    file_name=f"{selected_col}_chart.html",
                    mime="text/html",
                    use_container_width=True,
                )

            with col_exp3:
                try:
                    table_png = table_to_png(result, title=f"{selected_col} — {data_type.replace('_',' ').title()}")
                    st.download_button(
                        "📋 Download Tabel (PNG)",
                        data=table_png,
                        file_name=f"{selected_col}_table.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Table PNG export error: {e}")

        # Data table
        with st.expander("📋 Lihat Data Tabel"):
            st.dataframe(result, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Tidak ada data untuk ditampilkan.")
