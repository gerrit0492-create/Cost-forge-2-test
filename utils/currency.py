from __future__ import annotations

import streamlit as st

CURRENCIES: dict[str, tuple[str, float]] = {
    "EUR (€)":  ("€",   1.000),
    "USD ($)":  ("$",   1.085),
    "GBP (£)":  ("£",   0.855),
    "NOK (kr)": ("kr", 11.75),
    "SEK (kr)": ("kr", 11.40),
    "SGD ($)":  ("S$",  1.465),
    "AUD ($)":  ("A$",  1.660),
    "INR (₹)":  ("₹",  90.50),
}

_DEFAULT = "EUR (€)"


def _pair() -> tuple[str, float]:
    return CURRENCIES.get(st.session_state.get("currency", _DEFAULT), ("€", 1.0))


def sym() -> str:
    return _pair()[0]


def rate() -> float:
    return _pair()[1]


def fmt(amount_eur: float, decimals: int = 0) -> str:
    s, r = _pair()
    return f"{s} {float(amount_eur) * r:,.{decimals}f}"


def fmt_delta(amount_eur: float, decimals: int = 0) -> str:
    """fmt() with explicit + prefix for positive values — for metric deltas."""
    s, r = _pair()
    converted = float(amount_eur) * r
    prefix = "+" if converted > 0 else ""
    return f"{prefix}{s} {abs(converted):,.{decimals}f}"


def currency_selector() -> None:
    options = list(CURRENCIES.keys())
    current = st.session_state.get("currency", _DEFAULT)
    idx = options.index(current) if current in options else 0
    st.sidebar.selectbox("Currency", options, index=idx, key="currency")
