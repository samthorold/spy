# Architecture

How the code divides responsibility. Read this before deciding *where* a change belongs.

## Stack

Starlette serves HTML rendered by Jinja and extended with htmx: a hypermedia-driven application, not a SPA with a JSON API. How to build in that style is in [hypermedia.md](hypermedia.md). Development is test-driven (`/tdd`), through the HTTP interface.

## Today

- **`notebook.py`: the model.** `Entry` (the captured `text`, its Enrichment `spanish` / `meaning` / `context`, its `kind` (`Kind.EXPRESSION` by default, or `Kind.TIP`), its `captured_at`, and what the views ask of it: `errors`, `proposed_spanish`, `headline`, `is_tip`, `waiting_for_meaning`, `recallable`) and `Notebook` (`capture(entry)`, `entries()` newest first, `entry(id)`, `enrich(entry)`, `recap(window, order, seed)`, `waiting(window)`: the Expressions in the window still waiting for a Meaning, newest first), stored in a SQLite file. `Window` (`week`, `all`), `Order` (`newest`, `shuffled`) and `Direction` (`spanish`, `meaning`: the side shown first) are the Recap's choices; the direction changes only what the card shows, never which Expressions `recap` returns. `Notebook(path, clock=...)` takes the time from `clock`, so tests that depend on it pass their own (`create_app(path, clock=...)`). `_connect` creates the table and adds any column a notebook kept by an earlier version lacks (the Enrichment columns, `kind`, `captured_at`); each new column gets its own check and a default that keeps old rows meaning what they did. It speaks the language of `CONTEXT.md` and knows nothing of HTTP or HTML.
- **`main.py`: the hypermedia layer.** `create_app(notebook_path)` builds the Starlette app. Handlers are thin: build or look up an `Entry`, call one `Notebook` method, then render or redirect. Routes: `GET/POST /entries` (notebook, capture), `GET /entries/{id}` (one row, for htmx; otherwise a redirect to the notebook), `GET/POST /entries/{id}/edit` (Enrichment; an optional `next` names the page to go back to once saved or cancelled, kept in a hidden field, otherwise the notebook), `GET /recap` (Recap, one step per URL: `?window=week|all&order=newest|shuffled&direction=spanish|meaning[&seed=N]&at=K[&reveal=1]`; a shuffled recap without a seed is redirected to one with a fresh seed; missing or unknown values fall back to the defaults, `week`, `newest` and `spanish`, so URLs bookmarked before the direction existed are Spanish first). The module-level `app` reads its notebook path from `SPY_NOTEBOOK` (default `data/notebook.sqlite3`, gitignored). Run it with `uv run uvicorn main:app --reload`.
- **`templates/`**: `base.html` is the layout every page extends (viewport, htmx config, vendored htmx, `hx-boost`). Partials prefixed `_` are fragments shared by full pages and htmx responses: `_entry.html` (one notebook row), `_capture.html` (the capture box), `_enrich.html` (the Enrichment form; `inline` adds the htmx attributes) and `_editing.html` (a row holding that form, swapped in by htmx), `_recap_card.html` (one step of a recap; the side shown first carries the `prompt` class; its Reveal and Next links swap only the card and push its URL). `edit.html` is the Web 1.0 edit page; `recap.html` is the recap page, with the window, order and direction as a GET form, and below the card the Entries in the window waiting for a Meaning (their count, and an Enrich link to each whose `next` is the start of this recap).
- **`static/`**: `style.css` and htmx, vendored and pinned by file name (`htmx-2.0.11.min.js`). To upgrade, download the new `dist/htmx.min.js` from unpkg under its versioned name and update `base.html`.

Invariants:

- Marking an Entry a Tip hides its Spanish and Meaning but keeps them stored, so marking it an Expression again brings them back. A Tip is shown by its captured text and Context, and is never waiting for a Meaning.
- Entry text is stored exactly as typed (capture imposes no format). Only blank text is rejected. Enrichment never touches it: the Spanish is a separate field, prefilled from the text but stored apart.
- The learner's free text (captured text and Enrichment alike) is rendered only inside an element carrying `hx-disable` (each row's `.entry` block, the edit page's `.captured`), or as textarea content, with Jinja autoescaping on. The row's controls (Enrich, the inline form) sit outside it so htmx still drives them; `hx-disable` on the whole `#entries` list would kill them.
- A request is answered with a fragment only when `HX-Request` is set and neither `HX-Boosted` nor `HX-History-Restore-Request` is: a boosted link or form, and htmx restoring a pushed URL, want a whole page. Every rendered response sends `Vary: HX-Request, HX-Boosted, HX-History-Restore-Request`.
- A Recap's prompts are the `recallable` Entries: Expressions with a Meaning, never Tips or Expressions waiting for one. A Recap's Spanish side is the Entry's `headline` in both directions, so an Expression whose Spanish was cleared is prompted by (or, Meaning first, reveals) its captured text.
- Recap surfaces the Entries in its window waiting for a Meaning (never Tips), by the same window rule as its prompts. Enriching one from there comes back to the start of the same recap, where it is now a prompt.
- A `next` is followed only when it is a path on this site (starts with a single `/`, no scheme, host or backslash); anything else falls back to the notebook, so the edit page is never an open redirect.
- An Entry captured before the notebook kept capture times has `captured_at` None and is recapped only in the `all` window: no time is invented for it.
- htmx swaps a `422` (a re-rendered form with its errors) but counts it as a failure (`htmx-config` in `base.html`), so the capture box clears only after a real capture.

## Prototype first, deployed later

The target is a deployed, hosted service (`docs/system-design/boundary.md`), with identity delegated to a provider such as Clerk. The current stage is a prototype that runs on the owner's machine: no auth, no deployment. Don't build sign-in or deployment until asked. Do keep the shape compatible with hosting: state lives server-side, not in the browser, so the phone and laptop will see the same notebook once it is deployed.

Record here, as the code grows, which module owns what, the load-bearing invariants, and what must never leak across a boundary.
