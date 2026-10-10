# Architecture

How the code divides responsibility. Read this before deciding *where* a change belongs.

TODO: not yet written. Today the app is a single Starlette module, `main.py`, with Jinja templates in `templates/` and static files in `static/`. Its domain types (for example `FlashCard`) sit at the top of `main.py`. Record here, as the code grows, which module owns what, the load-bearing invariants, and what must never leak across a boundary.
