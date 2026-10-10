import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from html import unescape

import pytest
from starlette.testclient import TestClient

from main import create_app
from tests.test_enrich import HOSTILE, HtmxReach


@pytest.fixture
def notebook_path(tmp_path):
    return tmp_path / "notebook.sqlite3"


@pytest.fixture
def client(notebook_path):
    return TestClient(create_app(notebook_path))


def capture(client, text: str) -> str:
    """Capture `text` and return the URL of its edit page."""
    row = client.post("/entries", data={"text": text}, headers={"HX-Request": "true"}).text
    return re.search(r'href="(/entries/\d+/edit)"', row).group(1)


def expression(client, spanish: str, meaning: str, context: str = "") -> None:
    """Capture an Expression and give it its Meaning."""
    edit = capture(client, spanish)
    client.post(edit, data={"spanish": spanish, "meaning": meaning, "context": context})


def card(page: str) -> str:
    """The recap card in `page`."""
    match = re.search(r'<section id="recap-card".*?</section>', page, re.S)
    assert match, "no recap card"
    return match.group(0)


def link(html: str, label: str) -> str:
    """The href of the link labelled `label`."""
    match = re.search(rf'<a href="([^"]*)"[^>]*>{label}</a>', html)
    assert match, f"no {label} link"
    return unescape(match.group(1))


def test_recap_shows_the_spanish_and_reveals_the_meaning_on_request(client):
    expression(client, "¡Buen provecho!", "enjoy your meal")

    prompt = card(client.get("/recap?window=all").text)

    assert "¡Buen provecho!" in prompt
    assert "enjoy your meal" not in prompt

    revealed = card(client.get(link(prompt, "Reveal")).text)

    assert "¡Buen provecho!" in revealed
    assert "enjoy your meal" in revealed


PROMPT = r'<p class="\w+ prompt">(.*?)</p>'


def prompt_of(html: str) -> str:
    """The side a recap card shows first: the Spanish, or the Meaning when recapping Meaning first."""
    return unescape(re.search(PROMPT, card(html), re.S).group(1))


def step_through(client, url: str) -> tuple[list[str], str]:
    """Follow a recap from `url`, revealing and moving on, until it ends. The prompts seen, and the last card."""
    seen = []
    page = client.get(url).text
    while re.search(PROMPT, card(page), re.S):
        seen.append(prompt_of(page))
        assert len(seen) < 50, "the recap never ends"
        page = client.get(link(card(page), "Reveal")).text
        page = client.get(link(card(page), "Next")).text
    return seen, card(page)


def tip(client, text: str) -> None:
    client.post(capture(client, text), data={"kind": "tip", "spanish": "", "meaning": "", "context": ""})


def test_stepping_through_reaches_each_expression_with_a_meaning_once_newest_first_then_ends(client):
    expression(client, "vale", "OK")
    tip(client, "in Spain they say vale where Latin America says bueno")
    expression(client, "¡Qué guay!", "how cool")
    capture(client, "¿Mande?")  # still waiting for its Meaning
    expression(client, "¡Buen provecho!", "enjoy your meal")

    seen, end = step_through(client, "/recap?window=all&order=newest")

    assert seen == ["¡Buen provecho!", "¡Qué guay!", "vale"]
    assert "every Expression" in end


class Clock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def timed_client(notebook_path, clock):
    return TestClient(create_app(notebook_path, clock=clock))


def test_a_week_recap_goes_over_only_the_last_seven_days_and_all_goes_over_everything(timed_client, clock):
    expression(timed_client, "vale", "OK")
    clock.now += timedelta(days=10)
    expression(timed_client, "¡Qué guay!", "how cool")
    clock.now += timedelta(days=2)

    assert step_through(timed_client, "/recap?window=week&order=newest")[0] == ["¡Qué guay!"]
    assert step_through(timed_client, "/recap?window=all&order=newest")[0] == ["¡Qué guay!", "vale"]


def test_expressions_captured_before_capture_times_were_kept_are_recapped_only_over_everything(notebook_path, clock):
    with closing(sqlite3.connect(notebook_path)) as db, db:
        db.execute(
            "CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,"
            " spanish TEXT, meaning TEXT NOT NULL DEFAULT '', context TEXT NOT NULL DEFAULT '',"
            " kind TEXT NOT NULL DEFAULT 'expression')"
        )
        db.execute("INSERT INTO entries (text, spanish, meaning) VALUES ('vale', 'vale', 'OK')")
    client = TestClient(create_app(notebook_path, clock=clock))
    expression(client, "¡Qué guay!", "how cool")

    assert step_through(client, "/recap?window=week&order=newest")[0] == ["¡Qué guay!"]
    assert step_through(client, "/recap?window=all&order=newest")[0] == ["¡Qué guay!", "vale"]


SPANISH = ["uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho"]


def test_a_shuffled_recap_reaches_each_expression_once_in_an_order_its_seed_fixes(client):
    for number, word in enumerate(SPANISH, start=1):
        expression(client, word, str(number))
    newest_first = list(reversed(SPANISH))

    orders = [step_through(client, f"/recap?window=all&order=shuffled&seed={seed}")[0] for seed in range(1, 6)]

    for order in orders:
        assert sorted(order) == sorted(SPANISH)
    assert any(order != newest_first for order in orders)
    assert step_through(client, "/recap?window=all&order=shuffled&seed=3")[0] == orders[2]


def test_a_shuffled_recap_without_a_seed_is_given_one_in_its_url(client):
    expression(client, "vale", "OK")

    response = client.get("/recap?window=all&order=shuffled&direction=meaning", follow_redirects=False)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/recap?")
    assert "window=all" in location
    assert "order=shuffled" in location
    assert "direction=meaning" in location
    assert re.search(r"seed=\d+", location)


def test_an_empty_window_says_so(timed_client, clock):
    expression(timed_client, "vale", "OK")
    clock.now += timedelta(days=30)
    capture(timed_client, "¿Mande?")

    response = timed_client.get("/recap?window=week&order=newest")

    assert response.status_code == 200
    assert "Nothing to recap" in card(response.text)
    assert "Reveal" not in card(response.text)


def chosen(page: str, name: str) -> tuple[set[str], str]:
    """The values the radio group `name` offers, and the one it has selected."""
    radios = re.findall(rf'<input type="radio" name="{name}"[^>]*>', page)
    values = {re.search(r'value="(\w+)"', radio).group(1) for radio in radios}
    checked = [re.search(r'value="(\w+)"', radio).group(1) for radio in radios if " checked" in radio]
    assert len(checked) == 1
    return values, checked[0]


def test_the_notebook_leads_to_a_recap_whose_window_and_order_are_chosen_in_the_url(client):
    expression(client, "vale", "OK")
    recap = link(client.get("/entries").text, "Recap")

    page = client.get(recap).text

    assert '<form method="get" action="/recap"' in page
    assert chosen(page, "window") == ({"week", "all"}, "week")
    assert chosen(page, "order") == ({"newest", "shuffled"}, "newest")

    page = client.get("/recap?window=all&order=shuffled&seed=4").text

    assert chosen(page, "window")[1] == "all"
    assert chosen(page, "order")[1] == "shuffled"
    assert "vale" in card(page)


HTMX = {"HX-Request": "true"}


def test_with_htmx_reveal_and_next_swap_only_the_card_and_keep_the_url(client):
    expression(client, "vale", "OK")
    expression(client, "¡Qué guay!", "how cool")
    prompt = card(client.get("/recap?window=all&order=newest").text)

    for label in ("Reveal", "Next"):
        tag = re.search(rf'<a href="[^"]*"[^>]*>{label}</a>', prompt).group(0)
        assert f'hx-get="{re.search(r'href="([^"]*)"', tag).group(1)}"' in tag
        assert 'hx-target="#recap-card"' in tag
        assert 'hx-swap="outerHTML"' in tag
        assert 'hx-push-url="true"' in tag

    revealed = client.get(link(prompt, "Reveal"), headers=HTMX)

    assert revealed.text.lstrip().startswith('<section id="recap-card"')
    assert "<html" not in revealed.text
    assert "how cool" in revealed.text
    assert "HX-Request" in revealed.headers["vary"]

    following = client.get(link(revealed.text, "Next"), headers=HTMX).text

    assert following.lstrip().startswith('<section id="recap-card"')
    assert "vale" in following


def test_with_htmx_a_meaning_first_recap_swaps_only_the_card_and_stays_meaning_first(client):
    expression(client, "vale", "OK")
    expression(client, "¡Qué guay!", "how cool")
    prompt = card(client.get("/recap?window=all&order=newest&direction=meaning").text)

    revealed = client.get(link(prompt, "Reveal"), headers=HTMX).text

    assert revealed.lstrip().startswith('<section id="recap-card"')
    assert "<html" not in revealed
    assert prompt_of(revealed) == "how cool"
    assert "¡Qué guay!" in revealed

    following = client.get(link(revealed, "Next"), headers=HTMX).text

    assert following.lstrip().startswith('<section id="recap-card"')
    assert prompt_of(following) == "OK"
    assert "vale" not in following


def test_a_boosted_or_history_restoring_recap_request_gets_the_whole_page(client):
    """htmx restoring a pushed URL it has no snapshot of sends HX-Request too, and swaps the answer into the body."""
    expression(client, "vale", "OK")

    for headers in ({**HTMX, "HX-Boosted": "true"}, {**HTMX, "HX-History-Restore-Request": "true"}):
        response = client.get("/recap?window=all&order=newest&at=1&reveal=1", headers=headers)

        assert "<html" in response.text
        assert "OK" in card(response.text)
    assert "HX-History-Restore-Request" in response.headers["vary"]


def test_an_expression_whose_spanish_was_cleared_is_prompted_by_its_captured_text(client):
    edit = capture(client, "que guay")
    client.post(edit, data={"spanish": "", "meaning": "how cool", "context": ""})

    assert step_through(client, "/recap?window=all&order=newest")[0] == ["que guay"]

    meaning_first = card(client.get("/recap?window=all&order=newest&direction=meaning").text)
    revealed = card(client.get(link(meaning_first, "Reveal")).text)

    assert "que guay" not in meaning_first
    assert "que guay" in revealed


def test_the_cards_free_text_is_inert_while_its_controls_stay_live(client):
    expression(client, HOSTILE, HOSTILE + " means")

    for direction in ("spanish", "meaning"):
        prompt = client.get(f"/recap?window=all&order=newest&direction={direction}").text
        revealed = client.get(link(card(prompt), "Reveal"), headers=HTMX).text

        for html in (prompt, revealed):
            assert "<b hx-get" not in html
            assert not [text for text in HtmxReach(html).live_text if "hx-get" in text]
        assert any("reveal=1" in control for control in HtmxReach(prompt).live_controls)
        assert any("at=2" in control for control in HtmxReach(revealed).live_controls)


def test_a_recap_url_with_unknown_choices_falls_back_to_the_defaults(client):
    expression(client, "vale", "OK")

    page = client.get("/recap?window=year&order=sideways&direction=backwards&at=first")

    assert page.status_code == 200
    assert chosen(page.text, "window")[1] == "week"
    assert chosen(page.text, "order")[1] == "newest"
    assert chosen(page.text, "direction")[1] == "spanish"
    assert prompt_of(page.text) == "vale"

    reseeded = client.get("/recap?window=all&order=shuffled&seed=lucky", follow_redirects=False)

    assert reseeded.status_code == 303
    assert re.search(r"seed=\d+", reseeded.headers["location"])


def test_a_meaning_first_recap_shows_the_meaning_and_reveals_the_spanish_on_request(client):
    expression(client, "¡Buen provecho!", "enjoy your meal")

    prompt = card(client.get("/recap?window=all&direction=meaning").text)

    assert "enjoy your meal" in prompt
    assert "¡Buen provecho!" not in prompt

    revealed = card(client.get(link(prompt, "Reveal")).text)

    assert "enjoy your meal" in revealed
    assert "¡Buen provecho!" in revealed


def test_a_meaning_first_recap_goes_over_the_same_expressions_in_the_same_order(timed_client, clock):
    expression(timed_client, "vale", "OK")
    clock.now += timedelta(days=10)
    tip(timed_client, "in Spain they say vale where Latin America says bueno")
    expression(timed_client, "¡Qué guay!", "how cool")
    capture(timed_client, "¿Mande?")  # still waiting for its Meaning
    expression(timed_client, "¡Buen provecho!", "enjoy your meal")

    assert step_through(timed_client, "/recap?window=week&order=newest&direction=meaning")[0] == [
        "enjoy your meal",
        "how cool",
    ]
    assert step_through(timed_client, "/recap?window=all&order=newest&direction=meaning")[0] == [
        "enjoy your meal",
        "how cool",
        "OK",
    ]
    meanings = {"vale": "OK", "¡Qué guay!": "how cool", "¡Buen provecho!": "enjoy your meal"}
    for seed in range(1, 4):
        spanish_first = step_through(timed_client, f"/recap?window=all&order=shuffled&seed={seed}")[0]
        meaning_first = step_through(timed_client, f"/recap?window=all&order=shuffled&seed={seed}&direction=meaning")[0]
        assert meaning_first == [meanings[spanish] for spanish in spanish_first]


def test_the_direction_is_chosen_with_the_window_and_order_and_survives_a_refresh(client):
    expression(client, "vale", "OK")

    assert chosen(client.get("/recap").text, "direction") == ({"spanish", "meaning"}, "spanish")

    page = client.get("/recap?window=all&order=newest&direction=meaning").text
    revealed_url = link(card(page), "Reveal")
    refreshed = client.get(revealed_url).text

    assert "direction=meaning" in revealed_url
    assert chosen(refreshed, "direction")[1] == "meaning"
    assert prompt_of(refreshed) == "OK"
    assert "direction=meaning" in link(card(refreshed), "Next")
