import os
import random
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlencode

from jinja2 import (
    Environment as TemplateEnvironment,
    FileSystemLoader as TemplateLoader,
    select_autoescape,
)
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from notebook import Entry, Kind, Notebook, Order, Window

HERE = Path(__file__).parent
APP_DEBUG = bool(os.environ.get("DEBUG", 0))
DEFAULT_NOTEBOOK_PATH = HERE / "data" / "notebook.sqlite3"


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

    A boosted link or form (hx-boost) wants a whole page, and so does htmx restoring a pushed URL from the server.
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


def create_app(notebook_path: Path | str, clock: Callable[[], datetime] | None = None) -> Starlette:
    notebook = Notebook(notebook_path, clock) if clock else Notebook(notebook_path)

    async def list_entries(request: Request):
        return render("entries.html", entries=notebook.entries(), draft=None)

    async def create_entry(request: Request):
        form = await request.form()
        entry = Entry(text=str(form.get("text", "")))
        if not notebook.capture(entry):
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

    def entry_or_404(request: Request) -> Entry:
        entry = notebook.entry(request.path_params["id"])
        if entry is None:
            raise HTTPException(404)
        return entry

    async def show_entry(request: Request):
        entry = entry_or_404(request)
        if is_htmx(request):
            return render("_entry.html", entry=entry)
        # An Entry has no page of its own yet: it is shown in the notebook.
        return RedirectResponse("/entries", status_code=303)

    async def edit_entry(request: Request):
        entry = entry_or_404(request)
        if is_htmx(request):
            return render("_editing.html", entry=entry)
        return render("edit.html", entry=entry)

    async def enrich_entry(request: Request):
        entry = entry_or_404(request)
        form = await request.form()
        entry.spanish = str(form.get("spanish", ""))
        entry.meaning = str(form.get("meaning", ""))
        entry.context = str(form.get("context", ""))
        entry.kind = Kind.TIP if form.get("kind") == Kind.TIP else Kind.EXPRESSION
        notebook.enrich(entry)
        if is_htmx(request):
            return render("_entry.html", entry=entry)
        return RedirectResponse("/entries", status_code=303)

    async def recap(request: Request):
        """One step of a Recap. The URL carries the whole recap: its choices and how far the learner has got.

        `window` and `order` are the learner's choices; `seed` fixes a shuffled order; `at` counts the
        steps from 1; `reveal=1` shows the Meaning. Spanish first is the only direction so far, so the
        URL names none: the other direction will add one.
        """
        params = request.query_params
        window = _choice(Window, params.get("window"), Window.WEEK)
        order = _choice(Order, params.get("order"), Order.NEWEST)
        choices: dict[str, object] = {"window": window, "order": order}
        seed = _number(params.get("seed"))
        if order is Order.SHUFFLED:
            if seed is None:
                # The seed fixes the shuffle, so it goes in the URL: a refresh or a bookmark keeps the same order.
                choices["seed"] = random.randrange(1_000_000)
                return RedirectResponse("/recap?" + urlencode(choices), status_code=303)
            choices["seed"] = seed
        prompts = notebook.recap(window, order, seed or 0)
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
            prompt=prompt,
            at=at,
            total=len(prompts),
            reveal=reveal,
            step=step,
        )

    async def root(request: Request):
        return RedirectResponse("/entries")

    return Starlette(
        debug=APP_DEBUG,
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


app = create_app(os.environ.get("SPY_NOTEBOOK", DEFAULT_NOTEBOOK_PATH))
