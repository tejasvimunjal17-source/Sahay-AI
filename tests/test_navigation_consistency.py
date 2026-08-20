"""
tests/test_navigation_consistency.py
---------------------------------------
Confirms sidebar nav keys, streamlit_app.py's page router, and page
titles all agree, and that every referenced page module exists on disk.
No pytest available — run: python3 tests/test_navigation_consistency.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def run() -> int:
    sidebar_src = (ROOT / "components" / "sidebar.py").read_text(encoding="utf-8")
    app_src = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")

    nav_keys = set(re.findall(r'\("[^"]+",\s*"(\w+)"\)', sidebar_src))
    router_keys = set(re.findall(r'"(\w+)":\s*\w+\.render', app_src))
    title_block = app_src.split("PAGE_TITLES")[1].split("PAGE_RENDERERS")[0]
    title_keys = set(re.findall(r'"(\w+)":\s*"[^"]+"', title_block))

    check("Sidebar nav keys == page router keys", nav_keys == router_keys,
          f"nav={sorted(nav_keys)} router={sorted(router_keys)}")
    check("Sidebar nav keys == page title keys", nav_keys == title_keys,
          f"nav={sorted(nav_keys)} titles={sorted(title_keys)}")
    check("14 pages total", len(nav_keys) == 14, f"found {len(nav_keys)}")

    imported = re.search(r"from pages import \(([^)]+)\)", app_src, re.S)
    modules = [m.strip().rstrip(",") for m in imported.group(1).split(",") if m.strip()] if imported else []
    missing = [m for m in modules if not (ROOT / "pages" / f"{m}.py").is_file()]
    check("Every imported page module exists on disk", not missing, str(missing))

    print()
    print(f"TOTAL: {4 - len(failures)}/4 passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
