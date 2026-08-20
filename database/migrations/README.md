# Migrations

Apply in order via the Supabase SQL editor (or `supabase db push`). Each
file is idempotent — safe to re-run.

**Phase 2 (auth/security foundation):**
1. `001_initial_schema.sql` — `profiles`, `audit_logs`
2. `002_rls_policies.sql` — RLS for both
3. `003_role_protection.sql` — role self-escalation trigger

**Phase 4 (wellness experience — conversation/mood/activity persistence):**
4. `004_conversations.sql` — `conversations`
5. `005_messages.sql` — `messages`
6. `006_mood_events.sql` — `mood_events`
7. `007_wellness_activity_logs.sql` — `wellness_activity_logs`
8. `008_rls_policies.sql` — RLS for all four new tables, owner-scoped only
9. `009_indexes.sql` — query-pattern indexes for the four new tables

No RPC functions in Phase 4 either — every operation (create conversation,
add message, delete conversation, log a mood event/activity) is simple
single-table CRUD, no multi-table transaction that would justify one.

Deliberately NOT created: `wellness_activities` (the activity catalog is
static content in `pages/relaxation.py`, not a table), `feedback`
(nothing collects feedback yet), `admin_users` (still Phase 7).

**Phase 5 (wellness scales):**
10. `010_wellness_scales.sql` — adds `stress_level`, `energy_level`,
    `sleep_quality` (nullable, 1-5) to `mood_events`. No new table (the
    Phase 5 audit's decision: reuse `mood_events` rather than create a
    new one), no new RLS policy needed (RLS is row-level, and the
    existing `mood_events` policies already cover the whole row).
