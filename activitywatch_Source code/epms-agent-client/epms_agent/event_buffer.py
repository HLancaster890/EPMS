"""
Event buffer for offline resilience.
SQLite-backed persistent queue that holds events during connection loss
and replays them when the WebSocket reconnects. Events survive agent restarts.

Schema:
  event_buffer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,          -- "heartbeat", "browser_activity", "editor_activity", "metrics"
    data        TEXT NOT NULL,          -- JSON-serialized payload
    created_at  TEXT NOT NULL,          -- ISO-8601 timestamp
    sent_count  INTEGER DEFAULT 0,     -- number of times we've tried to send
    last_error  TEXT,                   -- last error message if send failed
    acked       INTEGER DEFAULT 0      -- 1 = server acknowledged
  )
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)

# Maximum age for buffered events before auto-purge
DEFAULT_MAX_EVENTS = 10000
DEFAULT_MAX_AGE_DAYS = 7


class EventBuffer:
    """Thread-safe, SQLite-backed persistent event buffer."""

    def __init__(
        self,
        db_path: str,
        max_events: int = DEFAULT_MAX_EVENTS,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ):
        self._max_events = max_events
        self._max_age_seconds = max_age_days * 86400
        self._lock = threading.Lock()

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._init_db()
        logger.debug(f"EventBuffer initialized: {db_path}")

    def _init_db(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_buffer (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                data        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                sent_count  INTEGER DEFAULT 0,
                last_error  TEXT,
                acked       INTEGER DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_buffer_created ON event_buffer(created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_buffer_acked ON event_buffer(acked)"
        )
        self._conn.commit()

    def enqueue(self, event_type: str, data: dict) -> int:
        """Add an event to the buffer. Returns the event ID."""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            cur = self._conn.execute(
                "INSERT INTO event_buffer (event_type, data, created_at) VALUES (?, ?, ?)",
                (event_type, json.dumps(data, default=str), now),
            )
            self._conn.commit()
            self._prune()
            return cur.lastrowid

    def get_pending(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return unacknowledged events in FIFO order, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, event_type, data, created_at, sent_count, last_error "
                "FROM event_buffer WHERE acked = 0 "
                "ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "event_type": row[1],
                    "data": json.loads(row[2]),
                    "created_at": row[3],
                    "sent_count": row[4],
                    "last_error": row[5],
                }
                for row in rows
            ]

    def mark_sent(self, event_id: int, error: Optional[str] = None):
        """Increment the send counter and optionally record an error."""
        with self._lock:
            if error:
                self._conn.execute(
                    "UPDATE event_buffer SET sent_count = sent_count + 1, last_error = ? WHERE id = ?",
                    (error, event_id),
                )
            else:
                self._conn.execute(
                    "UPDATE event_buffer SET sent_count = sent_count + 1 WHERE id = ?",
                    (event_id,),
                )
            self._conn.commit()

    def ack(self, event_id: int):
        """Mark event as acknowledged and remove it from the buffer."""
        with self._lock:
            self._conn.execute("DELETE FROM event_buffer WHERE id = ?", (event_id,))
            self._conn.commit()

    def ack_all(self):
        """Clear all acknowledged events (fast path for bulk replay)."""
        with self._lock:
            self._conn.execute("DELETE FROM event_buffer WHERE acked = 1")
            self._conn.commit()

    def count_pending(self) -> int:
        """Return number of unacknowledged events."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM event_buffer WHERE acked = 0"
            ).fetchone()
            return row[0] if row else 0

    def clear(self):
        """Remove ALL events from the buffer (use with care)."""
        with self._lock:
            self._conn.execute("DELETE FROM event_buffer")
            self._conn.commit()

    def replay_all(self, send_fn: Callable[[str, dict], bool]) -> int:
        """Replay all pending events via the given send callback.

        The callback receives (event_type, data_dict) and should return True
        on success. Successfully replayed events are removed from the buffer.

        Returns the number of events successfully replayed.
        """
        events = self.get_pending(limit=self._max_events)
        if not events:
            return 0

        success_count = 0
        for event in events:
            try:
                ok = send_fn(event["event_type"], event["data"])
                if ok:
                    self.ack(event["id"])
                    success_count += 1
                else:
                    self.mark_sent(event["id"], "send_fn returned False")
            except Exception as e:
                self.mark_sent(event["id"], str(e))
                logger.debug(f"Replay failed for event {event['id']}: {e}")

        if success_count:
            logger.info(
                f"Replayed {success_count}/{len(events)} buffered events "
                f"({self.count_pending()} remaining)"
            )
        return success_count

    def _prune(self):
        """Remove oldest events when over capacity or past max age."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM event_buffer"
        ).fetchone()[0]

        if count > self._max_events:
            excess = count - self._max_events
            self._conn.execute(
                "DELETE FROM event_buffer WHERE id IN "
                "(SELECT id FROM event_buffer ORDER BY id ASC LIMIT ?)",
                (excess,),
            )
            logger.debug(f"Pruned {excess} oldest events (buffer over capacity)")

        cutoff = (
            datetime.now(timezone.utc).timestamp() - self._max_age_seconds
        )
        deleted = self._conn.execute(
            "DELETE FROM event_buffer WHERE created_at < ?",
            (datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat(),),
        ).rowcount
        if deleted:
            logger.debug(f"Pruned {deleted} expired events")

    def close(self):
        """Close the database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
