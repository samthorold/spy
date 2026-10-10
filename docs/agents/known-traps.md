# Known Traps

Diagnoses that have cost time before. Check these first.

- **Mojibake when posting with `curl -d`.** `curl -d "text=¡Qué guay!"` sends raw UTF-8 that is not percent-encoded, and Starlette decodes it as Latin-1 (`Â¡QuÃ©`). Browsers always percent-encode form bodies, so the app is fine. Use `curl --data-urlencode` when smoke-testing.
- **`StarletteDeprecationWarning` about `httpx` in test output.** Starlette 1.x prefers `httpx2` for `TestClient`. The tests use `httpx` for now. The warning is harmless, and switching is a dev-dependency change only.
- **`hx-disable` on a container disables every htmx control inside it.** Put it on the element holding the learner's free text, not on a list whose rows also carry `hx-get` / `hx-post` controls. Tests through `TestClient` cannot see this: `HtmxReach` in `tests/support.py` checks which text and controls sit outside any `hx-disable`.
- **Boosted requests also send `HX-Request: true`.** `hx-boost` on the body turns plain links and forms into htmx requests that want a whole page. `is_htmx` in `app/web.py` excludes them via `HX-Boosted`; branching on `HX-Request` alone would swap a row fragment into the whole body.
- **htmx does not swap 4xx responses by default.** The capture form relies on the `responseHandling` rule for `422` in `base.html`'s `htmx-config`. Without it, a rejected htmx capture shows nothing.
- **htmx history restore sends `HX-Request: true` too.** A link with `hx-push-url` (the recap card) puts its URL in history. Going Back to it when htmx has no snapshot makes htmx fetch the URL with `HX-History-Restore-Request: true` and swap the answer into the whole body, so a fragment there would replace the page. `is_htmx` excludes it, and `Vary` names it.
