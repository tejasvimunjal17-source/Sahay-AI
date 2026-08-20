"""
tests/test_import_guard.py
-----------------------------
Enforces PHASE2_ARCHITECTURE_AUDIT.md §7 finding #2: the service-role
Supabase client must never be importable from pages/, components/, or
chatbot/ — only backend/audit_log.py (and supabase_admin_client.py
itself) may reference it.

No pytest available in this environment — run directly:
    python3 tests/test_import_guard.py
Exits non-zero on failure, so it's also CI-friendly once pytest (or any
runner) is available.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_DIRS = ["pages", "components", "chatbot"]
ALLOWED_FILES = {"backend/supabase_admin_client.py", "backend/audit_log.py"}
PATTERN = re.compile(r"supabase_admin_client")


def run() -> int:
    violations = []
    for d in FORBIDDEN_DIRS:
        for path in (ROOT / d).rglob("*.py"):
            rel = str(path.relative_to(ROOT))
            if rel in ALLOWED_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            if PATTERN.search(text):
                violations.append(rel)

    if violations:
        print("FAIL: service-role client referenced outside backend/audit_log.py:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("PASS: supabase_admin_client is not imported from pages/, components/, or chatbot/")
    return 0


if __name__ == "__main__":
    sys.exit(run())
