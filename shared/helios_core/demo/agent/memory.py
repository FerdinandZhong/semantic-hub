"""Release-scoped audit memory. Past answers never become query evidence."""
import json
import sqlite3
from datetime import datetime, timezone


class Memory:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'turns.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, created TEXT, release TEXT, snapshot TEXT, question TEXT, outcome TEXT, trace TEXT)')

    def record(self, turn, release, snapshot, question, response, trace):
        # Store checked outcomes and tool summaries, never credentials or raw model reasoning.
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('INSERT INTO turns VALUES (?, ?, ?, ?, ?, ?, ?)', (turn,
                datetime.now(timezone.utc).isoformat(), release, snapshot, question,
                response['status'], json.dumps(trace, ensure_ascii=False)))
            db.execute('DELETE FROM turns WHERE id NOT IN (SELECT id FROM turns ORDER BY created DESC LIMIT 500)')
