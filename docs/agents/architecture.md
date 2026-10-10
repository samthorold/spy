# Architecture

How the code divides responsibility. Read this before deciding *where* a change belongs.

## Stack

Starlette serves HTML rendered by Jinja and extended with htmx: a hypermedia-driven application, not a SPA with a JSON API. How to build in that style is in [hypermedia.md](hypermedia.md). Development is test-driven (`/tdd`), through the HTTP interface.

## Today

- **`notebook.py`: the model.** `Entry` (the captured `text`, its Enrichment `spanish` / `meaning` / `context`, its `kind` (`Kind.EXPRESSION` by default, or `Kind.TIP`), and what the views ask of it: `errors`, `proposed_spanish`, `headline`, `is_tip`, `waiting_for_meaning`) and `Notebook` (`capture(entry)`, `entries()` newest first, `entry(id)`, `enrich(entry)`), stored in a SQLite file. `_connect` creates the table and adds any column a notebook kept by an earlier version lacks (the Enrichment columns, `kind`); each new column gets its own check and a default that keeps old rows meaning what they did. It speaks the language of `CONTEXT.md` and knows nothing of HTTP or HTML.
- **`main.py`: the hypermedia layer.** `create_app(notebook_path)` builds the Starlette app. Handlers are thin: build or look up an `Entry`, call one `Notebook` method, then render or redirect. Routes: `GET/POST /entries` (notebook, capture), `GET /entries/{id}` (one row, for htmx; otherwise a redirect to the notebook), `GET/POST /entries/{id}/edit` (Enrichment). The module-level `app` reads its notebook path from `SPY_NOTEBOOK` (default `data/notebook.sqlite3`, gitignored). Run it with `uv run uvicorn main:app --reload`.
- **`templates/`**: `base.html` is the layout every page extends (viewport, htmx config, vendored htmx, `hx-boost`). Partials prefixed `_` are fragments shared by full pages and htmx responses: `_entry.html` (one notebook row), `_capture.html` (the capture box), `_enrich.html` (the Enrichment form; `inline` adds the htmx attributes) and `_editing.html` (a row holding that form, swapped in by htmx). `edit.html` is the Web 1.0 edit page.
- **`static/`**: `style.css` and htmx, vendored and pinned by file name (`htmx-2.0.11.min.js`). To upgrade, download the new `dist/htmx.min.js` from unpkg under its versioned name and update `base.html`.

Invariants:

- Marking an Entry a Tip hides its Spanish and Meaning but keeps them stored, so marking it an Expression again brings them back. A Tip is shown by its captured text and Context, and is never waiting for a Meaning.
- Entry text is stored exactly as typed (capture imposes no format). Only blank text is rejected. Enrichment never touches it: the Spanish is a separate field, prefilled from the text but stored apart.
- The learner's free text (captured text and Enrichment alike) is rendered only inside an element carrying `hx-disable` (each row's `.entry` block, the edit page's `.captured`), or as textarea content, with Jinja autoescaping on. The row's controls (Enrich, the inline form) sit outside it so htmx still drives them; `hx-disable` on the whole `#entries` list would kill them.
- A request is answered with a fragment only when `HX-Request` is set and `HX-Boosted` is not: a boosted link or form wants a whole page. Every rendered response sends `Vary: HX-Request, HX-Boosted`.
- htmx swaps a `422` (a re-rendered form with its errors) but counts it as a failure (`htmx-config` in `base.html`), so the capture box clears only after a real capture.

## Prototype first, deployed later

The target is a deployed, hosted service (`docs/system-design/boundary.md`), with identity delegated to a provider such as Clerk. The current stage is a prototype that runs on the owner's machine: no auth, no deployment. Don't build sign-in or deployment until asked. Do keep the shape compatible with hosting: state lives server-side, not in the browser, so the phone and laptop will see the same notebook once it is deployed.

Record here, as the code grows, which module owns what, the load-bearing invariants, and what must never leak across a boundary.
