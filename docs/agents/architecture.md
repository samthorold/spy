# Architecture

How the code divides responsibility. Read this before deciding *where* a change belongs.

## Stack

Starlette serves HTML rendered by Jinja and extended with htmx: a hypermedia-driven application, not a SPA with a JSON API. How to build in that style is in [hypermedia.md](hypermedia.md). Development is test-driven (`/tdd`), through the HTTP interface.

## Today

- **`notebook.py`: the model.** `Entry` (what the learner typed, plus its `errors`) and `Notebook` (`capture(entry)`, `entries()` newest first), stored in a SQLite file. It speaks the language of `CONTEXT.md` and knows nothing of HTTP or HTML.
- **`main.py`: the hypermedia layer.** `create_app(notebook_path)` builds the Starlette app. Handlers are thin: build an `Entry`, call one `Notebook` method, then render or redirect. The module-level `app` reads its notebook path from `SPY_NOTEBOOK` (default `data/notebook.sqlite3`, gitignored). Run it with `uv run uvicorn main:app --reload`.
- **`templates/`**: `base.html` is the layout every page extends (viewport, htmx config, vendored htmx, `hx-boost`). Partials prefixed `_` are fragments shared by full pages and htmx responses: `_entry.html` (one notebook row) and `_capture.html` (the capture box).
- **`static/`**: `style.css` and htmx, vendored and pinned by file name (`htmx-2.0.11.min.js`). To upgrade, download the new `dist/htmx.min.js` from unpkg under its versioned name and update `base.html`.

Invariants:

- Entry text is stored exactly as typed (capture imposes no format). Only blank text is rejected.
- Entry text is rendered only inside `#entries`, which carries `hx-disable`, with Jinja autoescaping on.
- Every rendered response sends `Vary: HX-Request`.
- htmx swaps a `422` (a re-rendered form with its errors) but counts it as a failure (`htmx-config` in `base.html`), so the capture box clears only after a real capture.

## Prototype first, deployed later

The target is a deployed, hosted service (`docs/system-design/boundary.md`), with identity delegated to a provider such as Clerk. The current stage is a prototype that runs on the owner's machine: no auth, no deployment. Don't build sign-in or deployment until asked. Do keep the shape compatible with hosting: state lives server-side, not in the browser, so the phone and laptop will see the same notebook once it is deployed.

Record here, as the code grows, which module owns what, the load-bearing invariants, and what must never leak across a boundary.
