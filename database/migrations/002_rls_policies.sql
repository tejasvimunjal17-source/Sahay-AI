-- =============================================================================
-- 002_rls_policies.sql
-- Sahay AI — Phase 2 Row Level Security
-- =============================================================================
-- Per PHASE2_ARCHITECTURE_AUDIT.md §4.4. Every user-owned table gets RLS
-- enabled with policies scoped to auth.uid() = id — no "authenticated
-- users can access everything" policy exists anywhere in this file.
--
-- audit_logs gets RLS ENABLED with ZERO permissive policies for anon/
-- authenticated roles — this is intentional (default-deny), not an
-- oversight. Only the service-role key (which bypasses RLS by Postgres
-- design) can read/write it.
--
-- Idempotent: drops-then-creates each policy by name, safe to re-run.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- profiles
-- -----------------------------------------------------------------------------
alter table public.profiles enable row level security;

-- SELECT: a user may only read their own profile row.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
    on public.profiles
    for select
    to authenticated
    using (auth.uid() = id);

-- INSERT: a user may only create their own row, and only once (the
-- primary key already prevents a second row for the same id).
drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
    on public.profiles
    for insert
    to authenticated
    with check (auth.uid() = id);

-- UPDATE: a user may only update their own row. This policy alone would
-- still permit `UPDATE profiles SET role = 'admin' WHERE id = auth.uid()`
-- — that gap is closed by the trigger in 003_role_protection.sql, applied
-- in the SAME migration set, not a "later" follow-up.
drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
    on public.profiles
    for update
    to authenticated
    using (auth.uid() = id)
    with check (auth.uid() = id);

-- DELETE: intentionally NOT granted. Per the audit's recommendation,
-- account deletion is routed through a controlled server-side path
-- (service-role client) rather than a direct client DELETE, so it can be
-- audited and so ON DELETE CASCADE from auth.users stays the single
-- source of truth for profile removal. No "profiles_delete_own" policy
-- exists — an authenticated user cannot DELETE their own profiles row
-- directly; deleting their auth.users row (via the account-deletion
-- flow) cascades instead.

-- No policy grants anything to the `anon` (unauthenticated) role at all.

-- -----------------------------------------------------------------------------
-- audit_logs — default-deny for anon/authenticated
-- -----------------------------------------------------------------------------
alter table public.audit_logs enable row level security;

-- Deliberately no policies created for `anon` or `authenticated`. With
-- RLS enabled and no permissive policy matching a given role, Postgres
-- denies all access for that role by default. The service-role key
-- bypasses RLS entirely (Postgres/Supabase behavior, not a policy we
-- write), which is the only way this table is ever read or written.
