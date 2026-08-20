-- =============================================================================
-- 007_wellness_activity_logs.sql
-- Sahay AI — Phase 4: relaxation/wellness activity completion logging
-- =============================================================================
-- The activities themselves (breathing, grounding, journaling prompts,
-- etc.) are static content in pages/relaxation.py, not database rows —
-- only USE of an activity is logged, for the wellness dashboard's
-- non-clinical "activities completed" count.
create table if not exists public.wellness_activity_logs (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references auth.users (id) on delete cascade,
    activity_key   text not null,
    completed_at   timestamptz not null default now()
);

comment on table public.wellness_activity_logs is
    'One row per completed relaxation/wellness activity. activity_key '
    'matches a key in pages/relaxation.py''s static activity list, not '
    'a foreign key (the activity catalog is code, not a table).';
