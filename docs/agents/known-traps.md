# Known Traps

Diagnoses that have cost time before. Check these first.

- **Mojibake when posting with `curl -d`.** `curl -d "text=¡Qué guay!"` sends raw UTF-8 that is not percent-encoded, and Starlette decodes it as Latin-1 (`Â¡QuÃ©`). Browsers always percent-encode form bodies, so the app is fine. Use `curl --data-urlencode` when smoke-testing.
- **`StarletteDeprecationWarning` about `httpx` in test output.** Starlette 1.x prefers `httpx2` for `TestClient`. The tests use `httpx` for now. The warning is harmless, and switching is a dev-dependency change only.
- **htmx does not swap 4xx responses by default.** The capture form relies on the `responseHandling` rule for `422` in `base.html`'s `htmx-config`. Without it, a rejected htmx capture shows nothing.
