"""
Theme Utility
Centralized CSS injection for the Streamlit app.
Uses Streamlit's native theme engine and CSS variables
to guarantee identical colors in dark/light mode globally.
"""

import streamlit as st

def get_plotly_export_layout() -> dict:
    """
    Return a LIGHT Plotly layout for PNG export downloads.
    Always white background with dark text for print-readiness.
    """
    return dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Inter", color="#1a1a2e"),
    )


def inject_theme_css() -> None:
    """Inject CSS using Streamlit's internal CSS variables for native theming."""
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

        /* Custom component cards */
        .feature-card, .stat-card, .clean-stat, .wc-stat {{
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .feature-card {{ border-radius: 14px; padding: 1.8rem 1.5rem; height: 100%; }}
        .feature-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
        }}
        .feature-icon {{ font-size: 2.8rem; margin-bottom: 0.8rem; }}
        .feature-title {{ font-size: 1.1rem; font-weight: 600; color: var(--text-color); margin-bottom: 0.4rem; }}
        .feature-desc {{ font-size: 0.88rem; color: var(--text-color); opacity: 0.8; line-height: 1.5; }}

        .stat-value, .clean-stat-val, .wc-stat-val {{ font-size: 1.6rem; font-weight: 700; color: var(--primary-color); }}
        .stat-label, .clean-stat-lbl, .wc-stat-lbl {{ font-size: 0.82rem; color: var(--text-color); opacity: 0.8; margin-top: 0.3rem; }}

        /* Upload zone */
        .upload-zone {{
            background: var(--secondary-background-color);
            border: 2px dashed rgba(102, 126, 234, 0.4);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            margin-bottom: 1.5rem;
        }}

        /* Analysis header */
        .analysis-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 1.5rem;
            color: white;
            margin-bottom: 1.5rem;
        }}
        .analysis-header h2 {{ color: white; margin: 0; }}
        .analysis-header p {{ color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; }}

        /* Hero container */
        .hero-container {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 3rem 2.5rem;
            margin-bottom: 2rem;
            color: white;
            text-align: center;
        }}
        .hero-container h1 {{ font-size: 2.8rem; font-weight: 700; margin-bottom: 0.5rem; color: white; }}
        .hero-container p {{ font-size: 1.15rem; opacity: 0.9; margin: 0; }}

        /* Pipeline */
        .pipeline-step {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border-radius: 10px;
            padding: 0.6rem 1.2rem;
            margin: 0.3rem;
            font-weight: 500;
            font-size: 0.9rem;
        }}
        .pipeline-arrow {{
            display: inline-block;
            color: #667eea;
            font-size: 1.3rem;
            margin: 0 0.2rem;
            vertical-align: middle;
        }}

        /* Hide default streamlit elements */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)
