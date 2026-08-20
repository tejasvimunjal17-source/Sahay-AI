-- =============================================================================
-- 010_wellness_scales.sql
-- Sahay AI — Phase 5: stress/energy/sleep self-report scales
-- =============================================================================
-- Extends the existing mood_events table (per the approved Phase 5 audit —
-- reuse existing tables, don't create a new one) with three optional,
-- self-reported 1-5 scales. Same ownership/RLS model as every other
-- column on this table: row-level security already scopes the whole row
-- to auth.uid() = user_id (see 008_rls_policies.sql), so no new RLS
-- policy is needed — RLS is row-level, not column-level.
--
-- All three columns are nullable: a chat-derived mood_event (source=chat)
-- never has these values, and a check-in (source=checkin) only has them
-- if the student chose to fill them in — nothing is mandatory.
--
-- Idempotent: uses ADD COLUMN IF NOT EXISTS, safe to re-run.
-- =============================================================================

alter table public.mood_events
    add column if not exists stress_level smallint check (stress_level between 1 and 5),
    add column if not exists energy_level smallint check (energy_level between 1 and 5),
    add column if not exists sleep_quality smallint check (sleep_quality between 1 and 5);

comment on column public.mood_events.stress_level is
    'Self-reported stress, 1 (low) - 5 (high). Non-clinical, optional.';
comment on column public.mood_events.energy_level is
    'Self-reported energy, 1 (low) - 5 (high). Non-clinical, optional.';
comment on column public.mood_events.sleep_quality is
    'Self-reported sleep quality, 1 (poor) - 5 (great). Non-clinical, optional.';
