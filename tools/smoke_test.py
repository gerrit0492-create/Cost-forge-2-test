from __future__ import annotations

import pathlib
import py_compile
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
errors = []
for p in sorted((ROOT/'pages').glob('*.py')):
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok]  {p.name}")
    except Exception as e:
        print(f"[ERR] {p.name}: {type(e).__name__}: {e}")
        errors.append((p.name, str(e)))
if errors:
    print("Failures:")
    for n, e in errors:
        print(" -", n, e)
    sys.exit(1)
print("All pages compiled.")
