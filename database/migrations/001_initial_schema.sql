-- =============================================================================
-- 001_initial_schema.sql
-- Sahay AI — Phase 2 initial schema
-- =============================================================================
-- Creates the minimum two tables justified for Phase 2 (auth + security
-- foundation), per PHASE2_ARCHITECTURE_AUDIT.md §2. Every other table
-- discussed in the audit (conversations, messages, mood_events,
-- wellness_activities, safety_events, feedback, admin_users) is
-- deliberately deferred to the phase that actually needs it.
--
-- Idempotent: safe to re-run (uses IF NOT EXISTS throughout).
-- Apply via the Supabase SQL editor or `supabase db push`, in order.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- profiles
-- One row per Supabase Auth user. id is a direct FK to auth.users, not a
-- separate identity — profiles never exists without a matching auth user.
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
    id                   uuid primary key references auth.users (id) on delete cascade,
    display_name         text,
    preferred_language   text not null default 'en',
    onboarding_complete  boolean not null default false,
    role                 text not null default 'student'
                         check (role in ('student', 'admin')),
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);

comment on table public.profiles is
    'One row per authenticated Sahay AI user. role is intentionally NOT '
    'user-writable via normal RLS — see 003_role_protection.sql.';

-- Keep updated_at current on every row change.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
    before update on public.profiles
    for each row
    execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- audit_logs
-- System-written only. No user or admin ever writes to this table directly
-- from the anon-key client — see 002_rls_policies.sql (zero permissive
-- policies granted to anon/authenticated roles, by design).
-- -----------------------------------------------------------------------------
create table if not exists public.audit_logs (
    id          bigint generated always as identity primary key,
    actor_type  text not null check (actor_type in ('user', 'admin', 'system')),
    actor_id    uuid references auth.users (id) on delete set null,
    action      text not null,
    target      text,
    created_at  timestamptz not null default now()
);

comment on table public.audit_logs is
    'Security/auth event trail. Written only via the service-role client '
    '(backend/audit_log.py). Never stores message content, passwords, '
    'tokens, or other sensitive payloads — action/target are short '
    'identifiers only.';

create index if not exists idx_audit_logs_actor
    on public.audit_logs (actor_id);

create index if not exists idx_audit_logs_created_at
    on public.audit_logs (created_at desc);
