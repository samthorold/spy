import re

import pytest
from starlette.testclient import TestClient

from main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "notebook.sqlite3"))


def test_pages_load_the_vendored_htmx(client):
    page = client.get("/entries").text

    script = re.search(r'<script src="(/static/[^"]*htmx[^"]*\.js)"', page)
    assert script, "page does not load htmx from /static"
    served = client.get(script.group(1))
    assert served.status_code == 200
    assert "htmx" in served.text


def test_pages_boost_links_and_forms(client):
    page = client.get("/entries").text

    assert re.search(r'<body[^>]*hx-boost="true"', page)


def test_pages_fit_a_phone_screen(client):
    page = client.get("/entries").text

    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
