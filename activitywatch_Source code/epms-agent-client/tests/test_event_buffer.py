"""Tests for the SQLite-backed event buffer."""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

import pytest

from epms_agent.event_buffer import EventBuffer


@pytest.fixture
def buffer():
    """Create and yield a closed EventBuffer with clean temp db."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_events.db")
    eb = EventBuffer(db_path)
    try:
        yield eb
    finally:
        eb.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestEventBuffer:
    def test_init_creates_db(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_events.db")
        eb = EventBuffer(db_path, max_events=100, max_age_days=7)
        assert os.path.exists(db_path)
        assert eb.count_pending() == 0
        eb.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_enqueue_and_count(self, buffer):
        event_id = buffer.enqueue("heartbeat", {"timestamp": "2026-01-01T00:00:00"})
        assert event_id is not None
        assert buffer.count_pending() == 1

    def test_get_pending_returns_fifo(self, buffer):
        buffer.enqueue("heartbeat", {"seq": 1})
        buffer.enqueue("heartbeat", {"seq": 2})
        buffer.enqueue("heartbeat", {"seq": 3})
        pending = buffer.get_pending(limit=10)
        assert len(pending) == 3
        assert pending[0]["data"]["seq"] == 1
        assert pending[1]["data"]["seq"] == 2
        assert pending[2]["data"]["seq"] == 3

    def test_ack_removes_event(self, buffer):
        event_id = buffer.enqueue("heartbeat", {"test": True})
        assert buffer.count_pending() == 1
        buffer.ack(event_id)
        assert buffer.count_pending() == 0

    def test_ack_all(self, buffer):
        e1 = buffer.enqueue("heartbeat", {"seq": 1})
        e2 = buffer.enqueue("heartbeat", {"seq": 2})
        buffer.ack(e1)
        buffer.ack(e2)
        assert buffer.count_pending() == 0

    def test_clear(self, buffer):
        buffer.enqueue("heartbeat", {"test": True})
        buffer.enqueue("heartbeat", {"test": False})
        assert buffer.count_pending() == 2
        buffer.clear()
        assert buffer.count_pending() == 0

    def test_mark_sent_increments_counter(self, buffer):
        event_id = buffer.enqueue("heartbeat", {"test": True})
        pending = buffer.get_pending()
        assert pending[0]["sent_count"] == 0
        buffer.mark_sent(event_id)
        pending = buffer.get_pending()
        assert pending[0]["sent_count"] == 1
        buffer.mark_sent(event_id, "connection refused")
        pending = buffer.get_pending()
        assert pending[0]["sent_count"] == 2
        assert pending[0]["last_error"] == "connection refused"

    def test_replay_all_calls_send_fn(self, buffer):
        buffer.enqueue("heartbeat", {"seq": 1})
        buffer.enqueue("heartbeat", {"seq": 2})
        buffer.enqueue("heartbeat", {"seq": 3})
        replayed = []
        send_fn = lambda typ, data: replayed.append((typ, data)) or True
        count = buffer.replay_all(send_fn)
        assert count == 3
        assert len(replayed) == 3
        assert replayed[0] == ("heartbeat", {"seq": 1})
        assert replayed[1] == ("heartbeat", {"seq": 2})
        assert replayed[2] == ("heartbeat", {"seq": 3})
        assert buffer.count_pending() == 0

    def test_replay_all_send_fn_failure(self, buffer):
        """Events should remain in buffer if send_fn returns False."""
        buffer.enqueue("heartbeat", {"seq": 1})
        buffer.enqueue("heartbeat", {"seq": 2})
        call_count = 0
        def send_fn(typ, data):
            nonlocal call_count
            call_count += 1
            return False
        count = buffer.replay_all(send_fn)
        assert count == 0
        assert call_count == 2
        assert buffer.count_pending() == 2

    def test_replay_all_send_fn_exception(self, buffer):
        """Events should remain in buffer if send_fn raises."""
        buffer.enqueue("heartbeat", {"seq": 1})
        buffer.enqueue("heartbeat", {"seq": 2})
        call_count = 0
        def send_fn(typ, data):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("oh no")
        count = buffer.replay_all(send_fn)
        assert count == 0
        assert call_count == 2
        pending = buffer.get_pending()
        assert len(pending) == 2
        assert pending[0]["sent_count"] == 1
        assert pending[1]["sent_count"] == 1

    def test_prune_over_capacity(self, buffer):
        buffer._max_events = 3
        buffer.enqueue("heartbeat", {"seq": 1})
        buffer.enqueue("heartbeat", {"seq": 2})
        buffer.enqueue("heartbeat", {"seq": 3})
        buffer.enqueue("heartbeat", {"seq": 4})
        pending = buffer.get_pending(limit=10)
        assert len(pending) <= 3, f"expected <=3, got {len(pending)}"
        seqs = [e["data"]["seq"] for e in pending]
        assert 1 not in seqs, "oldest event should have been pruned"
        assert 4 in seqs

    def test_prune_expired(self, buffer):
        old_ts = "2020-01-01T00:00:00+00:00"
        buffer._conn.execute(
            "INSERT INTO event_buffer (event_type, data, created_at) VALUES (?, ?, ?)",
            ("heartbeat", json.dumps({"test": True}), old_ts),
        )
        buffer._conn.commit()
        buffer._prune()
        assert buffer.count_pending() == 0

    def test_persistent_across_buffers(self):
        """Events survive buffer close and reopen."""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_events.db")
        eb = EventBuffer(db_path)
        eb.enqueue("heartbeat", {"persistent": True})
        eb.close()
        eb2 = EventBuffer(db_path)
        assert eb2.count_pending() == 1
        pending = eb2.get_pending()
        assert pending[0]["data"]["persistent"] is True
        eb2.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_multiple_event_types(self, buffer):
        buffer.enqueue("heartbeat", {"type": "hb"})
        buffer.enqueue("browser_activity", {"url": "https://example.com"})
        buffer.enqueue("editor_activity", {"file": "main.py"})
        buffer.enqueue("metrics", {"cpu": 50})
        assert buffer.count_pending() == 4
        pending = buffer.get_pending(limit=4)
        types = [e["event_type"] for e in pending]
        assert types == ["heartbeat", "browser_activity", "editor_activity", "metrics"]

    def test_get_pending_respects_limit(self, buffer):
        for i in range(10):
            buffer.enqueue("heartbeat", {"seq": i})
        pending = buffer.get_pending(limit=3)
        assert len(pending) == 3
        assert pending[0]["data"]["seq"] == 0
        assert pending[2]["data"]["seq"] == 2

    def test_empty_replay(self, buffer):
        count = buffer.replay_all(lambda typ, data: True)
        assert count == 0
