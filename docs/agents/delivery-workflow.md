# Delivery Workflow

How work moves from a design question to merged code in this repo.

## The pipeline

For an epic: `grill-with-docs` (settle the design against `CONTEXT.md`, `docs/learning/` and `docs/system-design/`, updating the docs inline) → `to-issues` (tracer-bullet vertical slices, labelled `ready-for-agent`) → `tdd` per slice.

- **One branch and one PR per slice.** Squash-merge with `--delete-branch`, and close the issue referencing the PR. The repo's gitignored `.claude/settings.local.json` allows the git/gh commands, so the flow runs without prompts.
- **TDD strictly red → green,** one behaviour per cycle. Surface design ambiguity the moment it appears rather than guessing.
- **Checkpoint at natural boundaries** (for example halfway through an epic) with a concise status and a default to continue, not a stop-and-ask. The owner delegates heavily and wants momentum with visibility, not permission-seeking at every step.

## The test loop

pytest, driving the app through Starlette's `TestClient` (`docs/agents/hypermedia.md`, *Testing*). Tests live in `tests/`, and each builds its own app with `create_app(tmp_path / "notebook.sqlite3")`, so no test touches the real notebook.

- **Inner loop** (one file): `uv run pytest tests/test_capture.py`. Narrow further with `-k <name>`.
- **Full run** (before every commit): `uv run pytest`.
- **Baseline** (issue #3): 40 tests, about 0.3s in pytest and under 0.5s wall clock including `uv` start-up. A run that takes seconds means something is wrong (a hang, a real network call). Find the test that is still running and stop it rather than waiting.

## Durable knowledge lives in the repo

Anything worth remembering across sessions — workflow, runtimes, known traps, project vision — is written into committed docs (`CLAUDE.md`, `docs/agents/`, `CONTEXT.md`, `docs/system-design/`), never only in an agent's private memory. Private memory is not under source control and drifts out of date unseen.

Research working folders and scratch outputs are temporary. Once the research is finished, fold what is durable into the right docs layer: domain findings into `docs/learning/`, measurements into `docs/research/<issue>-<slug>.md`, and design into `docs/system-design/` via a grill. Then delete the working folders. They are never committed.
