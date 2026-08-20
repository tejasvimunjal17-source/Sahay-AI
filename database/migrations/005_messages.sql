-- =============================================================================
-- 005_messages.sql
-- Sahay AI — Phase 4: message persistence
-- =============================================================================
-- Deliberately stores only role/content/timestamps. Never a system prompt,
-- never chain-of-thought, never API keys. `role` is constrained to the two
-- user-visible roles — any internal system/developer message stays out of
-- persisted history entirely (chatbot/response_generator.py never asks to
-- store one).
create table if not exists public.messages (
    id               uuid primary key default gen_random_uuid(),
    conversation_id  uuid not null references public.conversations (id) on delete cascade,
    user_id          uuid not null references auth.users (id) on delete cascade,
    role             text not null check (role in ('user', 'assistant')),
    content          text not null,
    created_at       timestamptz not null default now()
);

comment on table public.messages is
    'Chat turns for a conversation. user_id is denormalized from the '
    'parent conversation for simpler, faster RLS policies (avoids a '
    'subquery/join on every row-level check) — see 008_rls_policies.sql.';
