import re

import pytest
from starlette.testclient import TestClient

from main import create_app


@pytest.fixture
def notebook_path(tmp_path):
    return tmp_path / "notebook.sqlite3"


@pytest.fixture
def client(notebook_path):
    return TestClient(create_app(notebook_path))


def test_root_leads_to_the_notebook(client):
    response = client.get("/", follow_redirects=False)

    assert response.is_redirect
    assert response.headers["location"] == "/entries"


def test_captured_entry_appears_in_the_notebook(client):
    client.post("/entries", data={"text": "¡Qué guay!"})

    response = client.get("/entries")

    assert response.status_code == 200
    assert "¡Qué guay!" in response.text


def test_capture_without_htmx_redirects_back_to_the_notebook(client):
    response = client.post(
        "/entries", data={"text": "vale"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/entries"


def test_notebook_lists_newest_entry_first(client):
    client.post("/entries", data={"text": "first heard"})
    client.post("/entries", data={"text": "second heard"})

    page = client.get("/entries").text

    assert page.index("second heard") < page.index("first heard")


def test_entries_survive_a_server_restart(notebook_path):
    TestClient(create_app(notebook_path)).post("/entries", data={"text": "¡Buen provecho!"})

    restarted = TestClient(create_app(notebook_path))

    assert "¡Buen provecho!" in restarted.get("/entries").text


HTMX = {"HX-Request": "true"}


def test_capture_with_htmx_returns_only_the_new_entry(client):
    client.post("/entries", data={"text": "earlier entry"})

    response = client.post("/entries", data={"text": "vale"}, headers=HTMX)

    assert response.status_code == 200
    assert "vale" in response.text
    assert "earlier entry" not in response.text
    assert "<form" not in response.text
    assert "HX-Request" in response.headers["vary"]


@pytest.mark.parametrize("blank", ["", "   \n\t "])
def test_blank_capture_is_rejected_and_adds_nothing(client, blank):
    client.post("/entries", data={"text": "earlier entry"})

    response = client.post("/entries", data={"text": blank}, follow_redirects=False)

    assert response.status_code == 422
    assert "Type something to capture" in response.text
    assert client.get("/entries").text.count("<li>") == 1


def test_a_fresh_capture_box_shows_no_error(client):
    page = client.get("/entries").text

    assert "Type something to capture" not in page


def test_rejected_capture_keeps_what_was_typed(client):
    response = client.post("/entries", data={"text": "  \n  "})

    assert '<textarea name="text"' in response.text
    assert "  \n  </textarea>" in response.text


def test_blank_capture_with_htmx_swaps_back_only_the_capture_box(client):
    response = client.post("/entries", data={"text": "   "}, headers=HTMX)

    assert response.status_code == 422
    assert "<html" not in response.text
    assert '<form id="capture"' in response.text
    assert "Type something to capture" in response.text
    assert "   </textarea>" in response.text
    assert response.headers["HX-Retarget"] == "#capture"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert "HX-Request" in response.headers["vary"]


HOSTILE = '<img src=x onerror="alert(1)"><b hx-get="/entries" hx-trigger="load">hi</b>'


def test_entry_text_with_html_and_htmx_attributes_is_rendered_inert(client):
    client.post("/entries", data={"text": HOSTILE})

    page = client.get("/entries").text

    assert "<img" not in page
    assert "<b hx-get" not in page
    assert "&lt;b hx-get=&#34;/entries&#34;" in page
    notebook_list = page[page.index('<ul id="entries"') :]
    assert notebook_list.startswith('<ul id="entries" hx-disable')


def test_htmx_fragment_escapes_entry_text(client):
    response = client.post("/entries", data={"text": HOSTILE}, headers=HTMX)

    assert "<b hx-get" not in response.text
    assert "&lt;b hx-get" in response.text


def capture_form(page: str) -> str:
    start = page.index('<form id="capture"')
    return page[start : page.index("</form>", start)]


def test_capture_box_with_htmx_puts_the_new_entry_at_the_top_of_the_notebook(client):
    form = capture_form(client.get("/entries").text)

    assert 'hx-post="/entries"' in form
    assert 'hx-target="#entries"' in form
    assert 'hx-swap="afterbegin"' in form


def test_capture_box_clears_and_keeps_focus_after_a_successful_capture(client):
    form = capture_form(client.get("/entries").text)

    assert "autofocus" in form
    after_request = re.search(r'hx-on::after-request="([^"]*)"', form)
    assert after_request
    script = after_request.group(1)
    assert "event.detail.successful" in script  # a rejected capture keeps its text
    assert "this.reset()" in script
    assert ".error')?.remove()" in script
    assert "this.elements.text.focus()" in script


def test_notebook_page_varies_on_htmx_request(client):
    response = client.get("/entries")

    assert "HX-Request" in response.headers["vary"]
