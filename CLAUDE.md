## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — three layers: CONTEXT.md (ubiquitous language) + docs/learning/ (domain) + docs/system-design/ (the design, which is self-justifying — no separate decision-record layer). See `docs/agents/domain.md`.

### Architecture

How the code divides responsibility. Read before deciding where a change belongs. See `docs/agents/architecture.md`.

### Hypermedia patterns

Starlette + Jinja + htmx, following *Hypermedia Systems*: HTML over the wire, thin handlers and a fat model, Web 1.0 first then progressive enhancement, PRG with 303s, fragments with `Vary`. See `docs/agents/hypermedia.md`.

### Delivery workflow

grill-with-docs → to-issues → one TDD slice per PR, squash-merged. Durable knowledge goes in committed docs, never only in agent memory. See `docs/agents/delivery-workflow.md`.

### Project vision

What the app is for. See `docs/agents/project-vision.md`.

### Known traps

Diagnoses that have cost time before. See `docs/agents/known-traps.md`.

## Code style

Python (see `pyproject.toml`), run with `uv`. Match the surrounding code.
