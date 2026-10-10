# Hypermedia Patterns

The app is a hypermedia-driven application: Starlette serves HTML, Jinja renders it, and htmx extends it. Follow the patterns in *Hypermedia Systems* (Gross, Stepinski, Akşimşek; https://hypermedia.systems/book/contents/), written by htmx's creators. This is the short version of what applies here.

## The server owns the markup

- Every response is HTML. There is no JSON API for the browser. If another client ever needs data, it gets a separate, versioned JSON API under its own root (`/api/v1`); the hypermedia routes are never contorted to serve it.
- Because clients find URLs in the HTML they are given, hypermedia endpoints can be added, renamed or removed freely.
- **Thin handlers, fat model.** A handler looks up or builds a domain object, calls one domain method, then renders or redirects. Domain logic and storage sit behind a model layer that knows nothing about HTML or HTTP.

## Start from Web 1.0, then enhance

- Build each feature first as plain links and forms that work with JavaScript off, then layer htmx on top (progressive enhancement). `hx-boost="true"` on the body gives AJAX navigation for free and still degrades.
- **Resource-oriented URLs**, consistent across the app: list `GET /entries`, new `GET /entries/new`, create `POST /entries`, detail `GET /entries/{id}`, edit `GET /entries/{id}/edit`, update `POST /entries/{id}/edit`, delete `POST /entries/{id}/delete` (or `hx-delete` on `/entries/{id}`).
- **Post/Redirect/Get.** A successful form `POST` redirects (`303 See Other`) rather than rendering, so a refresh never resubmits. A `DELETE` must also answer with `303`: a `302` keeps the method and the follow-up would be another `DELETE`.
- **Validation failure re-renders the form** with the submitted values kept and the errors next to the fields. Errors live on the model object, not in the handler.

## Templates and fragments

- One base layout; pages `extend` it. Load htmx from a vendored copy in `app/static/` (no build step).
- Pull markup used in both a full page and an htmx response into its own template (for example the entry rows) and `include` it, so there is one source of truth. Render the fragment alone for htmx requests and the full page otherwise.
- Branch on the `HX-Request` / `HX-Trigger` request headers to choose fragment or full page, and send a matching `Vary` header, or a cache can serve a fragment to a full-page load.
- Prefer server-rendered fragments to `hx-select` filtering a full page on the client.

## Updating other parts of the page

In the authors' order of preference:

1. **Widen the target** so one swap covers everything that changes.
2. **Out-of-band swaps** (`hx-swap-oob="true"`, matched by `id`) for a second region.
3. **Server-triggered events**: an `HX-Trigger` response header that other elements listen for with `hx-trigger="<event> from:body"`.

## Everyday idioms

- `hx-target` with relative selectors (`closest li`, `next .error`) instead of inventing ids.
- `hx-trigger="keyup changed delay:200ms"` for search-as-you-type; target the results, not the input (an input can't hold HTML).
- `hx-indicator` with the `htmx-indicator` class for in-flight feedback; test on a throttled network, since locally everything looks instant.
- `hx-swap="outerHTML"` to replace an element entirely; `204 No Content` means "don't swap".
- Prefer inline editing or a separate page to modals.
- Configure htmx through `<meta name="htmx-config">`.

## Scripting

Scripting is for interaction design only; business and presentation logic stay on the server. Keep state in the DOM, not in JavaScript variables. Favour locality of behaviour (the behaviour is visible on the element that invokes it) and connect scripts to htmx through events. Reach for vanilla JS first; Alpine.js or _hyperscript only if a real need appears.

## Security

Everything the learner types is user content: Jinja autoescaping stays on, and anywhere free text is rendered sits inside an `hx-disable` region so injected `hx-*` attributes are inert.

## Testing

The hypermedia API is the app's public interface, so tests drive it the way a browser does: through Starlette's `TestClient`, asserting on status codes, redirects, headers and the returned HTML. The full-page path and the htmx-fragment path are both behaviour, and each gets a test. Domain rules that depend on things a browser cannot set, such as the time, are tested on the model directly (`docs/agents/architecture.md`, *Rules*).
