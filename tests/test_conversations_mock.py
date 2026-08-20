"""
tests/test_conversations_mock.py
-----------------------------------
MOCK VERIFICATION — NOT a live Supabase test. A fake Supabase client
(supporting select/insert/update/delete/eq/order/limit/single, enough
for backend/conversations.py's actual query shapes) lets these tests
exercise the real CRUD logic without a network call.

What this CANNOT verify (needs a real Postgres/Supabase instance):
  - that RLS actually blocks cross-user access at the database layer
  - that ON DELETE CASCADE actually removes messages when a conversation
    is deleted
  - real query performance/index usage

What this DOES verify: every write this module makes is scoped by
user_id (both in what gets inserted AND in the .eq("user_id", ...)
filter applied to every select/update/delete), so even if RLS were
somehow bypassed, the application-layer code itself never asks for
another user's data. See tests/test_static_security.py for a
grep-based structural check of the same property across the whole file.

Run: python3 tests/test_conversations_mock.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures: list[str] = []
total_checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


class FakeQuery:
    def __init__(self, store: dict, table: str):
        self.store = store
        self.table_name = table
        self.filters: dict = {}
        self.insert_payload = None
        self.update_payload = None
        self.delete_mode = False
        self.order_field = None
        self.order_desc = False
        self.limit_n = None
        self.single_mode = False

    def select(self, *a, **kw):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, field, desc=False):
        self.order_field = field
        self.order_desc = desc
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def single(self):
        self.single_mode = True
        return self

    def _matched(self):
        rows = self.store.setdefault(self.table_name, [])
        return [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])

        if self.insert_payload is not None:
            row = dict(self.insert_payload)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", "2026-01-01T00:00:00Z")
            row.setdefault("updated_at", "2026-01-01T00:00:00Z")
            row.setdefault("completed_at", "2026-01-01T00:00:00Z")
            rows.append(row)
            return SimpleNamespace(data=[row])

        if self.update_payload is not None:
            for r in self._matched():
                r.update(self.update_payload)
            return SimpleNamespace(data=[])

        if self.delete_mode:
            matched_ids = {id(r) for r in self._matched()}
            remaining = [r for r in rows if id(r) not in matched_ids]
            self.store[self.table_name] = remaining
            # Simulate ON DELETE CASCADE for conversations -> messages, for
            # test realism (the real cascade is a Postgres FK, untestable
            # here, but this keeps the fake store internally consistent).
            if self.table_name == "conversations":
                deleted_ids = {r["id"] for r in self._matched_before_delete}
                self.store["messages"] = [
                    m for m in self.store.get("messages", []) if m.get("conversation_id") not in deleted_ids
                ]
            return SimpleNamespace(data=[])

        matched = self._matched()
        if self.order_field:
            matched = sorted(matched, key=lambda r: r.get(self.order_field, ""), reverse=self.order_desc)
        if self.limit_n:
            matched = matched[: self.limit_n]
        if self.single_mode:
            return SimpleNamespace(data=matched[0] if matched else None)
        return SimpleNamespace(data=matched)

    # capture pre-delete match set for the cascade simulation above
    def delete(self):
        self.delete_mode = True
        self._matched_before_delete = None
        return self


class FakeClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        q = FakeQuery(self.store, name)
        # snapshot matched rows lazily right before execute() for delete-cascade sim
        orig_execute = q.execute
        def execute_with_snapshot():
            if q.delete_mode:
                q._matched_before_delete = q._matched()
            return orig_execute()
        q.execute = execute_with_snapshot
        return q


def run() -> int:
    store: dict = {}
    fake_client = FakeClient(store)

    import backend.conversations as conv_db
    conv_db.get_client_for_current_user = lambda: fake_client

    user_a = SimpleNamespace(id="user-a")
    user_b = SimpleNamespace(id="user-b")

    # ---- Create conversation ----
    c = conv_db.create_conversation(user_a, title="Exam stress")
    check("create_conversation returns a row with an id", bool(c.get("id")))
    check("create_conversation sets the requested title", c["title"] == "Exam stress")
    check("create_conversation stores the correct user_id", c["user_id"] == "user-a")
    convo_id = c["id"]

    # ---- Add messages ----
    m1 = conv_db.add_message(user_a, convo_id, "user", "I'm stressed about exams")
    m2 = conv_db.add_message(user_a, convo_id, "assistant", "That sounds hard. Want to talk about it?")
    check("add_message stores user_id on the message row", m1["user_id"] == "user-a")
    try:
        conv_db.add_message(user_a, convo_id, "system", "bad role")
        check("add_message rejects an invalid role", False)
    except ValueError:
        check("add_message rejects an invalid role", True)

    # ---- List messages, correct order ----
    messages = conv_db.list_messages(user_a, convo_id)
    check("list_messages returns both messages", len(messages) == 2)

    # ---- User isolation: user_b cannot see user_a's conversation ----
    convos_b = conv_db.list_conversations(user_b)
    check("Another user's list_conversations returns nothing for user_a's data", len(convos_b) == 0)
    messages_b = conv_db.list_messages(user_b, convo_id)
    check("Another user's list_messages returns nothing for user_a's conversation", len(messages_b) == 0)

    # ---- Rename ----
    conv_db.rename_conversation(user_a, convo_id, "Exam stress (renamed)")
    updated = conv_db.get_conversation(user_a, convo_id)
    check("rename_conversation updates the title", updated["title"] == "Exam stress (renamed)")

    # ---- Clear messages, keep conversation ----
    conv_db.clear_conversation_messages(user_a, convo_id)
    check("clear_conversation_messages empties the message list", conv_db.list_messages(user_a, convo_id) == [])
    check("clear_conversation_messages keeps the conversation itself", conv_db.get_conversation(user_a, convo_id) is not None)

    # ---- Mood events ----
    mood_result = {"mood": "Stressed", "sentiment": "negative", "confidence": 0.8, "risk_level": "low"}
    conv_db.log_mood_event(user_a, mood_result, source="chat", conversation_id=convo_id)
    conv_db.log_mood_event(user_a, {"mood": "Calm", "sentiment": "neutral", "confidence": 0.6, "risk_level": "none"}, source="checkin", note="feeling better")
    events = conv_db.list_mood_events(user_a)
    check("log_mood_event + list_mood_events round-trips 2 events", len(events) == 2)
    try:
        conv_db.log_mood_event(user_a, mood_result, source="bogus")
        check("log_mood_event rejects an invalid source", False)
    except ValueError:
        check("log_mood_event rejects an invalid source", True)

    events_b = conv_db.list_mood_events(user_b)
    check("Another user's list_mood_events returns nothing for user_a's events", len(events_b) == 0)

    # ---- Wellness activity logs ----
    conv_db.log_wellness_activity(user_a, "breathing_4_4")
    conv_db.log_wellness_activity(user_a, "grounding_54321")
    logs = conv_db.list_wellness_activity_logs(user_a)
    check("log_wellness_activity + list round-trips 2 entries", len(logs) == 2)

    # ---- Delete conversation cascades to messages (simulated) ----
    conv_db.add_message(user_a, convo_id, "user", "one more message")
    conv_db.delete_conversation(user_a, convo_id)
    check("delete_conversation removes the conversation", conv_db.get_conversation(user_a, convo_id) is None)
    check("delete_conversation cascades to its messages", conv_db.list_messages(user_a, convo_id) == [])

    # ---- delete_all_conversations only affects the calling user ----
    conv_db.create_conversation(user_a, title="A")
    conv_db.create_conversation(user_a, title="B")
    conv_db.create_conversation(user_b, title="user_b's convo")
    conv_db.delete_all_conversations(user_a)
    check("delete_all_conversations clears user_a's conversations", conv_db.list_conversations(user_a) == [])
    check("delete_all_conversations does NOT touch user_b's conversations", len(conv_db.list_conversations(user_b)) == 1)

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (MOCK verification — fake Supabase client, no network)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
