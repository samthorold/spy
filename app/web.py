"""The hypermedia layer: routes, thin handlers and rendering. All domain logic is in `app.notebook`.

Configuration comes from the environment, read when it is used (never at import), which is also how
end-to-end tests configure the app:

- `SPY_NOTEBOOK`: the notebook's SQLite file (default `data/notebook.sqlite3`, relative to the
working directory).
- `DEBUG`: Starlette's debug mode.
"""

import os
import random
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from jinja2 import (
    Environment as TemplateEnvironment,
)
from jinja2 import (
    FileSystemLoader as TemplateLoader,
)
from jinja2 import (
    select_autoescape,
)
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.notebook import Direction, Entry, Kind, Notebook, Order, Window

HERE = Path(__file__).parent
DEFAULT_NOTEBOOK_PATH = Path("data") / "notebook.sqlite3"


def open_notebook() -> Notebook:
    """The notebook `SPY_NOTEBOOK` names, read now so each request sees the current setting."""
    return Notebook(os.environ.get("SPY_NOTEBOOK") or DEFAULT_NOTEBOOK_PATH)


def now() -> datetime:
    """The time the notebook is told: captures are stamped with it and recap windows count back from
    it."""
    return datetime.now(UTC)


template_environment = TemplateEnvironment(
    loader=TemplateLoader(HERE / "templates"),
    autoescape=select_autoescape(),
)


def render(
    template_name: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    **context: object,
) -> HTMLResponse:
    template = template_environment.get_template(template_name)
    return HTMLResponse(
        template.render(**context),
        status_code=status_code,
        # Fragment or full page depends on these, so caches must key on them.
        headers={"Vary": "HX-Request, HX-Boosted, HX-History-Restore-Request", **(headers or {})},
    )


def is_htmx(request: Request) -> bool:
    """Whether to answer with a fragment.

    A boosted link or form (hx-boost) wants a whole page, and so does htmx restoring a pushed URL
    from the server.
    """
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Boosted") != "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def _choice[E: StrEnum](choices: type[E], value: str | None, default: E) -> E:
    """The choice `value` names, or `default` when it names none (a hand-edited URL, say)."""
    return choices(value) if value in set(choices) else default


def _number(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def _local(url: str | None) -> str | None:
    """`url` when it is a path on this site, else None, so a crafted `next` cannot send the learner
    elsewhere."""
    if not url or not url.startswith("/") or url.startswith("//") or "\\" in url:
        return None
    parts = urlsplit(url)
    return url if not parts.scheme and not parts.netloc else None


def _entry_or_404(notebook: Notebook, request: Request) -> Entry:
    entry = notebook.entry(request.path_params["id"])
    if entry is None:
        raise HTTPException(404)
    return entry


async def root(request: Request):
    return RedirectResponse("/entries")


async def list_entries(request: Request):
    return render("entries.html", entries=open_notebook().entries(), draft=None)


async def create_entry(request: Request):
    notebook = open_notebook()
    form = await request.form()
    entry = Entry(text=str(form.get("text", "")))
    if not notebook.capture(entry, at=now()):
        if is_htmx(request):
            # The form targets the notebook; send the rejected capture back to the box instead.
            return render(
                "_capture.html",
                status_code=422,
                headers={"HX-Retarget": "#capture", "HX-Reswap": "outerHTML"},
                draft=entry,
            )
        return render(
            "entries.html",
            status_code=422,
            entries=notebook.entries(),
            draft=entry,
        )
    if is_htmx(request):
        return render("_entry.html", entry=entry)
    return RedirectResponse("/entries", status_code=303)


async def show_entry(request: Request):
    entry = _entry_or_404(open_notebook(), request)
    if is_htmx(request):
        return render("_entry.html", entry=entry)
    # An Entry has no page of its own yet: it is shown in the notebook.
    return RedirectResponse("/entries", status_code=303)


async def edit_entry(request: Request):
    entry = _entry_or_404(open_notebook(), request)
    if is_htmx(request):
        return render("_editing.html", entry=entry)
    # Where the learner came from (the recap, say), to go back to once the Entry is enriched.
    return render("edit.html", entry=entry, next=_local(request.query_params.get("next")))


async def enrich_entry(request: Request):
    notebook = open_notebook()
    entry = _entry_or_404(notebook, request)
    form = await request.form()
    next_url = _local(str(form.get("next", ""))) or "/entries"
    entry.spanish = str(form.get("spanish", ""))
    entry.meaning = str(form.get("meaning", ""))
    entry.context = str(form.get("context", ""))
    entry.kind = Kind.TIP if form.get("kind") == Kind.TIP else Kind.EXPRESSION
    notebook.enrich(entry)
    if is_htmx(request):
        return render("_entry.html", entry=entry)
    return RedirectResponse(next_url, status_code=303)


async def recap(request: Request):
    """One step of a Recap. The URL carries the whole recap: its choices and how far the learner has
    got.

    `window`, `order` and `direction` are the learner's choices; `seed` fixes a shuffled order; `at`
    counts the steps from 1; `reveal=1` shows the side being recalled. A URL naming no direction
    (one bookmarked before Meaning first existed) is Spanish first.
    """
    params = request.query_params
    window = _choice(Window, params.get("window"), Window.WEEK)
    order = _choice(Order, params.get("order"), Order.NEWEST)
    direction = _choice(Direction, params.get("direction"), Direction.SPANISH)
    choices: dict[str, object] = {"window": window, "order": order, "direction": direction}
    seed = _number(params.get("seed"))
    if order is Order.SHUFFLED:
        if seed is None:
            # The seed fixes the shuffle, so it goes in the URL: a refresh or a bookmark keeps the
            # same order.
            choices["seed"] = random.randrange(1_000_000)
            return RedirectResponse("/recap?" + urlencode(choices), status_code=303)
        choices["seed"] = seed
    notebook = open_notebook()
    moment = now()
    prompts = notebook.recap(window, order, seed or 0, now=moment)
    at = _number(params.get("at")) or 1
    reveal = params.get("reveal") == "1"
    prompt = prompts[at - 1] if 0 < at <= len(prompts) else None

    def step(**changes: object) -> str:
        """The URL of a step in this recap: the same choices, a different place."""
        return "/recap?" + urlencode({**choices, **changes})

    return render(
        "_recap_card.html" if is_htmx(request) else "recap.html",
        window=window,
        order=order,
        direction=direction,
        prompt=prompt,
        at=at,
        total=len(prompts),
        reveal=reveal,
        step=step,
        waiting=notebook.waiting(window, now=moment),
        # Enriching a waiting Entry comes back to the start of this recap, where it is now a prompt.
        back=step(at=1),
    )


app = Starlette(
    debug=bool(os.environ.get("DEBUG")),
    routes=[
        Route("/", root),
        Route("/entries", list_entries, methods=["GET"]),
        Route("/entries", create_entry, methods=["POST"]),
        Route("/entries/{id:int}", show_entry, methods=["GET"]),
        Route("/entries/{id:int}/edit", edit_entry, methods=["GET"]),
        Route("/entries/{id:int}/edit", enrich_entry, methods=["POST"]),
        Route("/recap", recap, methods=["GET"]),
        Mount("/static", StaticFiles(directory=HERE / "static")),
    ],
)
