from pathlib import Path
from types import SimpleNamespace

from mailagent.config import (
    Config,
    Defaults,
    InboxConfig,
    Settings,
    Workflow,
    WorkflowAction,
    WorkflowMatch,
)
from mailagent.core.watcher import run


class FakeNotifier:
    def __init__(self, events):
        self._events = list(events)
        self._next_wd = 1

    def add_watch(self, _path, _flags):
        wd = self._next_wd
        self._next_wd += 1
        return wd

    def read(self, timeout=None):
        if self._events:
            return [self._events.pop(0)]
        return []


def _config() -> Config:
    inbox = InboxConfig(
        address="you@example.com",
        credentials={"password": "secret"},
        workflows=[
            Workflow(
                name="fallback",
                match=WorkflowMatch(intent="default"),
                action=WorkflowAction(type="ignore"),
            )
        ],
        classify_provider="p1",
        reply_provider="p1",
        system_prompt="sys",
    )

    return Config(
        providers={},
        defaults=Defaults(classify_provider="p1", reply_provider="p1"),
        inboxes=[inbox],
        settings=Settings(
            catch_up_on_start=False, data_dir="/tmp/mailagent-test-state"
        ),
    )


def test_unknown_watch_descriptor_ignored(monkeypatch, tmp_path):
    config = _config()
    config.settings.data_dir = str(tmp_path / "state")
    stop_event = SimpleNamespace(flag=False)
    stop_event.is_set = lambda: stop_event.flag
    stop_event.set = lambda: setattr(stop_event, "flag", True)

    watch_dir = tmp_path / "new"
    watch_dir.mkdir(parents=True)

    notifier = FakeNotifier([SimpleNamespace(wd=999, name="x.eml")])

    monkeypatch.setattr(
        "mailagent.core.watcher._create_notifier", lambda: (notifier, object())
    )
    monkeypatch.setattr(
        "mailagent.core.watcher.maildir_new_path", lambda _address: watch_dir
    )
    monkeypatch.setattr(
        "mailagent.core.watcher.build_provider", lambda _config, _name: object()
    )

    calls = []

    def fake_process(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("mailagent.core.watcher.process_email", fake_process)

    original_read = notifier.read

    def read_and_stop(timeout=None):
        events = original_read(timeout)
        stop_event.set()
        return events

    notifier.read = read_and_stop

    run(config, stop_event=stop_event)
    assert calls == []


def test_event_for_known_watch_calls_process_email(monkeypatch, tmp_path):
    config = _config()
    config.settings.data_dir = str(tmp_path / "state")
    stop_event = SimpleNamespace(flag=False)
    stop_event.is_set = lambda: stop_event.flag
    stop_event.set = lambda: setattr(stop_event, "flag", True)

    watch_dir = tmp_path / "new"
    watch_dir.mkdir(parents=True)
    (watch_dir / "msg.eml").write_text("dummy", encoding="utf-8")

    notifier = FakeNotifier([SimpleNamespace(wd=1, name="msg.eml")])

    monkeypatch.setattr(
        "mailagent.core.watcher._create_notifier", lambda: (notifier, object())
    )
    monkeypatch.setattr(
        "mailagent.core.watcher.maildir_new_path", lambda _address: watch_dir
    )
    monkeypatch.setattr(
        "mailagent.core.watcher.build_provider", lambda _config, _name: object()
    )

    calls = []

    def fake_process(filepath, runtime, cfg):
        calls.append((filepath, runtime.inbox.address, cfg))

    monkeypatch.setattr("mailagent.core.watcher.process_email", fake_process)

    original_read = notifier.read

    def read_and_stop(timeout=None):
        events = original_read(timeout)
        stop_event.set()
        return events

    notifier.read = read_and_stop

    run(config, stop_event=stop_event)

    assert len(calls) == 1
    assert calls[0][0] == Path(watch_dir / "msg.eml")
    assert calls[0][1] == "you@example.com"
