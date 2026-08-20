-- =============================================================================
-- 006_mood_events.sql
-- Sahay AI — Phase 4: non-clinical mood signal persistence
-- =============================================================================
-- Stores BOTH chat-derived mood classifications (chatbot/mood_analyzer.py)
-- and explicit mood check-ins (pages/mood_checkin.py) — `source`
-- distinguishes them. Never a medical record; risk_level is the same
-- non-clinical signal defined in chatbot/mood_analyzer.py, not a
-- diagnosis or clinical score.
create table if not exists public.mood_events (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users (id) on delete cascade,
    conversation_id  uuid references public.conversations (id) on delete set null,
    source           text not null check (source in ('chat', 'checkin')),
    mood             text not null,
    sentiment        text,
    confidence       real,
    risk_level       text,
    note             text,
    created_at       timestamptz not null default now()
);

comment on table public.mood_events is
    'Non-clinical mood signal, from either an in-chat classification '
    '(source=chat) or an explicit check-in (source=checkin). Never '
    'exposed to the user as a diagnosis — see chatbot/mood_analyzer.py '
    'and pages/mood_checkin.py for the framing rules.';
