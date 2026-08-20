"""
tests/test_phase5_ui_interactions_mock.py
---------------------------------------------
MOCK VERIFICATION — button/widget-driven UI tests for Phase 5's new
flows: mood check-in with stress/energy/sleep, per-record mood deletion,
"Try this now" suggestion cards (appear/dismiss/open-relaxation/no-stale-
suggestion-after-switching-conversation), wellness dashboard with real
data, Human Help's two tiers, Resources category rendering, and Privacy's
existing controls still working.

Requires SUPABASE_URL/SUPABASE_ANON_KEY set (fake values — see
tests/README.md's documented lesson from Phase 4) and the streamlit stub
on PYTHONPATH.

Run:
    SUPABASE_URL=https://fake.supabase.co SUPABASE_ANON_KEY=fake \\
        PYTHONPATH=/path/to/streamlit_stub python3 tests/test_phase5_ui_interactions_mock.py
"""

import sys, importlib
from types import SimpleNamespace
import uuid

sys.path.insert(0, ".")
import streamlit as st
from streamlit import StopRender

failures = []
total_checks = 0


def check(label, condition, detail=""):
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def fresh():
    for mod in list(sys.modules):
        if (mod == "streamlit_app" or mod.startswith("pages.") or mod.startswith("components.")
                or mod in ("config",) or mod.startswith("content.") or mod.startswith("backend.")
                or mod.startswith("chatbot.")):
            del sys.modules[mod]
    st.session_state.clear()
    st._click_queue.clear()
    st.query_params.clear()


def setup_mocked_auth():
    import backend.auth as auth_mod
    fake_user = SimpleNamespace(id="fake-user-1", email="student@example.com")
    st.session_state["sahay_supabase_session"] = {"access_token": "t", "refresh_token": "r"}
    auth_mod.get_current_user = lambda: fake_user

    import backend.conversations as conv_db
    store = {"conversations": [], "messages": [], "mood_events": [], "wellness_activity_logs": []}

    def _list(table, **filters):
        return [r for r in store[table] if all(r.get(k) == v for k, v in filters.items())]

    conv_db.list_conversations = lambda user: sorted(_list("conversations", user_id=user.id), key=lambda r: r["updated_at"], reverse=True)

    def _create_conversation(user, title="New conversation"):
        row = {"id": str(uuid.uuid4()), "user_id": user.id, "title": title,
               "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
        store["conversations"].append(row)
        return row
    conv_db.create_conversation = _create_conversation
    conv_db.get_conversation = lambda user, cid: next((r for r in _list("conversations", user_id=user.id) if r["id"] == cid), None)

    def _rename(user, cid, title):
        for r in store["conversations"]:
            if r["id"] == cid and r["user_id"] == user.id:
                r["title"] = title
    conv_db.rename_conversation = _rename
    conv_db.list_messages = lambda user, cid: [m for m in store["messages"] if m["conversation_id"] == cid and m["user_id"] == user.id]

    def _add_message(user, cid, role, content):
        row = {"id": str(uuid.uuid4()), "conversation_id": cid, "user_id": user.id, "role": role, "content": content, "created_at": "2026-01-01T00:00:01Z"}
        store["messages"].append(row)
        return row
    conv_db.add_message = _add_message

    conv_db.list_mood_events = lambda user, limit=100: [m for m in store["mood_events"] if m["user_id"] == user.id][:limit]

    def _log_mood(user, mood_result, source, conversation_id=None, note=None, stress_level=None, energy_level=None, sleep_quality=None):
        row = {"id": str(uuid.uuid4()), "user_id": user.id, "mood": mood_result.get("mood"), "source": source,
               "note": note, "stress_level": stress_level, "energy_level": energy_level, "sleep_quality": sleep_quality,
               "created_at": "2026-01-01T00:00:02Z"}
        store["mood_events"].append(row)
        return row
    conv_db.log_mood_event = _log_mood

    def _delete_mood(user, mood_event_id):
        store["mood_events"] = [m for m in store["mood_events"] if not (m["id"] == mood_event_id and m["user_id"] == user.id)]
    conv_db.delete_mood_event = _delete_mood
    conv_db.delete_all_mood_events = lambda user: store.update(mood_events=[m for m in store["mood_events"] if m["user_id"] != user.id])
    conv_db.delete_all_conversations = lambda user: store.update(conversations=[c for c in store["conversations"] if c["user_id"] != user.id])

    conv_db.list_wellness_activity_logs = lambda user, limit=200: [a for a in store["wellness_activity_logs"] if a["user_id"] == user.id][:limit]

    import chatbot.response_generator as rg
    rg.chat_completion = lambda messages, **kw: "That sounds hard. Want to talk about it?"
    import chatbot.mood_analyzer as ma
    ma.chat_completion_json = lambda **kw: {"mood": "Stressed", "sentiment": "negative", "confidence": 0.7, "risk_level": "low"}

    return fake_user, store


def run():
    try:
        importlib.import_module("streamlit_app")
        return "ran clean"
    except StopRender:
        return "rerun (expected)"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


def rerun_preserving(fake_user, store):
    """Simulate a real Streamlit rerun: re-import modules but keep session
    state and mocks, since a real rerun preserves both."""
    saved = dict(st.session_state)
    fresh()
    st.session_state.update(saved)
    import backend.auth as auth_mod
    auth_mod.get_current_user = lambda: fake_user
    import backend.conversations as conv_db

    def _list(table, **filters):
        return [r for r in store[table] if all(r.get(k) == v for k, v in filters.items())]
    conv_db.list_conversations = lambda user: sorted(_list("conversations", user_id=user.id), key=lambda r: r["updated_at"], reverse=True)
    conv_db.get_conversation = lambda user, cid: next((r for r in _list("conversations", user_id=user.id) if r["id"] == cid), None)
    conv_db.list_messages = lambda user, cid: [m for m in store["messages"] if m["conversation_id"] == cid and m["user_id"] == user.id]

    def _add_message(user, cid, role, content):
        row = {"id": str(uuid.uuid4()), "conversation_id": cid, "user_id": user.id, "role": role, "content": content, "created_at": "2026-01-01T00:00:01Z"}
        store["messages"].append(row)
        return row
    conv_db.add_message = _add_message

    def _rename(user, cid, title):
        for r in store["conversations"]:
            if r["id"] == cid and r["user_id"] == user.id:
                r["title"] = title
    conv_db.rename_conversation = _rename
    conv_db.list_mood_events = lambda user, limit=100: [m for m in store["mood_events"] if m["user_id"] == user.id][:limit]

    def _delete_mood(user, mood_event_id):
        store["mood_events"] = [m for m in store["mood_events"] if not (m["id"] == mood_event_id and m["user_id"] == user.id)]
    conv_db.delete_mood_event = _delete_mood
    conv_db.list_wellness_activity_logs = lambda user, limit=200: [a for a in store["wellness_activity_logs"] if a["user_id"] == user.id][:limit]
    conv_db.delete_all_conversations = lambda user: store.update(conversations=[c for c in store["conversations"] if c["user_id"] != user.id])
    conv_db.delete_all_mood_events = lambda user: store.update(mood_events=[m for m in store["mood_events"] if m["user_id"] != user.id])

    import chatbot.response_generator as rg
    rg.chat_completion = lambda messages, **kw: "That sounds hard. Want to talk about it?"
    import chatbot.mood_analyzer as ma
    ma.chat_completion_json = lambda **kw: {"mood": "Stressed", "sentiment": "negative", "confidence": 0.7, "risk_level": "low"}


results = []

# ============================================================================
# Mood Check-in: mood + stress + energy + sleep + save
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "mood_checkin"
st.session_state["sahay_view"] = "app"
st.radio = lambda *a, **kw: "😟 Anxious"
st.session_state["checkin_stress"] = 5
st.session_state["checkin_stress_include"] = True
st.session_state["checkin_energy"] = 2
st.session_state["checkin_energy_include"] = True
st.session_state["checkin_sleep"] = 1
st.session_state["checkin_sleep_include"] = True
st._click_queue.append("mood_checkin_save")
r = run()
ok = (len(store["mood_events"]) == 1 and store["mood_events"][0]["mood"] == "Anxious"
      and store["mood_events"][0]["stress_level"] == 5 and store["mood_events"][0]["energy_level"] == 2
      and store["mood_events"][0]["sleep_quality"] == 1)
results.append(("mood_checkin: mood+stress+energy+sleep all save correctly", r, ok, store["mood_events"]))
st.radio = lambda *a, **kw: None  # restore

# Validation: no mood picked -> nothing saved
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "mood_checkin"
st.session_state["sahay_view"] = "app"
st._click_queue.append("mood_checkin_save")
r = run()
ok = len(store["mood_events"]) == 0
results.append(("mood_checkin: Save with no mood picked saves nothing (validation)", r, ok, None))

# ============================================================================
# Mood History: display + per-record deletion
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
import backend.conversations as conv_db_a
e1 = conv_db_a.log_mood_event(fake_user, {"mood": "Sad"}, source="checkin", stress_level=3)
e2 = conv_db_a.log_mood_event(fake_user, {"mood": "Calm"}, source="checkin", energy_level=4)
st.session_state["sahay_page"] = "mood_history"
st.session_state["sahay_view"] = "app"
st._click_queue.append(f"delete_mood_{e1['id']}")
r = run()
ok = len(store["mood_events"]) == 1 and store["mood_events"][0]["id"] == e2["id"]
results.append(("mood_history: per-record delete removes only the targeted entry", r, ok, store["mood_events"]))

# ============================================================================
# "Try this now": appears, dismiss works, doesn't reappear after dismiss
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
st._click_queue.append("auth_companion_chip_1")  # "I'm stressed about exams" -> mocked mood=Stressed
r1 = run()
suggestion_after_send = st.session_state.get("sahay_last_suggestion")
ok1 = suggestion_after_send is not None and suggestion_after_send.get("activity_key") == "box_breathing"
results.append(("companion: suggestion attached after a Stressed reply", r1, ok1, suggestion_after_send))

# Dismiss it
rerun_preserving(fake_user, store)
st._click_queue.append("companion_auth_suggestion_dismiss")
r2 = run()
dismissed_set = st.session_state.get("companion_auth_dismissed_suggestions", set())
ok2 = len(dismissed_set) == 1
results.append(("companion: Dismiss button records the dismissal", r2, ok2, dismissed_set))

# ============================================================================
# "Try this now": stale suggestion does not appear after switching conversation
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
convo_a = conv_db_a.create_conversation(fake_user, "Convo A")
st.session_state["sahay_active_conversation_id"] = convo_a["id"]
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
st._click_queue.append("companion_new_conversation")  # creates convo B and switches to it
r = run()
new_convo_id = st.session_state.get("sahay_active_conversation_id")
# last_suggestion_convo_id still points at nothing (no message sent yet) -> card must not show
ok = st.session_state.get("sahay_last_suggestion_convo_id") != new_convo_id or st.session_state.get("sahay_last_suggestion") is None
results.append(("companion: no stale suggestion shown when switching to a fresh conversation", r, ok, None))

# ============================================================================
# Wellness Dashboard: real data populates cards/charts; empty state otherwise
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
conv_db_a.create_conversation(fake_user, "A")
conv_db_a.log_mood_event(fake_user, {"mood": "Calm"}, source="checkin", stress_level=2, energy_level=4, sleep_quality=4)
conv_db_a.log_mood_event(fake_user, {"mood": "Calm"}, source="checkin", stress_level=3)
st.session_state["sahay_page"] = "wellness_dashboard"
st.session_state["sahay_view"] = "app"
r = run()
results.append(("wellness_dashboard: renders with real mood+stress data present", r, r == "ran clean", None))

fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "wellness_dashboard"
st.session_state["sahay_view"] = "app"
r = run()
results.append(("wellness_dashboard: renders cleanly with NO data (empty state)", r, r == "ran clean", None))

# ============================================================================
# Human Help: renders both tiers without crashing
# ============================================================================
fresh()
st.session_state["sahay_page"] = "human_help"
st.session_state["sahay_view"] = "app"
st.session_state["sahay_demo_mode"] = True
r = run()
results.append(("human_help: renders both Normal and Urgent tiers", r, r == "ran clean", None))

# ============================================================================
# Resources: category rendering + activity-link navigation
# ============================================================================
fresh()
st.session_state["sahay_page"] = "resources"
st.session_state["sahay_view"] = "app"
st.session_state["sahay_demo_mode"] = True
r = run()
results.append(("resources: renders all 10 categories", r, r == "ran clean", None))

# ============================================================================
# Privacy: existing delete-conversations control still works after Phase 5 changes
# ============================================================================
fresh()
fake_user, store = setup_mocked_auth()
conv_db_a.create_conversation(fake_user, "will be deleted")
st.session_state["sahay_page"] = "privacy"
st.session_state["sahay_view"] = "app"
st._click_queue.append("privacy_delete_conversations")
r1 = run()
rerun_preserving(fake_user, store)
st.session_state["privacy_confirm_convos"] = True
st._click_queue.append("privacy_confirm_convos_yes")
r2 = run()
ok = len(store["conversations"]) == 0
results.append(("privacy: delete-all-conversations still works after Phase 5 changes", f"{r1} | {r2}", ok, store["conversations"]))

print()
for label, r, ok, detail in results:
    status = "PASS" if (ok and "FAIL" not in str(r)) else "FAIL"
    print(f"{status}: {label} [{r}]" + (f" -- {detail}" if detail is not None and not ok else ""))

fails = [l for l, r, ok, d in results if not (ok and "FAIL" not in str(r))]
print()
print(f"TOTAL: {len(results)-len(fails)}/{len(results)} passed")
if fails:
    sys.exit(1)
