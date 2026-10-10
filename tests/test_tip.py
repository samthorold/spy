import re
import sqlite3
from contextlib import closing
from pathlib import Path

from starlette.testclient import TestClient

from tests.support import HOSTILE, HTMX, WAITING, HtmxReach, capture, field, search

TIP_TEXT = "in Spain they say vale where Latin America says bueno"


def test_an_entry_marked_as_a_tip_shows_as_a_tip_with_its_text_and_context(client: TestClient):
    edit = capture(client, TIP_TEXT)

    response = client.post(
        edit,
        data={"kind": "tip", "spanish": TIP_TEXT, "meaning": "", "context": "from class"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    page = client.get("/entries").text
    assert TIP_TEXT in page
    assert "from class" in page
    assert '<p class="kind">Tip</p>' in page
    assert WAITING not in page


def chosen_kind(page: str) -> str:
    """Which kind the form's kind radio has selected."""
    radios = re.findall(r'<input type="radio" name="kind"[^>]*>', page)
    assert {search(r'value="(\w+)"', r).group(1) for r in radios} == {"expression", "tip"}
    checked = [search(r'value="(\w+)"', r).group(1) for r in radios if " checked" in r]
    assert len(checked) == 1
    return checked[0]


def test_an_entry_is_an_expression_until_marked_as_a_tip(client: TestClient):
    edit = capture(client, TIP_TEXT)
    assert chosen_kind(client.get(edit).text) == "expression"

    client.post(edit, data={"kind": "tip", "spanish": TIP_TEXT, "meaning": "", "context": ""})

    assert chosen_kind(client.get(edit).text) == "tip"


def test_a_notebook_kept_before_tips_existed_holds_expressions_that_can_become_tips(client: TestClient, notebook_path: Path):
    with closing(sqlite3.connect(notebook_path)) as db, db:
        db.execute(
            "CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,"
            " spanish TEXT, meaning TEXT NOT NULL DEFAULT '', context TEXT NOT NULL DEFAULT '')"
        )
        db.execute("INSERT INTO entries (text) VALUES (?)", (TIP_TEXT,))

    assert WAITING in client.get("/entries").text
    client.post("/entries/1/edit", data={"kind": "tip", "spanish": "", "meaning": "", "context": ""})
    assert WAITING not in client.get("/entries").text


def test_a_tip_hides_its_spanish_and_meaning_until_marked_an_expression_again(client: TestClient):
    edit = capture(client, "vale")
    client.post(edit, data={"kind": "tip", "spanish": "¡Vale!", "meaning": "OK", "context": "Spain"})

    page = client.get("/entries").text
    assert "¡Vale!" not in page
    assert "OK" not in page

    form = client.get(edit).text
    client.post(
        edit,
        data={"kind": "expression", **{name: field(form, name) for name in ("spanish", "meaning", "context")}},
    )

    page = client.get("/entries").text
    assert "¡Vale!" in page
    assert "OK" in page


def test_with_htmx_an_entry_is_marked_as_a_tip_inline(client: TestClient):
    edit = capture(client, TIP_TEXT)
    assert chosen_kind(client.get(edit, headers=HTMX).text) == "expression"

    row = client.post(edit, data={"kind": "tip", "spanish": TIP_TEXT, "meaning": "", "context": "from class"}, headers=HTMX)

    assert row.text.lstrip().startswith("<li")
    assert '<p class="kind">Tip</p>' in row.text
    assert TIP_TEXT in row.text
    assert "from class" in row.text
    assert WAITING not in row.text
    assert chosen_kind(client.get(edit, headers=HTMX).text) == "tip"


def test_a_tips_text_is_rendered_inert(client: TestClient):
    edit = capture(client, HOSTILE)

    row = client.post(edit, data={"kind": "tip", "spanish": "", "meaning": "", "context": HOSTILE}, headers=HTMX).text

    for html in (client.get("/entries").text, row):
        assert '<p class="kind">Tip</p>' in html
        assert "<b hx-get" not in html
        assert not [text for text in HtmxReach(html).live_text if "hx-get" in text]
