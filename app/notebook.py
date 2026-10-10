"""The notebook: the learner's Entries, how they get in, and how they are enriched.

Knows nothing of HTTP or HTML. Language follows CONTEXT.md.
"""

import random
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from attrs import define


class Kind(StrEnum):
    """Every Entry is an Expression or a Tip (CONTEXT.md)."""

    EXPRESSION = "expression"
    TIP = "tip"


class Window(StrEnum):
    """How far back a Recap goes, counted from now."""

    WEEK = "week"
    ALL = "all"

    def since(self, now: datetime) -> datetime | None:
        """The earliest capture time inside this window; None when it reaches back to the start."""
        return now - timedelta(days=7) if self is Window.WEEK else None


class Order(StrEnum):
    """The order a Recap goes over its Expressions in."""

    NEWEST = "newest"
    SHUFFLED = "shuffled"


class Direction(StrEnum):
    """Which side of an Expression a Recap shows first: the learner recalls the other."""

    SPANISH = "spanish"
    MEANING = "meaning"


@define
class Entry:
    """Anything the learner notes down, in whatever words they typed.

    `text` is what was captured and never changes. `spanish`, `meaning` and
    `context` come later, through Enrichment. `spanish` is None until the
    learner has given it.

    `kind` is an Expression until the learner marks it a Tip. A Tip has no Spanish/Meaning
    pair; any the learner gave before marking it a Tip is kept, unshown, so
    marking it an Expression again brings them back.

    `captured_at` is when it went into the notebook, or None for an Entry
    captured before the notebook kept that.
    """

    text: str
    id: int | None = None
    spanish: str | None = None
    meaning: str = ""
    context: str = ""
    kind: Kind = Kind.EXPRESSION
    captured_at: datetime | None = None

    @property
    def is_tip(self) -> bool:
        return self.kind is Kind.TIP

    @property
    def proposed_spanish(self) -> str:
        """The Spanish to offer for enrichment: as given, or else the captured text."""
        return self.text if self.spanish is None else self.spanish

    @property
    def headline(self) -> str:
        """What the notebook shows this Entry by: its Spanish once given, else the captured text."""
        return self.spanish or self.text

    @property
    def waiting_for_meaning(self) -> bool:
        """An Expression without a Meaning yet. A Tip has no Meaning to wait for."""
        return not self.is_tip and not self.meaning.strip()

    @property
    def recallable(self) -> bool:
        """An Expression with a Meaning: something a Recap can ask the learner to recall."""
        return not self.is_tip and not self.waiting_for_meaning

    @property
    def errors(self) -> dict[str, str]:
        """What stops this Entry going into the notebook, by field."""
        if not self.text.strip():
            return {"text": "Type something to capture."}
        return {}


_COLUMNS = "id, text, spanish, meaning, context, kind, captured_at"


class Notebook:
    """One learner's notebook, kept in a SQLite file at `path`.

    It never reads the clock: whatever depends on the time is told it (`at`, `now`), so the caller
    decides what "now" is. The file is created on first use, not when a Notebook is made.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def capture(self, entry: Entry, at: datetime) -> bool:
        """Note `entry` down, exactly as typed, as captured `at`. False if it has errors."""
        if entry.errors:
            return False
        with closing(self._connect()) as db, db:
            entry.captured_at = at
            cursor = db.execute(
                "INSERT INTO entries (text, captured_at) VALUES (?, ?)",
                (entry.text, entry.captured_at.isoformat()),
            )
        entry.id = cursor.lastrowid
        return True

    def entries(self) -> list[Entry]:
        with closing(self._connect()) as db:
            rows = db.execute(f"SELECT {_COLUMNS} FROM entries ORDER BY id DESC").fetchall()
        return [_entry(row) for row in rows]

    def recap(
        self, window: Window, order: Order = Order.NEWEST, seed: int = 0, *, now: datetime
    ) -> list[Entry]:
        """The Expressions a Recap over `window`, counted back from `now`, goes over, in the order
        it goes over them.

        A shuffled order is fixed by `seed`, so the same seed goes over the same Expressions in the
        same order.
        """
        prompts = [entry for entry in self._within(window, now) if entry.recallable]
        if order is Order.SHUFFLED:
            random.Random(seed).shuffle(prompts)
        return prompts

    def waiting(self, window: Window, *, now: datetime) -> list[Entry]:
        """The Expressions captured in `window`, counted back from `now`, still waiting for a
        Meaning, newest first.

        Never a Tip.
        """
        return [entry for entry in self._within(window, now) if entry.waiting_for_meaning]

    def _within(self, window: Window, now: datetime) -> list[Entry]:
        """The Entries captured in `window`, counted back from `now`, newest first.

        An Entry captured before the notebook kept capture times is only in the window that reaches
        back to the start.
        """
        since = window.since(now)
        return [
            entry
            for entry in self.entries()
            if since is None or (entry.captured_at is not None and entry.captured_at >= since)
        ]

    def entry(self, entry_id: int) -> Entry | None:
        with closing(self._connect()) as db:
            row = db.execute(f"SELECT {_COLUMNS} FROM entries WHERE id = ?", (entry_id,)).fetchone()
        return _entry(row) if row else None

    def enrich(self, entry: Entry) -> None:
        """Keep what the learner has added to `entry`. Its captured text is left as it was."""
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE entries SET spanish = ?, meaning = ?, context = ?, kind = ? WHERE id = ?",
                (entry.spanish, entry.meaning, entry.context, entry.kind, entry.id),
            )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " text TEXT NOT NULL,"
            " spanish TEXT,"
            " meaning TEXT NOT NULL DEFAULT '',"
            " context TEXT NOT NULL DEFAULT '',"
            " kind TEXT NOT NULL DEFAULT 'expression',"
            " captured_at TEXT)"
        )
        # A notebook kept before Enrichment existed has only id and text.
        columns = {name for _, name, *_ in db.execute("PRAGMA table_info(entries)")}
        if "spanish" not in columns:
            with db:
                db.execute("ALTER TABLE entries ADD COLUMN spanish TEXT")
                db.execute("ALTER TABLE entries ADD COLUMN meaning TEXT NOT NULL DEFAULT ''")
                db.execute("ALTER TABLE entries ADD COLUMN context TEXT NOT NULL DEFAULT ''")
        # A notebook kept before Tips existed holds only Expressions.
        if "kind" not in columns:
            with db:
                db.execute("ALTER TABLE entries ADD COLUMN kind TEXT NOT NULL DEFAULT 'expression'")
        # A notebook kept before capture times were recorded: its Entries stay without one.
        if "captured_at" not in columns:
            with db:
                db.execute("ALTER TABLE entries ADD COLUMN captured_at TEXT")
        return db


def _entry(row: tuple[int, str, str | None, str, str, str, str | None]) -> Entry:
    entry_id, text, spanish, meaning, context, kind, captured_at = row
    return Entry(
        text=text,
        id=entry_id,
        spanish=spanish,
        meaning=meaning,
        context=context,
        kind=Kind(kind),
        captured_at=datetime.fromisoformat(captured_at) if captured_at else None,
    )
