import time
from pathlib import Path

from mailagent.state import InboxState, ThreadState


def test_processed_emails_not_reprocessed(tmp_path):
    state = InboxState(tmp_path, "you@example.com")
    assert state.has("a.eml") is False

    state.add("a.eml")
    assert state.has("a.eml") is True


def test_state_file_survives_restart(tmp_path):
    state1 = InboxState(tmp_path, "you@example.com")
    state1.add("b.eml")

    state2 = InboxState(tmp_path, "you@example.com")
    assert state2.has("b.eml") is True


def test_pruning_removes_stale_entries(tmp_path):
    watch_dir = tmp_path / "maildir"
    watch_dir.mkdir()
    (watch_dir / "keep.eml").write_text("x", encoding="utf-8")

    state = InboxState(tmp_path, "you@example.com")
    state.add("keep.eml")
    state.add("stale.eml")

    before, after = state.prune(watch_dir, threshold=1)
    assert before == 2
    assert after == 1
    assert state.has("keep.eml")
    assert not state.has("stale.eml")


def test_thread_state_record_and_lookup(tmp_path):
    ts = ThreadState(tmp_path, "you@example.com")
    assert ts.is_own("<msg1@example.com>") is False

    ts.record_sent("<msg1@example.com>", None)
    assert ts.is_own("<msg1@example.com>") is True
    assert ts.is_own("<msg2@example.com>") is False


def test_thread_state_depth_tracking(tmp_path):
    ts = ThreadState(tmp_path, "you@example.com")

    # First reply — no parent, depth 0
    assert ts.get_depth("") == 0
    ts.record_sent("<reply1@example.com>", "<incoming1@example.com>")

    # Incoming reply to our reply1 — depth should be 1
    assert ts.get_depth("<reply1@example.com>") == 1

    # We reply again at depth 1
    ts.record_sent("<reply2@example.com>", "<incoming2@example.com>")
    # This second reply had no known parent, so depth 0 again
    assert ts.get_depth("<reply2@example.com>") == 1


def test_thread_state_survives_restart(tmp_path):
    ts1 = ThreadState(tmp_path, "you@example.com")
    ts1.record_sent("<msg1@example.com>", None)

    ts2 = ThreadState(tmp_path, "you@example.com")
    assert ts2.is_own("<msg1@example.com>") is True


def test_thread_state_prune_removes_old_entries(tmp_path):
    ts = ThreadState(tmp_path, "you@example.com")
    ts.record_sent("<old@example.com>", None)
    # Manually set timestamp to 60 days ago
    ts._entries["<old@example.com>"]["timestamp"] = time.time() - 60 * 86400
    ts._save()

    ts.record_sent("<new@example.com>", None)

    removed = ts.prune(max_age_days=30)
    assert removed == 1
    assert ts.is_own("<old@example.com>") is False
    assert ts.is_own("<new@example.com>") is True
