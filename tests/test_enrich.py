import sqlite3
from contextlib import closing
from pathlib import Path

from starlette.testclient import TestClient

from tests.support import HOSTILE, HTMX, WAITING, HtmxReach, capture, field, search


def test_enriched_meaning_appears_in_the_notebook(client: TestClient):
    edit = capture(client, "¡Buen provecho!")

    response = client.post(
        edit,
        data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/entries"
    assert "enjoy your meal" in client.get("/entries").text


def test_edit_page_prefills_the_spanish_from_the_captured_text(client: TestClient):
    edit = capture(client, "¡Qué guay!")

    page = client.get(edit)

    assert page.status_code == 200
    assert f'<form method="post" action="{edit}"' in page.text
    assert field(page.text, "spanish") == "¡Qué guay!"
    assert field(page.text, "meaning") == ""
    assert field(page.text, "context") == ""


def test_enrichment_is_kept_and_shown_again_for_the_next_sitting(client: TestClient):
    edit = capture(client, "que guay")
    client.post(
        edit, data={"spanish": "¡Qué guay!", "meaning": "", "context": "a friend, informal"}
    )

    page = client.get(edit).text

    assert field(page, "spanish") == "¡Qué guay!"
    assert field(page, "meaning") == ""
    assert field(page, "context") == "a friend, informal"


def test_enrichment_never_alters_the_captured_text(client: TestClient):
    edit = capture(client, "  que guay\n")
    client.post(edit, data={"spanish": "¡Qué guay!", "meaning": "how cool", "context": ""})

    page = client.get(edit).text

    assert '<blockquote class="captured" hx-disable>  que guay\n</blockquote>' in page


def test_spanish_cleared_on_purpose_stays_cleared(client: TestClient):
    edit = capture(client, "in Spain they say vale")
    client.post(edit, data={"spanish": "", "meaning": "", "context": "a tip"})

    assert field(client.get(edit).text, "spanish") == ""


def test_notebook_shows_an_entry_by_its_enriched_spanish_with_its_context(client: TestClient):
    edit = capture(client, "que guay")
    client.post(
        edit, data={"spanish": "¡Qué guay!", "meaning": "how cool", "context": "a friend, informal"}
    )

    page = client.get("/entries").text

    assert "¡Qué guay!" in page
    assert "how cool" in page
    assert "a friend, informal" in page
    assert "que guay" not in page


def test_entry_without_a_meaning_is_marked_waiting_until_one_is_added(client: TestClient):
    edit = capture(client, "¡Buen provecho!")
    assert WAITING in client.get("/entries").text

    client.post(
        edit, data={"spanish": "¡Buen provecho!", "meaning": "   ", "context": "said at lunch"}
    )
    assert WAITING in client.get("/entries").text

    client.post(
        edit, data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""}
    )
    assert WAITING not in client.get("/entries").text


def test_with_htmx_enrich_swaps_the_row_for_its_edit_form(client: TestClient):
    edit = capture(client, "¡Qué guay!")
    page = client.get("/entries").text
    link = search(rf'<a href="{edit}"[^>]*>', page).group(0)
    assert f'hx-get="{edit}"' in link
    assert 'hx-target="closest li"' in link
    assert 'hx-swap="outerHTML"' in link

    response = client.get(edit, headers=HTMX)

    assert response.status_code == 200
    assert "<html" not in response.text
    assert response.text.lstrip().startswith("<li")
    assert field(response.text, "spanish") == "¡Qué guay!"
    form = search(r"<form[^>]*>", response.text).group(0)
    assert f'hx-post="{edit}"' in form
    assert 'hx-target="closest li"' in form
    assert 'hx-swap="outerHTML"' in form
    assert "HX-Request" in response.headers["vary"]


def test_an_entry_captured_with_htmx_can_be_enriched_straight_away(client: TestClient):
    capture(client, "earlier entry")

    row = client.post("/entries", data={"text": "vale"}, headers=HTMX).text

    assert 'hx-get="/entries/2/edit"' in row


def test_with_htmx_saving_swaps_back_only_that_entrys_row(client: TestClient):
    capture(client, "another entry")
    edit = capture(client, "¡Buen provecho!")

    response = client.post(
        edit,
        data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert response.text.lstrip().startswith("<li")
    assert response.text.count("<li") == 1
    assert "enjoy your meal" in response.text
    assert "another entry" not in response.text
    assert "<form" not in response.text
    assert "HX-Request" in response.headers["vary"]


def test_with_htmx_cancel_swaps_the_row_back_unchanged(client: TestClient):
    edit = capture(client, "¡Qué guay!")
    entry_url = edit.removesuffix("/edit")
    inline_form = client.get(edit, headers=HTMX).text
    cancel = search(r'<a href="/entries"[^>]*>Cancel</a>', inline_form).group(0)
    assert f'hx-get="{entry_url}"' in cancel
    assert 'hx-target="closest li"' in cancel
    assert 'hx-swap="outerHTML"' in cancel

    response = client.get(entry_url, headers=HTMX)

    assert response.status_code == 200
    assert response.text.lstrip().startswith("<li")
    assert "¡Qué guay!" in response.text
    assert "<form" not in response.text
    assert "HX-Request" in response.headers["vary"]


def test_enriched_fields_are_rendered_inert_while_the_row_controls_stay_live(client: TestClient):
    edit = capture(client, HOSTILE)
    enrichment = {
        "spanish": HOSTILE + " es",
        "meaning": HOSTILE + " means",
        "context": HOSTILE + " ctx",
    }
    saved_row = client.post(edit, data=enrichment, headers=HTMX).text

    for html in (
        client.get("/entries").text,
        saved_row,
        client.get(edit).text,
        client.get(edit, headers=HTMX).text,
    ):
        assert "<b hx-get" not in html
        assert "<img" not in html
        reach = HtmxReach(html)
        assert not [text for text in reach.live_text if "hx-get" in text]

    page = HtmxReach(client.get("/entries").text)
    assert any(f'hx-get="{edit}"' in control for control in page.live_controls)
    form = HtmxReach(client.get(edit, headers=HTMX).text)
    assert any(f'hx-post="{edit}"' in control for control in form.live_controls)


BOOSTED = {"HX-Request": "true", "HX-Boosted": "true"}


def test_boosted_edit_page_behaves_as_without_htmx(client: TestClient):
    """hx-boost on the body turns the edit page's plain form into an htmx request: it still wants
    whole pages."""
    edit = capture(client, "vale")

    page = client.get(edit, headers=BOOSTED)
    saved = client.post(
        edit,
        data={"spanish": "vale", "meaning": "OK", "context": ""},
        headers=BOOSTED,
        follow_redirects=False,
    )

    assert "<html" in page.text
    assert saved.status_code == 303
    assert saved.headers["location"] == "/entries"
    assert "HX-Boosted" in page.headers["vary"]


def test_a_notebook_kept_before_enrichment_existed_can_be_enriched(
    client: TestClient, notebook_path: Path
):
    with closing(sqlite3.connect(notebook_path)) as db, db:
        db.execute(
            "CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL)"
        )
        db.execute("INSERT INTO entries (text) VALUES ('¡Buen provecho!')")

    assert WAITING in client.get("/entries").text
    client.post(
        "/entries/1/edit",
        data={"spanish": "¡Buen provecho!", "meaning": "enjoy your meal", "context": ""},
    )
    assert "enjoy your meal" in client.get("/entries").text


def test_enriching_an_unknown_entry_is_not_found(client: TestClient):
    assert client.get("/entries/99/edit").status_code == 404
    assert client.post("/entries/99/edit", data={"meaning": "x"}).status_code == 404
