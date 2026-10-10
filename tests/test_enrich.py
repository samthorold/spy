import re
import sqlite3
from contextlib import closing
from html.parser import HTMLParser

import pytest
from starlette.testclient import TestClient

from main import create_app


@pytest.fixture
def notebook_path(tmp_path):
    return tmp_path / "notebook.sqlite3"


@pytest.fixture
def client(notebook_path):
    return TestClient(create_app(notebook_path))


def capture(client, text: str) -> str:
    """Capture `text` and return the URL of its edit page, as linked from the notebook."""
    client.post("/entries", data={"text": text})
    page = client.get("/entries").text
    return re.findall(r'href="(/entries/\d+/edit)"', page)[0]


def test_enriched_meaning_appears_in_the_notebook(client):
    edit = capture(client, "¡Buen provecho!")

    response = client.post(
        edit,
        data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/entries"
    assert "enjoy your meal" in client.get("/entries").text


def field(page: str, name: str) -> str:
    """What the textarea called `name` holds."""
    match = re.search(rf'<textarea name="{name}"[^>]*>\n?(.*?)</textarea>', page, re.S)
    assert match, f"no {name} field"
    return match.group(1)


def test_edit_page_prefills_the_spanish_from_the_captured_text(client):
    edit = capture(client, "¡Qué guay!")

    page = client.get(edit)

    assert page.status_code == 200
    assert f'<form method="post" action="{edit}"' in page.text
    assert field(page.text, "spanish") == "¡Qué guay!"
    assert field(page.text, "meaning") == ""
    assert field(page.text, "context") == ""


def test_enrichment_is_kept_and_shown_again_for_the_next_sitting(client):
    edit = capture(client, "que guay")
    client.post(edit, data={"spanish": "¡Qué guay!", "meaning": "", "context": "a friend, informal"})

    page = client.get(edit).text

    assert field(page, "spanish") == "¡Qué guay!"
    assert field(page, "meaning") == ""
    assert field(page, "context") == "a friend, informal"


def test_enrichment_never_alters_the_captured_text(client):
    edit = capture(client, "  que guay\n")
    client.post(edit, data={"spanish": "¡Qué guay!", "meaning": "how cool", "context": ""})

    page = client.get(edit).text

    assert '<blockquote class="captured" hx-disable>  que guay\n</blockquote>' in page


def test_spanish_cleared_on_purpose_stays_cleared(client):
    edit = capture(client, "in Spain they say vale")
    client.post(edit, data={"spanish": "", "meaning": "", "context": "a tip"})

    assert field(client.get(edit).text, "spanish") == ""


def test_notebook_shows_an_entry_by_its_enriched_spanish_with_its_context(client):
    edit = capture(client, "que guay")
    client.post(edit, data={"spanish": "¡Qué guay!", "meaning": "how cool", "context": "a friend, informal"})

    page = client.get("/entries").text

    assert "¡Qué guay!" in page
    assert "how cool" in page
    assert "a friend, informal" in page
    assert "que guay" not in page


WAITING = "Waiting for a meaning"


def test_entry_without_a_meaning_is_marked_waiting_until_one_is_added(client):
    edit = capture(client, "¡Buen provecho!")
    assert WAITING in client.get("/entries").text

    client.post(edit, data={"spanish": "¡Buen provecho!", "meaning": "   ", "context": "said at lunch"})
    assert WAITING in client.get("/entries").text

    client.post(edit, data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""})
    assert WAITING not in client.get("/entries").text


HTMX = {"HX-Request": "true"}
HOSTILE = '<img src=x onerror="alert(1)"><b hx-get="/entries" hx-trigger="load">hi</b>'


def test_with_htmx_enrich_swaps_the_row_for_its_edit_form(client):
    edit = capture(client, "¡Qué guay!")
    page = client.get("/entries").text
    link = re.search(rf'<a href="{edit}"[^>]*>', page).group(0)
    assert f'hx-get="{edit}"' in link
    assert 'hx-target="closest li"' in link
    assert 'hx-swap="outerHTML"' in link

    response = client.get(edit, headers=HTMX)

    assert response.status_code == 200
    assert "<html" not in response.text
    assert response.text.lstrip().startswith("<li")
    assert field(response.text, "spanish") == "¡Qué guay!"
    form = re.search(r"<form[^>]*>", response.text).group(0)
    assert f'hx-post="{edit}"' in form
    assert 'hx-target="closest li"' in form
    assert 'hx-swap="outerHTML"' in form
    assert "HX-Request" in response.headers["vary"]


def test_an_entry_captured_with_htmx_can_be_enriched_straight_away(client):
    capture(client, "earlier entry")

    row = client.post("/entries", data={"text": "vale"}, headers=HTMX).text

    assert 'hx-get="/entries/2/edit"' in row


def test_with_htmx_saving_swaps_back_only_that_entrys_row(client):
    capture(client, "another entry")
    edit = capture(client, "¡Buen provecho!")

    response = client.post(
        edit, data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""}, headers=HTMX
    )

    assert response.status_code == 200
    assert response.text.lstrip().startswith("<li")
    assert response.text.count("<li") == 1
    assert "enjoy your meal" in response.text
    assert "another entry" not in response.text
    assert "<form" not in response.text
    assert "HX-Request" in response.headers["vary"]


def test_with_htmx_cancel_swaps_the_row_back_unchanged(client):
    edit = capture(client, "¡Qué guay!")
    entry_url = edit.removesuffix("/edit")
    inline_form = client.get(edit, headers=HTMX).text
    cancel = re.search(r'<a href="/entries"[^>]*>Cancel</a>', inline_form).group(0)
    assert f'hx-get="{entry_url}"' in cancel
    assert 'hx-target="closest li"' in cancel
    assert 'hx-swap="outerHTML"' in cancel

    response = client.get(entry_url, headers=HTMX)

    assert response.status_code == 200
    assert response.text.lstrip().startswith("<li")
    assert "¡Qué guay!" in response.text
    assert "<form" not in response.text
    assert "HX-Request" in response.headers["vary"]


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class HtmxReach(HTMLParser):
    """Which text and which htmx-driven elements htmx would process, i.e. sit outside any hx-disable."""

    def __init__(self, page: str):
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.live_text: list[str] = []
        self.live_controls: list[str] = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        names = {name for name, _ in attrs}
        disabled = "hx-disable" in names or (self.stack and self.stack[-1][1])
        if not disabled and any(name.startswith("hx-") for name in names):
            self.live_controls.append(self.get_starttag_text())
        if tag not in VOID:
            self.stack.append((tag, bool(disabled)))

    def handle_endtag(self, tag):
        while self.stack and self.stack.pop()[0] != tag:
            pass

    def handle_data(self, data):
        inside = self.stack[-1] if self.stack else ("", False)
        # Textarea content is raw text to the browser, never markup, so it is inert anyway.
        if not inside[1] and inside[0] != "textarea":
            self.live_text.append(data)


def test_enriched_fields_are_rendered_inert_while_the_row_controls_stay_live(client):
    edit = capture(client, HOSTILE)
    enrichment = {"spanish": HOSTILE + " es", "meaning": HOSTILE + " means", "context": HOSTILE + " ctx"}
    saved_row = client.post(edit, data=enrichment, headers=HTMX).text

    for html in (client.get("/entries").text, saved_row, client.get(edit).text, client.get(edit, headers=HTMX).text):
        assert "<b hx-get" not in html
        assert "<img" not in html
        reach = HtmxReach(html)
        assert not [text for text in reach.live_text if "hx-get" in text]

    page = HtmxReach(client.get("/entries").text)
    assert any(f'hx-get="{edit}"' in control for control in page.live_controls)
    form = HtmxReach(client.get(edit, headers=HTMX).text)
    assert any(f'hx-post="{edit}"' in control for control in form.live_controls)


BOOSTED = {"HX-Request": "true", "HX-Boosted": "true"}


def test_boosted_edit_page_behaves_as_without_htmx(client):
    """hx-boost on the body turns the edit page's plain form into an htmx request: it still wants whole pages."""
    edit = capture(client, "vale")

    page = client.get(edit, headers=BOOSTED)
    saved = client.post(
        edit, data={"spanish": "vale", "meaning": "OK", "context": ""}, headers=BOOSTED, follow_redirects=False
    )

    assert "<html" in page.text
    assert saved.status_code == 303
    assert saved.headers["location"] == "/entries"
    assert "HX-Boosted" in page.headers["vary"]


def test_a_notebook_kept_before_enrichment_existed_can_be_enriched(notebook_path):
    with closing(sqlite3.connect(notebook_path)) as db, db:
        db.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL)")
        db.execute("INSERT INTO entries (text) VALUES ('¡Buen provecho!')")
    client = TestClient(create_app(notebook_path))

    assert WAITING in client.get("/entries").text
    client.post("/entries/1/edit", data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""})
    assert "enjoy your meal" in client.get("/entries").text


def test_enriching_an_unknown_entry_is_not_found(client):
    assert client.get("/entries/99/edit").status_code == 404
    assert client.post("/entries/99/edit", data={"meaning": "x"}).status_code == 404
