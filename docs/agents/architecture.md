# Architecture

How the code divides responsibility. Read this before deciding *where* a change belongs.

## Stack

Starlette serves HTML rendered by Jinja and extended with htmx: a hypermedia-driven application, not a SPA with a JSON API. How to build in that style is in [hypermedia.md](hypermedia.md). Development is test-driven (`/tdd`), through the HTTP interface.

## Today

The app is a single Starlette module, `main.py`, with Jinja templates in `templates/` and static files in `static/`. Its domain types (for example `FlashCard`, which predates the language in `CONTEXT.md`) sit at the top of `main.py`.

## Prototype first, deployed later

The target is a deployed, hosted service (`docs/system-design/boundary.md`), with identity delegated to a provider such as Clerk. The current stage is a prototype that runs on the owner's machine: no auth, no deployment. Don't build sign-in or deployment until asked. Do keep the shape compatible with hosting: state lives server-side, not in the browser, so the phone and laptop will see the same notebook once it is deployed.

Record here, as the code grows, which module owns what, the load-bearing invariants, and what must never leak across a boundary.
