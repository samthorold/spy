"""The notebook: the learner's Entries, and how they get in.

Knows nothing of HTTP or HTML. Language follows CONTEXT.md.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from attrs import define


@define
class Entry:
    """Anything the learner notes down, in whatever words they typed."""

    text: str

    @property
    def errors(self) -> dict[str, str]:
        """What stops this Entry going into the notebook, by field."""
        if not self.text.strip():
            return {"text": "Type something to capture."}
        return {}


class Notebook:
    """One learner's notebook, kept in a SQLite file at `path`."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def capture(self, entry: Entry) -> bool:
        """Note `entry` down, exactly as typed. False if it has errors."""
        if entry.errors:
            return False
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO entries (text) VALUES (?)", (entry.text,))
        return True

    def entries(self) -> list[Entry]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT text FROM entries ORDER BY id DESC").fetchall()
        return [Entry(text=text) for (text,) in rows]

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " text TEXT NOT NULL)"
        )
        return db
