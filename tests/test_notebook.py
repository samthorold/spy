"""The model on its own: what depends on the time is told the time, so these tests pick it."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.notebook import Entry, Kind, Notebook, Order, Window

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


@pytest.fixture
def notebook(tmp_path: Path) -> Notebook:
    return Notebook(tmp_path / "notebook.sqlite3")


def capture(notebook: Notebook, text: str, at: datetime) -> Entry:
    entry = Entry(text=text)
    assert notebook.capture(entry, at=at)
    return entry


def expression(notebook: Notebook, spanish: str, meaning: str, at: datetime) -> None:
    """Capture an Expression `at` a time and give it its Meaning."""
    entry = capture(notebook, spanish, at)
    entry.spanish, entry.meaning = spanish, meaning
    notebook.enrich(entry)


def tip(notebook: Notebook, text: str, at: datetime) -> None:
    entry = capture(notebook, text, at)
    entry.kind = Kind.TIP
    notebook.enrich(entry)


def headlines(entries: list[Entry]) -> list[str]:
    return [entry.headline for entry in entries]


def test_a_capture_keeps_the_time_it_was_captured_at(notebook: Notebook):
    entry = capture(notebook, "vale", NOW)

    assert entry.captured_at == NOW
    assert Notebook(notebook.path).entries()[0].captured_at == NOW


def test_a_week_recap_goes_over_only_the_last_seven_days_and_all_goes_over_everything(notebook: Notebook):
    expression(notebook, "vale", "OK", NOW - 12 * DAY)
    expression(notebook, "¡Qué guay!", "how cool", NOW - 2 * DAY)

    assert headlines(notebook.recap(Window.WEEK, Order.NEWEST, now=NOW)) == ["¡Qué guay!"]
    assert headlines(notebook.recap(Window.ALL, Order.NEWEST, now=NOW)) == ["¡Qué guay!", "vale"]


def test_a_week_reaches_back_exactly_seven_days_from_now(notebook: Notebook):
    expression(notebook, "vale", "OK", NOW)

    assert headlines(notebook.recap(Window.WEEK, now=NOW + 7 * DAY)) == ["vale"]
    assert notebook.recap(Window.WEEK, now=NOW + 7 * DAY + timedelta(seconds=1)) == []


def test_a_week_with_nothing_captured_in_it_has_nothing_to_recap(notebook: Notebook):
    expression(notebook, "vale", "OK", NOW - 30 * DAY)
    capture(notebook, "¿Mande?", NOW)  # in the week, but still waiting for its Meaning

    assert notebook.recap(Window.WEEK, now=NOW) == []


def test_only_expressions_captured_in_the_window_are_waiting_and_never_tips(notebook: Notebook):
    capture(notebook, "ojalá", NOW - 10 * DAY)
    capture(notebook, "¡Qué guay!", NOW)
    tip(notebook, "in Spain they say vale where Latin America says bueno", NOW)
    expression(notebook, "vale", "OK", NOW)

    assert headlines(notebook.waiting(Window.WEEK, now=NOW)) == ["¡Qué guay!"]
    assert headlines(notebook.waiting(Window.ALL, now=NOW)) == ["¡Qué guay!", "ojalá"]
