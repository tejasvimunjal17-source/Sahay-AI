-- =============================================================================
-- 008_rls_policies.sql
-- Sahay AI — Phase 4 Row Level Security
-- =============================================================================
-- Same pattern as 002_rls_policies.sql: every policy scoped to
-- auth.uid() = user_id, no "authenticated users can access everything"
-- policy anywhere, no policy at all for the `anon` role. Service-role
-- access (bypasses RLS by Postgres design) stays reserved for
-- backend/supabase_admin_client.py's existing, narrow use (audit_logs) —
-- nothing in Phase 4 adds a new service-role use case.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- conversations
-- -----------------------------------------------------------------------------
alter table public.conversations enable row level security;

drop policy if exists "conversations_select_own" on public.conversations;
create policy "conversations_select_own" on public.conversations
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "conversations_insert_own" on public.conversations;
create policy "conversations_insert_own" on public.conversations
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "conversations_update_own" on public.conversations;
create policy "conversations_update_own" on public.conversations
    for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "conversations_delete_own" on public.conversations;
create policy "conversations_delete_own" on public.conversations
    for delete to authenticated using (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- messages
-- -----------------------------------------------------------------------------
alter table public.messages enable row level security;

drop policy if exists "messages_select_own" on public.messages;
create policy "messages_select_own" on public.messages
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "messages_insert_own" on public.messages;
create policy "messages_insert_own" on public.messages
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "messages_delete_own" on public.messages;
create policy "messages_delete_own" on public.messages
    for delete to authenticated using (auth.uid() = user_id);

-- No UPDATE policy: messages are immutable once sent (matches how the
-- app actually works — nothing edits a message after creation).

-- -----------------------------------------------------------------------------
-- mood_events
-- -----------------------------------------------------------------------------
alter table public.mood_events enable row level security;

drop policy if exists "mood_events_select_own" on public.mood_events;
create policy "mood_events_select_own" on public.mood_events
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "mood_events_insert_own" on public.mood_events;
create policy "mood_events_insert_own" on public.mood_events
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "mood_events_delete_own" on public.mood_events;
create policy "mood_events_delete_own" on public.mood_events
    for delete to authenticated using (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- wellness_activity_logs
-- -----------------------------------------------------------------------------
alter table public.wellness_activity_logs enable row level security;

drop policy if exists "wellness_activity_logs_select_own" on public.wellness_activity_logs;
create policy "wellness_activity_logs_select_own" on public.wellness_activity_logs
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "wellness_activity_logs_insert_own" on public.wellness_activity_logs;
create policy "wellness_activity_logs_insert_own" on public.wellness_activity_logs
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "wellness_activity_logs_delete_own" on public.wellness_activity_logs;
create policy "wellness_activity_logs_delete_own" on public.wellness_activity_logs
    for delete to authenticated using (auth.uid() = user_id);
