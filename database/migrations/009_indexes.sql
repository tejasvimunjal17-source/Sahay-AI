-- =============================================================================
-- 009_indexes.sql
-- Sahay AI — Phase 4 indexes
-- =============================================================================
-- Primary keys already index id columns automatically; these cover the
-- actual query patterns backend/conversations.py uses: list a user's
-- conversations by recency, list a conversation's messages in order,
-- list a user's mood/activity history by recency.

create index if not exists idx_conversations_user_updated
    on public.conversations (user_id, updated_at desc);

create index if not exists idx_messages_conversation_created
    on public.messages (conversation_id, created_at);

create index if not exists idx_messages_user
    on public.messages (user_id);

create index if not exists idx_mood_events_user_created
    on public.mood_events (user_id, created_at desc);

create index if not exists idx_wellness_activity_logs_user_completed
    on public.wellness_activity_logs (user_id, completed_at desc);
