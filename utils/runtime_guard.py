from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st


def render_safe(section_name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        st.warning(f'{section_name} is tijdelijk uitgeschakeld door inconsistente data: {exc}')
        return None
