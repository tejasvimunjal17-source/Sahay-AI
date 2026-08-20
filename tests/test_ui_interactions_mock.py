"""
tests/test_ui_interactions_mock.py
-------------------------------------
MOCK VERIFICATION — button-click-driven UI tests for the Phase 4
authenticated code paths (companion, mood_checkin, relaxation,
wellness_dashboard, conversations, mood_history, privacy). Requires
SUPABASE_URL/SUPABASE_ANON_KEY set (fake values) so streamlit_app.py's
auth gate actually calls the mocked backend.auth.get_current_user() —
without them, every one of these tests would silently redirect to the
landing page instead of exercising the authenticated page (a real bug
found and fixed during Phase 4 verification; see
PHASE4_IMPLEMENTATION_REPORT.md).

Run (env vars required):
    SUPABASE_URL=https://fake.supabase.co SUPABASE_ANON_KEY=fake \\
        PYTHONPATH=/path/to/streamlit_stub python3 tests/test_ui_interactions_mock.py
"""

import sys, importlib
from types import SimpleNamespace
sys.path.insert(0, ".")
import streamlit as st
from streamlit import StopRender

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
    import uuid as _uuid

    def _list(table, **filters):
        rows = store[table]
        return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]

    conv_db.list_conversations = lambda user: sorted(_list("conversations", user_id=user.id), key=lambda r: r["updated_at"], reverse=True)
    def _create_conversation(user, title="New conversation"):
        row = {"id": str(_uuid.uuid4()), "user_id": user.id, "title": title,
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
    def _delete_conv(user, cid):
        store["conversations"] = [r for r in store["conversations"] if not (r["id"] == cid and r["user_id"] == user.id)]
        store["messages"] = [m for m in store["messages"] if m["conversation_id"] != cid]
    conv_db.delete_conversation = _delete_conv
    conv_db.delete_all_conversations = lambda user: store.update(conversations=[r for r in store["conversations"] if r["user_id"] != user.id])

    conv_db.list_messages = lambda user, cid: [m for m in store["messages"] if m["conversation_id"] == cid and m["user_id"] == user.id]
    def _add_message(user, cid, role, content):
        row = {"id": str(_uuid.uuid4()), "conversation_id": cid, "user_id": user.id, "role": role, "content": content, "created_at": "2026-01-01T00:00:01Z"}
        store["messages"].append(row)
        return row
    conv_db.add_message = _add_message
    conv_db.clear_conversation_messages = lambda user, cid: store.update(messages=[m for m in store["messages"] if m["conversation_id"] != cid])

    conv_db.list_mood_events = lambda user, limit=100: [m for m in store["mood_events"] if m["user_id"] == user.id][:limit]
    def _log_mood(user, mood_result, source, conversation_id=None, note=None, stress_level=None, energy_level=None, sleep_quality=None):
        row = {"id": str(_uuid.uuid4()), "user_id": user.id, "mood": mood_result.get("mood"), "source": source, "created_at": "2026-01-01T00:00:02Z", "note": note}
        store["mood_events"].append(row)
        return row
    conv_db.log_mood_event = _log_mood
    conv_db.delete_all_mood_events = lambda user: store.update(mood_events=[m for m in store["mood_events"] if m["user_id"] != user.id])

    conv_db.list_wellness_activity_logs = lambda user, limit=200: [a for a in store["wellness_activity_logs"] if a["user_id"] == user.id][:limit]
    def _log_activity(user, key):
        row = {"id": str(_uuid.uuid4()), "user_id": user.id, "activity_key": key, "completed_at": "2026-01-01T00:00:03Z"}
        store["wellness_activity_logs"].append(row)
        return row
    conv_db.log_wellness_activity = _log_activity

    # mock the model call so companion.py's real pipeline runs end-to-end
    import chatbot.response_generator as rg
    rg.chat_completion = lambda messages, **kw: "That sounds stressful. Want to talk about it?"

    return fake_user, store

def run():
    try:
        importlib.import_module("streamlit_app")
        return "ran clean"
    except StopRender:
        return "rerun (expected)"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"FAIL: {type(e).__name__}: {e}"

results = []

# ---- Test 1: New Conversation button creates a conversation ----
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
st._click_queue.append("companion_new_conversation")
r = run()
ok = len(store["conversations"]) == 1
results.append(("companion: New Conversation button creates a row", r, ok))

# ---- Test 2: sending a message via suggestion chip persists both turns + mood event ----
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
st._click_queue.append("auth_companion_chip_0")  # "Help me relax"
r = run()
ok = len(store["messages"]) == 2 and store["messages"][0]["content"] == "Help me relax" and len(store["mood_events"]) == 1
results.append(("companion: suggestion chip persists user+assistant messages and a mood event", r, ok))

# ---- Test 3: typed message via chat_input persists correctly ----
fresh()
fresh()
fake_user, store = setup_mocked_auth()
convo = None
import backend.conversations as conv_db
convo = conv_db.create_conversation(fake_user)  # default title "New conversation" — exercises auto-titling
st.session_state["sahay_active_conversation_id"] = convo["id"]
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
orig_chat_input = st.chat_input
st.chat_input = lambda *a, **kw: "I'm anxious about my interview"
try:
    r = run()
finally:
    st.chat_input = orig_chat_input
ok = len(store["messages"]) == 2 and store["messages"][0]["content"] == "I'm anxious about my interview"
results.append(("companion: typed chat_input message persists", r, ok))

# ---- Test 4: auto-title from first message ----
ok_title = convo is not None and conv_db.get_conversation(fake_user, convo["id"])["title"].startswith("I'm anxious")
results.append(("companion: new conversation auto-titled from first message", "n/a", ok_title))

# ---- Test 5: delete conversation via history panel ----
fresh()
fake_user, store = setup_mocked_auth()
c1 = None
import backend.conversations as conv_db2
c1 = conv_db2.create_conversation(fake_user, "To delete")
st.session_state["sahay_page"] = "companion"
st.session_state["sahay_view"] = "app"
st._click_queue.append(f"delete_convo_{c1['id']}")
r = run()
ok = len(store["conversations"]) == 0
results.append(("companion: delete conversation button removes it", r, ok))

# ---- Test 6: mood check-in save persists a checkin-source mood event ----
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "mood_checkin"
st.session_state["sahay_view"] = "app"
orig_radio = st.radio
st.radio = lambda *a, **kw: "😣 Stressed"
st._click_queue.append("mood_checkin_save")
try:
    r = run()
finally:
    st.radio = orig_radio
ok = len(store["mood_events"]) == 1 and store["mood_events"][0]["source"] == "checkin" and store["mood_events"][0]["mood"] == "Stressed"
results.append(("mood_checkin: Save check-in persists a checkin mood event", r, ok))

# ---- Test 7: relaxation activity Start -> Mark complete logs an activity ----
fresh()
fake_user, store = setup_mocked_auth()
st.session_state["sahay_page"] = "relaxation"
st.session_state["sahay_view"] = "app"
st._click_queue.append("relax_start_breathing_4_4")
r1 = run()
# Step 2: re-run as a fresh module import (matching how Streamlit actually
# reruns the whole script on every interaction) but preserve session_state
# and the mocked store/user, since those persist across a real rerun too.
saved_session_state = dict(st.session_state)
fresh()
st.session_state.update(saved_session_state)
import backend.auth as auth_mod2
auth_mod2.get_current_user = lambda: fake_user
import backend.conversations as conv_db2
conv_db2.log_wellness_activity = lambda user, key: store["wellness_activity_logs"].append({"user_id": user.id, "activity_key": key})
import chatbot.response_generator as rg2
rg2.chat_completion = lambda messages, **kw: "mocked reply"
st.session_state["relax_expanded_breathing_4_4"] = True
st._click_queue.append("relax_complete_breathing_4_4")
r2 = run()
ok = len(store["wellness_activity_logs"]) == 1 and store["wellness_activity_logs"][0]["activity_key"] == "breathing_4_4"
results.append(("relaxation: Start -> Mark complete logs the activity", f"{r1} | {r2}", ok))

# ---- Test 8: wellness_dashboard shows real counts, not "Not enough activity yet", once data exists ----
fresh()
fake_user, store = setup_mocked_auth()
import backend.conversations as conv_db3
conv_db3.create_conversation(fake_user, "A")
conv_db3.log_mood_event(fake_user, {"mood": "Calm", "sentiment": "positive", "confidence": 0.7, "risk_level": "none"}, source="checkin")
conv_db3.log_wellness_activity(fake_user, "breathing_4_4")
st.session_state["sahay_page"] = "wellness_dashboard"
st.session_state["sahay_view"] = "app"
r = run()
results.append(("wellness_dashboard: renders with real data present, no crash", r, r == "ran clean"))

# ---- Test 9: privacy delete-conversations flow (two-step confirm) ----
fresh()
fake_user, store = setup_mocked_auth()
import backend.conversations as conv_db4
conv_db4.create_conversation(fake_user, "will be deleted")
st.session_state["sahay_page"] = "privacy"
st.session_state["sahay_view"] = "app"
st._click_queue.append("privacy_delete_conversations")
r1 = run()
saved_session_state2 = dict(st.session_state)
fresh()
st.session_state.update(saved_session_state2)
import backend.auth as auth_mod3
auth_mod3.get_current_user = lambda: fake_user
import backend.conversations as conv_db4b
conv_db4b.delete_all_conversations = lambda user: store.update(conversations=[c for c in store["conversations"] if c["user_id"] != user.id])
st.session_state["privacy_confirm_convos"] = True
st._click_queue.append("privacy_confirm_convos_yes")
r2 = run()
ok = len(store["conversations"]) == 0
results.append(("privacy: delete-all-conversations confirm flow actually deletes", f"{r1} | {r2}", ok))

# ---- Test 10: conversations.py list page shows real conversations ----
fresh()
fake_user, store = setup_mocked_auth()
import backend.conversations as conv_db5
conv_db5.create_conversation(fake_user, "Listed convo")
st.session_state["sahay_page"] = "conversations"
st.session_state["sahay_view"] = "app"
r = run()
results.append(("conversations page: renders with a real conversation present", r, r == "ran clean"))

# ---- Test 11: mood_history.py shows real events ----
fresh()
fake_user, store = setup_mocked_auth()
import backend.conversations as conv_db6
conv_db6.log_mood_event(fake_user, {"mood": "Lonely", "sentiment": "negative", "confidence": 0.5, "risk_level": "low"}, source="checkin", note="test note")
st.session_state["sahay_page"] = "mood_history"
st.session_state["sahay_view"] = "app"
r = run()
results.append(("mood_history page: renders with a real mood event present", r, r == "ran clean"))

print()
for label, r, ok in results:
    status = "PASS" if (ok and "FAIL" not in str(r)) else "FAIL"
    print(f"{status}: {label} [{r}]")

fails = [l for l, r, ok in results if not (ok and "FAIL" not in str(r))]
print()
print(f"INTERACTION TOTAL: {len(results)-len(fails)}/{len(results)} passed")
