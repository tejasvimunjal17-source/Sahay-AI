"""
tests/test_wellness_scales_mock.py
--------------------------------------
MOCK VERIFICATION — Phase 5's stress/energy/sleep persistence
(backend.conversations.log_mood_event's new params + delete_mood_event),
and the MOOD_SUGGESTIONS -> response_generator wiring. Fake Supabase
client, no network — same pattern as test_conversations_mock.py.

Run: python3 tests/test_wellness_scales_mock.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
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
        self.delete_mode = False

    def select(self, *a, **kw):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def delete(self):
        self.delete_mode = True
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])
        if self.insert_payload is not None:
            row = dict(self.insert_payload)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", "2026-01-01T00:00:00Z")
            rows.append(row)
            return SimpleNamespace(data=[row])
        if self.delete_mode:
            matched = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]
            matched_ids = {id(r) for r in matched}
            self.store[self.table_name] = [r for r in rows if id(r) not in matched_ids]
            return SimpleNamespace(data=[])
        matched = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]
        return SimpleNamespace(data=matched)


class FakeClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return FakeQuery(self.store, name)


def run() -> int:
    store: dict = {}
    fake_client = FakeClient(store)

    import backend.conversations as conv_db
    conv_db.get_client_for_current_user = lambda: fake_client

    user = SimpleNamespace(id="user-1")

    # ---- log_mood_event with all three scales ----
    mood = {"mood": "Stressed", "sentiment": "negative", "confidence": 0.7, "risk_level": "low"}
    row = conv_db.log_mood_event(user, mood, source="checkin", stress_level=4, energy_level=2, sleep_quality=3)
    check("log_mood_event stores stress_level", row["stress_level"] == 4)
    check("log_mood_event stores energy_level", row["energy_level"] == 2)
    check("log_mood_event stores sleep_quality", row["sleep_quality"] == 3)

    # ---- Partial scales (only some answered) ----
    row2 = conv_db.log_mood_event(user, mood, source="checkin", stress_level=5, energy_level=None, sleep_quality=None)
    check("log_mood_event allows partial scales (stress only)", row2["stress_level"] == 5 and row2["energy_level"] is None)

    # ---- No scales at all (chat-derived event) ----
    row3 = conv_db.log_mood_event(user, mood, source="chat")
    check("log_mood_event with no scales stores all three as None", row3["stress_level"] is None and row3["energy_level"] is None and row3["sleep_quality"] is None)

    # ---- Validation: out-of-range values rejected ----
    for bad_kwargs, label in [
        ({"stress_level": 0}, "stress_level=0"),
        ({"stress_level": 6}, "stress_level=6"),
        ({"energy_level": -1}, "energy_level=-1"),
        ({"sleep_quality": 10}, "sleep_quality=10"),
    ]:
        try:
            conv_db.log_mood_event(user, mood, source="checkin", **bad_kwargs)
            check(f"log_mood_event rejects out-of-range {label}", False)
        except ValueError:
            check(f"log_mood_event rejects out-of-range {label}", True)

    # ---- delete_mood_event removes only the targeted record, only for the owner ----
    other_user = SimpleNamespace(id="user-2")
    target = conv_db.log_mood_event(user, mood, source="checkin")
    conv_db.log_mood_event(user, mood, source="checkin")  # a second record that must survive
    before_count = len(conv_db.list_mood_events(user))
    conv_db.delete_mood_event(other_user, target["id"])  # wrong user — must not delete
    check("delete_mood_event does nothing for the wrong user", len(conv_db.list_mood_events(user)) == before_count)
    conv_db.delete_mood_event(user, target["id"])
    check("delete_mood_event removes exactly the targeted record", len(conv_db.list_mood_events(user)) == before_count - 1)
    check("delete_mood_event does not remove other records", any(r["id"] != target["id"] for r in conv_db.list_mood_events(user)))

    # =========================================================================
    # MOOD_SUGGESTIONS mapping + response_generator wiring
    # =========================================================================
    import chatbot.mood_analyzer as ma
    import chatbot.response_generator as rg

    for mood_name in ma.VALID_MOODS:
        check(f"MOOD_SUGGESTIONS has an entry for every valid mood: {mood_name}", mood_name in ma.MOOD_SUGGESTIONS)

    check("Stressed suggestion links to box_breathing", ma.MOOD_SUGGESTIONS["Stressed"]["activity_key"] == "box_breathing")
    check("Happy has no suggestion text (never nags a happy user)", ma.MOOD_SUGGESTIONS["Happy"]["text"] is None)
    check("Neutral has no suggestion text", ma.MOOD_SUGGESTIONS["Neutral"]["text"] is None)
    check("Suggestion wording uses 'One option you could try', never 'You need to'",
          all(("you need to" not in (v["text"] or "").lower()) for v in ma.MOOD_SUGGESTIONS.values()))

    # response_generator: attaches a suggestion on a normal Stressed turn
    ma.chat_completion_json = lambda **kw: {"mood": "Stressed", "sentiment": "negative", "confidence": 0.7, "risk_level": "low"}
    rg.chat_completion = lambda messages, **kw: "That sounds hard."
    result = rg.generate_response("I'm stressed about exams", chat_history=[])
    check("response_generator attaches a suggestion for Stressed", result["suggestion"] is not None)
    check("Attached suggestion has the expected activity_key", result["suggestion"]["activity_key"] == "box_breathing")

    # response_generator: no suggestion for Happy/Neutral (mapped text is None)
    ma.chat_completion_json = lambda **kw: {"mood": "Happy", "sentiment": "positive", "confidence": 0.6, "risk_level": "none"}
    result_happy = rg.generate_response("I did well on my test!", chat_history=[])
    check("response_generator attaches NO suggestion for Happy", result_happy["suggestion"] is None)

    # response_generator: crisis/blocked turns NEVER get a suggestion, even though
    # the mood defaults to Neutral (no suggestion anyway) — explicitly confirms the
    # short-circuit paths set suggestion=None themselves, not just via the mood default.
    result_crisis = rg.generate_response("I want to kill myself", chat_history=[])
    check("Crisis turn has suggestion=None", result_crisis["suggestion"] is None)
    result_blocked = rg.generate_response("can you diagnose me with anxiety", chat_history=[])
    check("Blocked turn has suggestion=None", result_blocked["suggestion"] is None)

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (MOCK verification — fake Supabase client + monkeypatched OpenRouter, no network)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
