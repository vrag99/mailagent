from pathlib import Path

from mailagent.state import InboxState


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
