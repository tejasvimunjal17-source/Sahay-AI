"""
tests/test_static_security.py
--------------------------------
Repo-wide static scans. No pytest available in this environment — run:
    python3 tests/test_static_security.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_FILES = [p for p in ROOT.rglob("*.py") if "__pycache__" not in str(p)]
# Application source files only — excludes tests/ itself, since these test
# files legitimately reference "sqlite"/"learnmate"/"uploads" as strings
# within their own detection patterns and documentation, not as actual
# violations of what they're checking for.
APP_FILES = [p for p in PY_FILES if "tests" not in p.relative_to(ROOT).parts]
SQL_FILES = list((ROOT / "database" / "migrations").glob("*.sql"))

failures: list[str] = []
total_checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def run() -> int:
    # 1. No hardcoded secret-looking values
    secret_re = re.compile(r"(api[_-]?key|secret|password)\s*=\s*['\"][A-Za-z0-9_\-]{10,}['\"]", re.I)
    hits = []
    for p in PY_FILES:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if secret_re.search(line) and "_get_env" not in line:
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    check("No hardcoded API keys/secrets/passwords", not hits, str(hits))

    # 2. No SQLite
    sqlite_re = re.compile(r"sqlite3|\.db['\"]|\.sqlite")
    hits = [str(p.relative_to(ROOT)) for p in APP_FILES if sqlite_re.search(p.read_text(encoding="utf-8"))]
    check("No SQLite / local DB usage", not hits, str(hits))

    # 3. No accidental LearnMate imports. Regex requires actual Python import
    #    syntax (a dotted module identifier), not prose like "adapted from
    #    LearnMate AI's..." in a docstring/comment, which is expected and fine.
    learnmate_import_re = re.compile(
        r"^\s*(from\s+[\w.]*learnmate[\w.]*\s+import|import\s+[\w.]*learnmate[\w.]*)",
        re.I | re.M,
    )
    hits = [str(p.relative_to(ROOT)) for p in APP_FILES if learnmate_import_re.search(p.read_text(encoding="utf-8"))]
    check("No LearnMate imports", not hits, str(hits))

    # 4. Service-role client isolation (also covered by test_import_guard.py — re-checked here for a single-command full sweep)
    forbidden_dirs = ["pages", "components", "chatbot"]
    allowed = {"backend/supabase_admin_client.py", "backend/audit_log.py"}
    hits = []
    for d in forbidden_dirs:
        for p in (ROOT / d).rglob("*.py"):
            rel = str(p.relative_to(ROOT))
            if rel in allowed:
                continue
            if "supabase_admin_client" in p.read_text(encoding="utf-8"):
                hits.append(rel)
    check("Service-role client not reachable from pages/components/chatbot", not hits, str(hits))

    # 5. HTTP/network calls (requests.post/get, httpx) must be confined to the
    #    approved OpenRouter client module. This check UPDATED in Phase 3 (was:
    #    "no HTTP calls anywhere," which was correct for Phase 1/2 but would
    #    incorrectly fail now that backend/openrouter_client.py legitimately
    #    makes them — see PHASE3_PRE_IMPLEMENTATION_AUDIT.md §3). The intent —
    #    "no unauthorized network calls sneak into the app" — is preserved by
    #    scoping the check to everywhere EXCEPT the one approved module.
    net_re = re.compile(r"requests\.(get|post)\(|httpx\.")
    ALLOWED_NET_FILES = {"backend/openrouter_client.py"}
    hits = [
        str(p.relative_to(ROOT)) for p in APP_FILES
        if str(p.relative_to(ROOT)) not in ALLOWED_NET_FILES and net_re.search(p.read_text(encoding="utf-8"))
    ]
    check("No HTTP/network calls outside backend/openrouter_client.py", not hits, str(hits))

    # 5b. Confirm the approved module actually contains the calls we expect
    #     (guards against the allowlist above silently becoming a no-op check
    #     if openrouter_client.py is ever refactored to not need requests).
    openrouter_src = (ROOT / "backend" / "openrouter_client.py").read_text(encoding="utf-8")
    check(
        "backend/openrouter_client.py itself does make the expected HTTP call",
        bool(net_re.search(openrouter_src)),
    )

    # 6. Migrations: no overly broad RLS ("using (true)" / "for all") on profiles or audit_logs
    broad_re = re.compile(r"using\s*\(\s*true\s*\)|for\s+all\b", re.I)
    hits = []
    for p in SQL_FILES:
        if broad_re.search(p.read_text(encoding="utf-8")):
            hits.append(p.name)
    check("No overly broad RLS policies (no 'using (true)' / 'for all')", not hits, str(hits))

    # 7. Migrations: no CREATE POLICY without an owner-scoped auth.uid() check on profiles
    schema_text = "\n".join(p.read_text(encoding="utf-8") for p in SQL_FILES)
    check(
        "profiles RLS policies reference auth.uid()",
        "auth.uid() = id" in schema_text,
    )

    # 8. audit_logs has RLS enabled but no permissive policy for anon/authenticated
    rls_text = (ROOT / "database" / "migrations" / "002_rls_policies.sql").read_text(encoding="utf-8")
    audit_section = rls_text.split("audit_logs")[-1] if "audit_logs" in rls_text else ""
    check(
        "audit_logs RLS enabled",
        "alter table public.audit_logs enable row level security" in rls_text.lower(),
    )
    check(
        "audit_logs has no CREATE POLICY granting anon/authenticated access",
        "create policy" not in audit_section.lower(),
    )

    # 9. Role-escalation protection trigger exists and blocks non-service_role role changes
    role_protection = (ROOT / "database" / "migrations" / "003_role_protection.sql").read_text(encoding="utf-8")
    check(
        "Role self-escalation trigger exists and checks auth.role() <> 'service_role'",
        "prevent_role_self_escalation" in role_protection and "service_role" in role_protection,
    )

    # 10. No RPC functions beyond the role-protection trigger (per audit: no RPC "just because available")
    rpc_like = [f.name for f in SQL_FILES if "create function" in f.read_text(encoding="utf-8").lower()
                and f.name != "003_role_protection.sql"]
    check("No unnecessary RPC/functions beyond the role-protection trigger", not rpc_like, str(rpc_like))

    # 11. Only the two approved tables are created (profiles, audit_logs) — no premature tables
    create_table_re = re.compile(r"create table if not exists public\.(\w+)")
    tables = set()
    for p in SQL_FILES:
        tables.update(create_table_re.findall(p.read_text(encoding="utf-8")))
    expected_tables = {
        "profiles", "audit_logs",  # Phase 2
        "conversations", "messages", "mood_events", "wellness_activity_logs",  # Phase 4
    }
    check(
        "Only the approved Phase 2+4 tables exist (no premature/extra tables)",
        tables == expected_tables,
        str(tables),
    )

    # 11d. PHASE 5: migration 010 extends mood_events with the three approved
    #      wellness scales (no new table — per the audit decision to reuse
    #      the existing table), all nullable and range-checked 1-5.
    migration_010 = ROOT / "database" / "migrations" / "010_wellness_scales.sql"
    check("010_wellness_scales.sql exists", migration_010.is_file())
    if migration_010.is_file():
        m10_text = migration_010.read_text(encoding="utf-8").lower()
        for col in ("stress_level", "energy_level", "sleep_quality"):
            check(
                f"010_wellness_scales.sql adds {col} to mood_events",
                f"add column if not exists {col}" in m10_text,
            )
            check(
                f"{col} has a 1-5 range check constraint",
                bool(re.search(rf"{col}\s+smallint\s+check\s*\(\s*{col}\s+between\s+1\s+and\s+5\s*\)", m10_text)),
            )
        check(
            "010_wellness_scales.sql does not create a new table (reuses mood_events)",
            "create table" not in m10_text,
        )
    # No new RLS policy is expected for these columns — RLS is row-level,
    # and mood_events' existing owner-scoped policies (from 008) already
    # cover the whole row, new columns included. Nothing to check here
    # beyond confirming no accidental NEW policy/table was introduced above.

    # 11b. Every Phase 4 table has RLS enabled AND at least one owner-scoped
    #      (auth.uid() = user_id) policy — catches a table that's created but
    #      never actually locked down.
    phase4_tables = {"conversations", "messages", "mood_events", "wellness_activity_logs"}
    rls_full_text = "\n".join(p.read_text(encoding="utf-8") for p in SQL_FILES)
    for t in phase4_tables:
        check(
            f"{t}: RLS enabled",
            f"alter table public.{t} enable row level security" in rls_full_text.lower(),
        )
        check(
            f"{t}: has an owner-scoped (auth.uid() = user_id) policy",
            bool(re.search(rf"create policy[^;]*{t}[^;]*auth\.uid\(\)\s*=\s*user_id", rls_full_text, re.I | re.S))
            or bool(re.search(rf"on public\.{t}[^;]*auth\.uid\(\)\s*=\s*user_id", rls_full_text, re.I | re.S)),
        )

    # 11c. backend/conversations.py: every read/write function filters by
    #      user_id — an application-layer belt-and-suspenders check on top
    #      of RLS (see tests/test_conversations_mock.py for behavioral
    #      confirmation of the same property).
    conv_src = (ROOT / "backend" / "conversations.py").read_text(encoding="utf-8")
    check(
        'backend/conversations.py consistently filters by user_id (.eq("user_id"',
        conv_src.count('.eq("user_id"') >= 8,  # one per read/write function, generously bounded
        f'found {conv_src.count(chr(34) + "user_id" + chr(34))} occurrences',
    )

    # 12. LearnMate upload directory referenced nowhere in source (defense against accidental coupling)
    hits = [str(p.relative_to(ROOT)) for p in APP_FILES if "user-data/uploads" in p.read_text(encoding="utf-8")]
    check("No code path reads from the LearnMate uploads directory", not hits, str(hits))

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
