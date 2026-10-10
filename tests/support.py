"""Helpers shared by the end-to-end tests: how a browser drives the app and how to read what it gets back."""

import re
from html.parser import HTMLParser

HTMX = {"HX-Request": "true"}
HOSTILE = '<img src=x onerror="alert(1)"><b hx-get="/entries" hx-trigger="load">hi</b>'
WAITING = "Waiting for a meaning"


def capture(client, text: str) -> str:
    """Capture `text` and return the URL of its edit page, as linked from the notebook."""
    client.post("/entries", data={"text": text})
    page = client.get("/entries").text
    return re.findall(r'href="(/entries/\d+/edit)"', page)[0]


def field(page: str, name: str) -> str:
    """What the textarea called `name` holds."""
    match = re.search(rf'<textarea name="{name}"[^>]*>\n?(.*?)</textarea>', page, re.S)
    assert match, f"no {name} field"
    return match.group(1)


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
            self.live_controls.append(self.get_starttag_text() or "")
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
