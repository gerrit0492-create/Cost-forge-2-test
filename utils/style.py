"""
Professional CSS injection and branded header for Cost Forge 2.
Call inject_css() once per page for consistent styling.
"""
from __future__ import annotations
import streamlit as st


_CSS = """
<style>
/* ── Metric cards ─────────────────────────────────── */
[data-testid="stMetric"] {
    background: #0e1621;
    border: 1px solid #1e2d40;
    border-radius: 10px;
    padding: 14px 18px 10px 18px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem;
    color: #7a9bbf;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="stMetricValue"] {
    font-size: 1.45rem;
    font-weight: 700;
    color: #e8f0fe;
}
[data-testid="stMetricDelta"] { font-size: 0.82rem; }

/* ── Dataframe ────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #1e2d40;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Tabs ─────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
    font-weight: 600;
    font-size: 0.88rem;
    letter-spacing: 0.03em;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #4da6ff;
    border-bottom: 2px solid #4da6ff;
}

/* ── Containers with border ───────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px;
    border-color: #1e2d40 !important;
}

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #0a111a;
    border-right: 1px solid #1e2d40;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label {
    color: #7a9bbf;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Buttons ──────────────────────────────────────── */
[data-testid="stButton"] > button {
    border-radius: 6px;
    font-weight: 600;
}

/* ── Divider ──────────────────────────────────────── */
hr { border-color: #1e2d40; }

/* ── Page link buttons ────────────────────────────── */
[data-testid="stPageLink"] a {
    border: 1px solid #1e2d40;
    border-radius: 6px;
    padding: 4px 12px;
    font-weight: 600;
    font-size: 0.85rem;
}
[data-testid="stPageLink"] a:hover {
    border-color: #4da6ff;
    color: #4da6ff;
}

/* ── Expander ─────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #1e2d40;
    border-radius: 8px;
}

/* ── Alert / status boxes ─────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px;
    border-left-width: 4px;
}

/* ── Input fields ─────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: #0e1621;
    border-color: #1e2d40;
    border-radius: 6px;
}
</style>
"""

_MATURITY_COLOUR = {
    "RoM (±30%)":       ("#f0a500", "#2a1f00"),
    "Budget (±15%)":    ("#ff7043", "#2a0f00"),
    "Definitive (±5%)": ("#42a5f5", "#001929"),
    "Firm":             ("#66bb6a", "#00180a"),
}


def inject_css() -> None:
    """Inject professional CSS. Call once at the top of every page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(
    title: str,
    icon: str = "",
    caption: str = "",
    project: str = "",
    maturity: str = "",
    right_html: str = "",
) -> None:
    """
    Renders a full-width branded header bar with optional project name,
    maturity badge, and right-side custom HTML (e.g. report timestamp).
    Call AFTER inject_css().
    """
    mat_fg, mat_bg = _MATURITY_COLOUR.get(maturity, ("#42a5f5", "#001929"))
    mat_badge = (
        f"<span style='background:{mat_bg}; border:1px solid {mat_fg}; "
        f"border-radius:4px; padding:2px 10px; font-size:0.8em; "
        f"color:{mat_fg}; font-weight:600; vertical-align:middle;'>"
        f"{maturity}</span>"
        if maturity else ""
    )
    proj_html = (
        f"<span style='color:#4da6ff; font-size:0.88em; "
        f"vertical-align:middle; margin-left:12px;'>📦 {project}</span>"
        if project else ""
    )
    right_block = (
        f"<div style='text-align:right; color:#5a7a9a; font-size:0.8em; "
        f"line-height:1.6;'>{right_html}</div>"
        if right_html else ""
    )
    cap_html = (
        f"<div style='color:#5a7a9a; font-size:0.85em; margin-top:4px;'>{caption}</div>"
        if caption else ""
    )

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0a1520 0%,#0e1f32 100%);
            border-bottom:2px solid #1a3050; border-radius:0 0 12px 12px;
            padding:20px 28px 16px 28px; margin:-1rem -1rem 1.5rem -1rem;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
    <div>
      <div style="font-size:1.6em; font-weight:700; color:#e8f0fe; letter-spacing:.3px;">
        {icon}&nbsp; {title}&nbsp; {mat_badge}{proj_html}
      </div>
      {cap_html}
    </div>
    {right_block}
  </div>
</div>
""", unsafe_allow_html=True)
