"""Runtime test: imports and executes every page's main() with a mocked Streamlit."""
from __future__ import annotations

import importlib.util
import sys
import traceback
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _make_st() -> mock.MagicMock:
    st = mock.MagicMock()
    st.session_state = {}
    st.sidebar = mock.MagicMock()
    st.sidebar.slider      = mock.MagicMock(return_value=0)
    st.sidebar.radio       = mock.MagicMock(return_value="Eén materiaal")
    st.sidebar.selectbox   = mock.MagicMock(return_value="S235")
    st.sidebar.multiselect = mock.MagicMock(return_value=["S235", "AL6061"])
    st.sidebar.date_input  = mock.MagicMock(return_value=("2025-09-06", "2026-05-18"))
    st.sidebar.header      = mock.MagicMock()
    st.slider        = mock.MagicMock(return_value=0)
    st.number_input  = mock.MagicMock(return_value=10.0)
    st.text_input    = mock.MagicMock(return_value="data/market.csv")
    st.selectbox     = mock.MagicMock(return_value="Standard")
    st.radio         = mock.MagicMock(return_value="Materials")
    st.multiselect   = mock.MagicMock(return_value=[])
    st.file_uploader = mock.MagicMock(return_value=None)
    st.button        = mock.MagicMock(return_value=False)
    st.columns       = mock.MagicMock(side_effect=lambda n, **kw: [mock.MagicMock() for _ in range(n)])
    st.tabs          = mock.MagicMock(side_effect=lambda labels: [mock.MagicMock() for _ in labels])
    st.expander      = mock.MagicMock(
        return_value=mock.MagicMock(
            __enter__=lambda s, *a: s,
            __exit__=lambda s, *a: None,
        )
    )
    st.stop = mock.MagicMock(side_effect=SystemExit)
    return st


SKIP = {"00_Debug.py", "0_Diagnose.py"}

errors: list[tuple[str, str]] = []
ok = 0

for page_file in sorted((ROOT / "pages").glob("*.py")):
    if page_file.name in SKIP:
        print(f"[skip] {page_file.name}")
        continue

    sys.modules["streamlit"] = _make_st()

    try:
        spec = importlib.util.spec_from_file_location(page_file.stem, page_file)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "main"):
            mod.main()
        print(f"[ok]   {page_file.name}")
        ok += 1
    except SystemExit:
        print(f"[ok]   {page_file.name}  (st.stop)")
        ok += 1
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        print(f"[ERR]  {page_file.name}: {msg}")
        traceback.print_exc()
        errors.append((page_file.name, msg))

print(f"\n{ok} passed, {len(errors)} failed")
if errors:
    print("Failures:")
    for name, msg in errors:
        print(f"  - {name}: {msg}")
    sys.exit(1)
