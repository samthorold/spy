# Delivery Workflow

How work moves from a design question to merged code in this repo.

## The pipeline

For an epic: `grill-with-docs` (settle the design against `CONTEXT.md`, `docs/learning/` and `docs/system-design/`, updating the docs inline) → `to-issues` (tracer-bullet vertical slices, labelled `ready-for-agent`) → `tdd` per slice.

- **One branch and one PR per slice.** Squash-merge with `--delete-branch`, and close the issue referencing the PR. The repo's gitignored `.claude/settings.local.json` allows the git/gh commands, so the flow runs without prompts.
- **TDD strictly red → green,** one behaviour per cycle. Surface design ambiguity the moment it appears rather than guessing.
- **Checkpoint at natural boundaries** (for example halfway through an epic) with a concise status and a default to continue, not a stop-and-ask. The owner delegates heavily and wants momentum with visibility, not permission-seeking at every step.

## The test loop

pytest, driving the app through Starlette's `TestClient` (`docs/agents/hypermedia.md`, *Testing*), plus model tests that call `Notebook` directly (`tests/test_notebook.py`). Tests live in `tests/`. An autouse fixture in `tests/conftest.py` points `SPY_NOTEBOOK` at a tmp file for every test, so no test touches the real notebook. Shared helpers live in `tests/support.py`; test modules never import each other. No mocks and no monkeypatching of code (`docs/agents/architecture.md`, *Rules*).

- **Inner loop** (one file): `uv run pytest tests/test_capture.py`. Narrow further with `-k <name>`.
- **Full run** (before every commit): `uv run pytest`.
- **Type check** (before every commit, alongside the full run): `uvx pyright -p pyproject.toml`, which must report 0 errors. The config is `strict` and covers `main.py`, `app/` and `tests/`, so tests annotate their fixture parameters (`client: TestClient`, `notebook_path: Path`) and helpers. A regex match the test needs goes through `search` in `tests/support.py`, which fails the test with a message rather than returning `None`. No `# type: ignore`, `cast` or relaxed settings.
- **Baseline** (the `app/` package refactor): 73 tests, about 4–5.5s in pytest on the owner's machine (issue #6's 69 tests measured 0.8–5.4s in back-to-back runs, so single runs are noisy). Expect a few seconds; the slowest test is the shuffled-recap one (about 0.7s). A run well past that means something is wrong (a hang, a real network call). Find the test that is still running and stop it rather than waiting.

## Durable knowledge lives in the repo

Anything worth remembering across sessions — workflow, runtimes, known traps, project vision — is written into committed docs (`CLAUDE.md`, `docs/agents/`, `CONTEXT.md`, `docs/system-design/`), never only in an agent's private memory. Private memory is not under source control and drifts out of date unseen.

Research working folders and scratch outputs are temporary. Once the research is finished, fold what is durable into the right docs layer: domain findings into `docs/learning/`, measurements into `docs/research/<issue>-<slug>.md`, and design into `docs/system-design/` via a grill. Then delete the working folders. They are never committed.
