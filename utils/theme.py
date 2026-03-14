"""
Theme Utility
Centralized dark/light mode management for the Streamlit app.
Provides auto-detection of system theme, toggle, CSS injection,
and Plotly layout helpers.
"""

import streamlit as st
import streamlit.components.v1 as components


# --------------- Color Tokens ---------------

THEMES = {
    "dark": {
        "bg": "#0e1117",
        "bg_secondary": "#1e1e2e",
        "bg_tertiary": "#2a2a3e",
        "text": "#e0e0e0",
        "text_muted": "#9a9ab0",
        "border": "rgba(255,255,255,0.06)",
        "accent": "#667eea",
        "sidebar_bg_start": "#1a1a2e",
        "sidebar_bg_end": "#16213e",
    },
    "light": {
        "bg": "#ffffff",
        "bg_secondary": "#f5f7fa",
        "bg_tertiary": "#e8ecf1",
        "text": "#1a1a2e",
        "text_muted": "#5a5a7a",
        "border": "rgba(0,0,0,0.08)",
        "accent": "#667eea",
        "sidebar_bg_start": "#f0f2f6",
        "sidebar_bg_end": "#e8ecf1",
    },
}


def _inject_system_theme_detection() -> None:
    """Inject invisible JS to detect browser prefers-color-scheme and redirect."""
    components.html("""
    <script>
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = isDark ? 'dark' : 'light';
        const url = new URL(window.parent.location.href);
        if (!url.searchParams.has('system_theme')) {
            url.searchParams.set('system_theme', theme);
            window.parent.location.href = url.toString();
        }
    </script>
    """, height=0)


def init_theme() -> None:
    """
    Initialize theme in session state.
    On first load, auto-detects browser/OS dark or light preference
    via JavaScript. The user can still override with the toggle.
    """
    if "theme" not in st.session_state:
        # Check if the JS detection already redirected with a query param
        params = st.query_params
        if "system_theme" in params:
            detected = params["system_theme"]
            st.session_state.theme = detected if detected in ("dark", "light") else "dark"
            del st.query_params["system_theme"]
        else:
            # First visit — inject JS to detect system theme, then stop
            # so the page doesn't flash with the wrong theme
            st.session_state.theme = "dark"  # temporary fallback
            _inject_system_theme_detection()
            st.stop()
    else:
        # Clean up stale query param if user navigated back
        params = st.query_params
        if "system_theme" in params:
            del st.query_params["system_theme"]


def get_theme() -> str:
    """Get current theme name."""
    return st.session_state.get("theme", "dark")


def get_colors() -> dict:
    """Get current theme's color tokens."""
    return THEMES[get_theme()]


def render_theme_toggle() -> None:
    """Render a dark/light toggle button in the sidebar."""
    with st.sidebar:
        current = get_theme()
        label = "☀️ Light Mode" if current == "dark" else "🌙 Dark Mode"
        if st.button(label, key="theme_toggle", use_container_width=True):
            st.session_state.theme = "light" if current == "dark" else "dark"
            st.rerun()


def get_plotly_layout(**overrides) -> dict:
    """Return a Plotly layout dict matching the current theme."""
    c = get_colors()
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=c["text"]),
        margin=dict(t=40, b=40, l=40, r=40),
    )
    layout.update(overrides)
    return layout


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
    """Inject theme-aware CSS into the page."""
    c = get_colors()
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {c['sidebar_bg_start']} 0%, {c['sidebar_bg_end']} 100%);
        }}

        /* Custom component cards */
        .feature-card, .stat-card, .clean-stat, .wc-stat {{
            background: linear-gradient(145deg, {c['bg_secondary']}, {c['bg_tertiary']});
            border: 1px solid {c['border']};
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
        .feature-title {{ font-size: 1.1rem; font-weight: 600; color: {c['text']}; margin-bottom: 0.4rem; }}
        .feature-desc {{ font-size: 0.88rem; color: {c['text_muted']}; line-height: 1.5; }}

        .stat-value, .clean-stat-val, .wc-stat-val {{ font-size: 1.6rem; font-weight: 700; color: {c['accent']}; }}
        .stat-label, .clean-stat-lbl, .wc-stat-lbl {{ font-size: 0.82rem; color: {c['text_muted']}; margin-top: 0.3rem; }}

        /* Upload zone */
        .upload-zone {{
            background: linear-gradient(145deg, {c['bg_secondary']}, {c['bg_tertiary']});
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
