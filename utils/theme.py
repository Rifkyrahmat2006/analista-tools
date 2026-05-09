"""
Theme Utility
Centralized CSS injection for the Streamlit app.
Includes sidebar branding, per-page copyright footer, and SVG click-to-toggle dark/light mode.
"""

import streamlit as st
import inspect
import os


def get_light_plotly_layout() -> dict:
    """Return a completely LIGHT Plotly layout for print-mode export."""
    return dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", color="#1a1a2e"),
        xaxis=dict(gridcolor="rgba(0,0,0,0.06)", zerolinecolor="rgba(0,0,0,0.06)", automargin=True),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", zerolinecolor="rgba(0,0,0,0.06)", automargin=True),
    )


def _toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode


def inject_theme_css() -> None:
    """Inject global CSS: typography, sidebar brand, menu icons, footer."""

    # Dark / Light mode toggle stored in session state
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True

    dark = st.session_state.dark_mode
    theme_emoji = "🌙" if dark else "☀️"

    # Render the toggle as a real Streamlit button in the sidebar.
    # CSS will collapse its wrapper to height:0 and position the button
    # itself as position:fixed at the top-right corner of the screen.
    with st.sidebar:
        st.button(
            theme_emoji,
            key="btn_toggle_theme",
            on_click=_toggle_dark_mode,
            help="Toggle Dark / Light Mode",
        )

    # Palette
    if dark:
        bg          = "#0f1117"
        sidebar_bg  = "#161b27"
        card_bg     = "#1c2135"
        border_col  = "rgba(255,255,255,0.08)"
        text_main   = "#e8eaf6"
        text_muted  = "rgba(200,200,220,0.55)"
        text_sub    = "rgba(160,160,190,0.7)"
        accent      = "#7c8ff7"
        accent2     = "#a78bfa"
        hero_grad   = "linear-gradient(135deg, #3730a3 0%, #6d28d9 100%)"
        card_hover  = "rgba(124,143,247,0.15)"
        divider     = "rgba(255,255,255,0.08)"
        # SVG: moon icon for dark mode
        theme_icon_svg = "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237c8ff7' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z'/%3E%3C/svg%3E"
    else:
        bg          = "#f5f7ff"
        sidebar_bg  = "#ffffff"
        card_bg     = "#ffffff"
        border_col  = "rgba(99,102,241,0.15)"
        text_main   = "#1e1b4b"
        text_muted  = "rgba(79,70,229,0.5)"
        text_sub    = "rgba(99,102,241,0.65)"
        accent      = "#4f46e5"
        accent2     = "#7c3aed"
        hero_grad   = "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)"
        card_hover  = "rgba(99,102,241,0.08)"
        divider     = "rgba(99,102,241,0.12)"
        # SVG: sun icon for light mode
        theme_icon_svg = "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%234f46e5' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='5'/%3E%3Cline x1='12' y1='1' x2='12' y2='3'/%3E%3Cline x1='12' y1='21' x2='12' y2='23'/%3E%3Cline x1='4.22' y1='4.22' x2='5.64' y2='5.64'/%3E%3Cline x1='18.36' y1='18.36' x2='19.78' y2='19.78'/%3E%3Cline x1='1' y1='12' x2='3' y2='12'/%3E%3Cline x1='21' y1='12' x2='23' y2='12'/%3E%3Cline x1='4.22' y1='19.78' x2='5.64' y2='18.36'/%3E%3Cline x1='18.36' y1='5.64' x2='19.78' y2='4.22'/%3E%3C/svg%3E"

    # Identify active page by looking at caller stack
    caller_file = inspect.stack()[1].filename
    basename = os.path.basename(caller_file)
    if basename == "app.py":
        active_css = f"""
        [data-testid="stSidebarNav"] a[href="/"] span,
        [data-testid="stSidebarNav"] a[href$="app"] span,
        [data-testid="stSidebarNav"] a[href$="dashboard"] span {{
            color: {accent} !important;
            font-weight: 800 !important;
        }}
        [data-testid="stSidebarNav"] a[href="/"]::before,
        [data-testid="stSidebarNav"] a[href$="app"]::before,
        [data-testid="stSidebarNav"] a[href$="dashboard"]::before {{
            opacity: 1 !important;
        }}
        """
    else:
        active_href = basename.split("_", 1)[-1].replace(".py", "")
        active_css = f"""
        [data-testid="stSidebarNav"] a[href$="{active_href}"] span {{
            color: {accent} !important;
            font-weight: 800 !important;
        }}
        [data-testid="stSidebarNav"] a[href$="{active_href}"]::before {{
            opacity: 1 !important;
        }}
        """

    st.markdown(f"""
    <style>
        /* ─── Google Fonts ─── */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

        /* ─── ANTI-FLICKER: Hide all default Streamlit chrome instantly ─── */
        /* Prevent white flash on page load/navigation */
        html {{ background-color: {bg} !important; }}
        body {{ background-color: {bg} !important; }}
        [data-testid="stApp"] {{ background-color: {bg} !important; }}

        /* Kill old Streamlit UI remnants */
        .css-1d391kg, .css-12oz5g7, .css-18e3th9,
        .css-1lcbmhc, .css-hxt7ib, .css-k1vhr4,
        .block-container > div:first-child > div:first-child > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"]:first-child {{
            display: none !important;
        }}

        /* Hide default Streamlit menu, footer, header */
        #MainMenu {{ visibility: hidden !important; display: none !important; }}
        footer {{ visibility: hidden !important; display: none !important; }}
        header {{ visibility: hidden !important; display: none !important; }}

        /* Kill deploy button */
        [data-testid="stToolbar"] {{ display: none !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        .viewerBadge_container__1QSob {{ display: none !important; }}

        /* ─── Global Reset ─── */
        html, body, [class*="css"], .stApp {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: {bg} !important;
            color: {text_main} !important;
        }}

        /* ─── Headings ─── */
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Space Grotesk', sans-serif !important;
            color: {text_main} !important;
            letter-spacing: -0.02em;
        }}

        /* ─── Sidebar base ─── */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            border-right: 1px solid {divider} !important;
        }}
        [data-testid="stSidebar"] * {{
            color: {text_main} !important;
        }}

        /* ─── Theme toggle button: fixed at top-right, looks like an icon ─── */
        /* Collapse ONLY the wrapper containing our toggle button */
        [data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child
          > div:first-child > div[data-testid="stVerticalBlock"] > div:nth-child(1) {{
            height: 0px !important;
            min-height: 0px !important;
            overflow: visible !important;
            padding: 0 !important;
            margin: 0 !important;
        }}
        /* The button itself floats fixed at top-right */
        [data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child
          > div:first-child > div[data-testid="stVerticalBlock"] > div:nth-child(1) button {{
            position: fixed !important;
            top: 12px !important;
            right: 12px !important;
            width: 38px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 !important;
            background: {sidebar_bg} !important;
            border: 1px solid {divider} !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            z-index: 99999 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
            transition: background 0.2s ease, transform 0.2s ease !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        [data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child
          > div:first-child > div[data-testid="stVerticalBlock"] > div:nth-child(1) button:hover {{
            background: {card_hover} !important;
            transform: scale(1.08) !important;
            border-color: {accent} !important;
        }}
        /* Show only the emoji */
        [data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child
          > div:first-child > div[data-testid="stVerticalBlock"] > div:nth-child(1) button p {{
            font-size: 1.15rem !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
        }}

        /* ─── Sidebar Brand Header ─── */
        [data-testid="stSidebarNav"]::before {{
            content: "AMERTOOLS";
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.35rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: {text_main};
            padding: 1.6rem 1.4rem 1.2rem 4.6rem;
            border-bottom: 1px solid {divider};
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'/%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'/%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: 1.4rem center;
            margin-bottom: 0.6rem;
        }}

        /* ─── Sidebar nav links: default ─── */
        [data-testid="stSidebarNav"] a {{
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            color: {text_sub} !important;
            border-radius: 10px !important;
            padding: 0.6rem 1rem 0.6rem 2.8rem !important;
            transition: color 0.2s ease, background 0.2s ease !important;
            background: transparent !important;
            position: relative;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            color: {accent} !important;
            background: transparent !important;
        }}

        /* ─── SVG Icons for each menu item ─── */
        [data-testid="stSidebarNav"] a::before {{
            content: "";
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            width: 18px;
            height: 18px;
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;
            opacity: 0.7;
            transition: all 0.2s ease;
        }}

        [data-testid="stSidebarNav"] a:hover::before,
        [data-testid="stSidebarNav"] a[aria-current="page"]::before {{
            opacity: 1;
        }}

        /* Map URLs to SVGs */
        [data-testid="stSidebarNav"] a[href$="/"]::before,
        [data-testid="stSidebarNav"] a[href$="app"]::before,
        [data-testid="stSidebarNav"] a[href$="dashboard"]::before {{
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='7' height='9' x='3' y='3' rx='1'/%3E%3Crect width='7' height='5' x='14' y='3' rx='1'/%3E%3Crect width='7' height='9' x='14' y='12' rx='1'/%3E%3Crect width='7' height='5' x='3' y='16' rx='1'/%3E%3C/svg%3E");
        }}

        [data-testid="stSidebarNav"] a[href$="upload_data"]::before {{
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/%3E%3Cpolyline points='17 8 12 3 7 8'/%3E%3Cline x1='12' x2='12' y1='3' y2='15'/%3E%3C/svg%3E");
        }}

        [data-testid="stSidebarNav"] a[href$="data_cleaning"]::before {{
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z'/%3E%3C/svg%3E");
        }}

        [data-testid="stSidebarNav"] a[href$="analysis"]::before {{
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='22 7 13.5 15.5 8.5 10.5 2 17'/%3E%3Cpolyline points='16 7 22 7 22 13'/%3E%3C/svg%3E");
        }}

        [data-testid="stSidebarNav"] a[href$="visualization"]::before {{
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{accent.replace('#','%23')}' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='18' x2='18' y1='20' y2='10'/%3E%3Cline x1='12' x2='12' y1='20' y2='4'/%3E%3Cline x1='6' x2='6' y1='20' y2='14'/%3E%3C/svg%3E");
        }}

        /* ─── Active sidebar nav link: no highlight, only color change ─── */
        [data-testid="stSidebarNav"] div,
        [data-testid="stSidebarNav"] a,
        [data-testid="stSidebarNav"] span,
        [data-testid="stSidebarNav"] li {{
            background-color: transparent !important;
            background: transparent !important;
        }}

        /* Default color for all links */
        [data-testid="stSidebarNav"] a span {{
            color: {text_sub} !important;
        }}

        /* Active/Selected font color - Injected Dynamically per Page */
        {active_css}

        /* Hover fallback */
        [data-testid="stSidebarNav"] a:hover span {{
            color: {accent} !important;
        }}

        /* ─── Replace RED with professional PINK in Streamlit elements ─── */
        /* Error messages */
        [data-testid="stAlert"][data-baseweb="notification"][kind="error"],
        div[data-testid="stAlert"] > div[style*="rgb(255"] {{
            background-color: rgba(236, 72, 153, 0.12) !important;
            border-color: rgba(236, 72, 153, 0.4) !important;
            color: {text_main} !important;
        }}
        /* Warning/error icons and text */
        [data-testid="stAlert"][kind="error"] svg,
        [data-testid="stAlert"][kind="error"] path {{
            stroke: #ec4899 !important;
            fill: #ec4899 !important;
            color: #ec4899 !important;
        }}
        /* Progress bars */
        [data-testid="stProgress"] > div > div {{
            background: linear-gradient(90deg, {accent}, #ec4899) !important;
        }}
        /* Required field asterisk */
        .required {{ color: #ec4899 !important; }}
        /* Any remaining red */
        [style*="color: rgb(255, 0, 0)"],
        [style*="color: red"],
        [style*="color:#ff0000"],
        [style*="color: #ff0000"] {{
            color: #ec4899 !important;
        }}

        /* ─── Sidebar Division Footer ─── */
        [data-testid="stSidebar"] > div:first-child {{
            display: flex;
            flex-direction: column;
        }}
        .sidebar-division-footer {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: {text_muted};
            text-align: center;
            padding: 1rem 1.2rem;
            border-top: 1px solid {divider};
            line-height: 1.6;
            margin-top: auto;
        }}
        .sidebar-division-footer span {{
            display: block;
            font-size: 0.68rem;
            font-weight: 400;
            color: {text_muted};
            margin-top: 2px;
        }}

        /* ─── Main page copyright footer ─── */
        .page-copyright-footer {{
            text-align: center;
            font-size: 0.72rem;
            color: {text_muted};
            padding: 2.5rem 1rem 1.5rem 1rem;
            border-top: 1px solid {divider};
            margin-top: 3rem;
            font-family: 'Plus Jakarta Sans', sans-serif;
            letter-spacing: 0.03em;
        }}

        /* ─── Feature cards ─── */
        .feature-card, .stat-card, .clean-stat, .wc-stat {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-radius: 14px;
            padding: 1.2rem;
            text-align: center;
            transition: transform 0.22s ease, box-shadow 0.22s ease;
        }}
        .feature-card {{
            border-radius: 16px;
            padding: 1.8rem 1.5rem;
            height: 100%;
        }}
        .feature-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 32px {card_hover};
            border-color: {accent};
        }}
        .feature-icon {{
            font-size: 2.4rem;
            margin-bottom: 0.8rem;
            color: {accent};
        }}
        .feature-icon svg {{ stroke: {accent}; }}
        .feature-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.05rem;
            font-weight: 700;
            color: {text_main};
            margin-bottom: 0.4rem;
        }}
        .feature-desc {{
            font-size: 0.84rem;
            color: {text_sub};
            line-height: 1.55;
        }}

        /* ─── Stat cards ─── */
        .stat-value, .clean-stat-val, .wc-stat-val {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.7rem;
            font-weight: 700;
            color: {accent};
        }}
        .stat-label, .clean-stat-lbl, .wc-stat-lbl {{
            font-size: 0.8rem;
            color: {text_sub};
            margin-top: 0.3rem;
            font-weight: 500;
        }}

        /* ─── Upload zone ─── */
        .upload-zone {{
            background: {card_bg};
            border: 2px dashed {accent};
            border-radius: 18px;
            padding: 2rem;
            text-align: center;
            margin-bottom: 1.5rem;
            opacity: 0.85;
        }}

        /* ─── Analysis header ─── */
        .analysis-header {{
            background: {hero_grad};
            border-radius: 14px;
            padding: 1.5rem;
            color: white;
            margin-bottom: 1.5rem;
        }}
        .analysis-header h2 {{ color: white; margin: 0; }}
        .analysis-header p {{ color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; }}

        /* ─── Hero container ─── */
        .hero-container {{
            background: {hero_grad};
            border-radius: 20px;
            padding: 3rem 2.5rem;
            margin-bottom: 2rem;
            color: white;
            text-align: center;
            box-shadow: 0 20px 60px rgba(99, 102, 241, 0.3);
        }}
        .hero-container h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.6rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            color: white !important;
        }}
        .hero-container p {{
            font-size: 1.1rem;
            opacity: 0.88;
            margin: 0;
        }}

        /* ─── Pipeline ─── */
        .pipeline-step {{
            display: inline-block;
            background: {hero_grad};
            color: white;
            border-radius: 10px;
            padding: 0.55rem 1.1rem;
            margin: 0.3rem;
            font-weight: 600;
            font-size: 0.87rem;
            letter-spacing: 0.01em;
        }}
        .pipeline-arrow {{
            display: inline-block;
            color: {accent};
            font-size: 1.2rem;
            margin: 0 0.2rem;
            vertical-align: middle;
        }}

        /* ─── Buttons ─── */
        .stButton > button {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            transition: all 0.2s ease !important;
        }}

        /* ════ WIDGET OVERRIDES — dark & light aware ════ */

        /* Text inputs & textareas */
        [data-baseweb="input"] > div,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {{
            background-color: {card_bg} !important;
            color: {text_main} !important;
            border-color: {border_col} !important;
        }}
        [data-baseweb="input"] input::placeholder,
        [data-baseweb="textarea"] textarea::placeholder {{
            color: {text_muted} !important;
        }}

        /* Select / Dropdown trigger */
        [data-baseweb="select"] > div:first-child,
        [data-baseweb="select"] [data-baseweb="select-container"] {{
            background-color: {card_bg} !important;
            color: {text_main} !important;
            border-color: {border_col} !important;
        }}
        [data-baseweb="select"] [data-baseweb="select-container"] span,
        [data-baseweb="select"] [data-baseweb="select-container"] div {{
            color: {text_main} !important;
        }}
        /* Dropdown options list */
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [data-baseweb="menu"] > ul,
        [role="listbox"] {{
            background-color: {card_bg} !important;
            border: 1px solid {border_col} !important;
            border-radius: 10px !important;
        }}
        [data-baseweb="option"],
        [role="option"] {{
            background-color: {card_bg} !important;
            color: {text_main} !important;
        }}
        [data-baseweb="option"]:hover,
        [role="option"]:hover,
        [aria-selected="true"][data-baseweb="option"] {{
            background-color: {card_hover} !important;
        }}

        /* Expanders */
        [data-testid="stExpander"] {{
            background-color: {card_bg} !important;
            border: 1px solid {border_col} !important;
            border-radius: 12px !important;
        }}
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] summary p {{
            color: {text_main} !important;
        }}

        /* Tabs */
        [data-testid="stTabs"] [data-baseweb="tab"] {{
            color: {text_sub} !important;
            background: transparent !important;
        }}
        [data-testid="stTabs"] [aria-selected="true"][data-baseweb="tab"] {{
            color: {accent} !important;
        }}
        [data-baseweb="tab-highlight"] {{
            background-color: {accent} !important;
        }}
        [data-baseweb="tab-border"] {{
            background-color: {border_col} !important;
        }}

        /* Radio & Checkbox labels */
        [data-testid="stRadio"] label span,
        [data-testid="stCheckbox"] label span {{
            color: {text_main} !important;
        }}

        /* Slider */
        [data-testid="stSlider"] [role="slider"] {{
            background-color: {accent} !important;
        }}
        [data-testid="stSlider"] [data-testid="stTickBarMin"],
        [data-testid="stSlider"] [data-testid="stTickBarMax"] {{
            color: {text_muted} !important;
        }}

        /* Alerts */
        [data-testid="stAlert"] {{
            background-color: {card_bg} !important;
            border-left-color: {accent} !important;
        }}
        [data-testid="stAlert"] p,
        [data-testid="stAlert"] span {{
            color: {text_main} !important;
        }}

        /* DataFrames / Tables */
        [data-testid="stDataFrame"] {{
            border-radius: 10px !important;
        }}
        /* AG-Grid */
        .ag-root-wrapper, .ag-header, .ag-header-row,
        .ag-cell, .ag-row {{
            background-color: {card_bg} !important;
            color: {text_main} !important;
            border-color: {border_col} !important;
        }}
        .ag-header {{
            background-color: {sidebar_bg} !important;
        }}

        /* Caption text */
        [data-testid="stCaptionContainer"] p {{
            color: {text_muted} !important;
        }}

        /* Color picker */
        [data-testid="stColorPicker"] input {{
            background-color: {card_bg} !important;
            color: {text_main} !important;
        }}

        /* Main content area */
        [data-testid="stMainBlockContainer"],
        .block-container {{
            background-color: {bg} !important;
        }}

        /* Sidebar inputs */
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] [data-baseweb="input"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {{
            background-color: {sidebar_bg} !important;
            border-color: {divider} !important;
        }}

    </style>
    """, unsafe_allow_html=True)




def render_sidebar_footer():
    """Inject the Division footer at the very bottom of the sidebar."""
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-division-footer">
                Direktorat Jenderal Analisis Data
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_page_footer():
    """Inject copyright footer at the bottom of each main page."""
    st.markdown(
        """
        <div class="page-copyright-footer">
            &copy; 2026 Kementerian Riset dan Data &nbsp;·&nbsp; BEM UNSOED
        </div>
        """,
        unsafe_allow_html=True,
    )
