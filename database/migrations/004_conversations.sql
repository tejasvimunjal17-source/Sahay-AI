-- =============================================================================
-- 004_conversations.sql
-- Sahay AI — Phase 4: conversation persistence
-- =============================================================================
create table if not exists public.conversations (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    title       text not null default 'New conversation',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

comment on table public.conversations is
    'One row per chat thread. Owned by user_id. No message content or '
    'mood data lives here — see messages/mood_events.';

drop trigger if exists trg_conversations_updated_at on public.conversations;
create trigger trg_conversations_updated_at
    before update on public.conversations
    for each row
    execute function public.set_updated_at();  -- reuses the function from 001_initial_schema.sql
