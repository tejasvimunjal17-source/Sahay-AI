-- =============================================================================
-- 003_role_protection.sql
-- Sahay AI — Phase 2 role self-escalation protection
-- =============================================================================
-- Per PHASE2_ARCHITECTURE_AUDIT.md §4.4 / §7 finding #3 (classified High,
-- blocking). RLS's "profiles_update_own" policy (002) permits a user to
-- UPDATE any column on their own row, including `role` — this migration
-- closes that gap at the database layer, not just in application code.
--
-- The database, not the Streamlit app, is the enforcement boundary: even
-- a bug in backend/auth.py or a direct API call cannot promote a user to
-- admin, because Postgres itself rejects the write.
--
-- MUST be applied together with 002_rls_policies.sql before any real
-- user is allowed to write to profiles — a role column without this
-- trigger is a privilege-escalation hole, not a partial mitigation.
-- =============================================================================

create or replace function public.prevent_role_self_escalation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    -- auth.role() reports the Postgres role Supabase is executing as for
    -- this request. The service-role key executes as 'service_role' and
    -- bypasses RLS/this check entirely by Postgres design — this trigger
    -- only needs to constrain the 'authenticated' (anon-key, RLS-bound)
    -- path, which is the only path a normal user's session can ever use.
    if new.role is distinct from old.role
       and auth.role() <> 'service_role' then
        raise exception
            'Changing role is not permitted through the user client. '
            'Contact an administrator if a role change is required.'
            using errcode = '42501'; -- insufficient_privilege
    end if;
    return new;
end;
$$;

comment on function public.prevent_role_self_escalation() is
    'Blocks any UPDATE to profiles.role unless executed via the '
    'service-role connection. Applies regardless of what RLS policy '
    'would otherwise permit — defense at the trigger layer, not just '
    'the policy layer.';

drop trigger if exists trg_prevent_role_self_escalation on public.profiles;
create trigger trg_prevent_role_self_escalation
    before update on public.profiles
    for each row
    execute function public.prevent_role_self_escalation();
