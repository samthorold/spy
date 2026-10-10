import os
from pathlib import Path

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

from notebook import Entry, Notebook

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
        headers={"Vary": "HX-Request, HX-Boosted", **(headers or {})},
    )


def is_htmx(request: Request) -> bool:
    """Whether to answer with a fragment. A boosted link or form (hx-boost) wants a whole page."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Boosted") != "true"
    )


def create_app(notebook_path: Path | str) -> Starlette:
    notebook = Notebook(notebook_path)

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
        notebook.enrich(entry)
        if is_htmx(request):
            return render("_entry.html", entry=entry)
        return RedirectResponse("/entries", status_code=303)

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
            Mount("/static", StaticFiles(directory=HERE / "static")),
        ],
    )


app = create_app(os.environ.get("SPY_NOTEBOOK", DEFAULT_NOTEBOOK_PATH))
