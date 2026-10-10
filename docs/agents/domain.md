# Domain Docs

How the engineering skills should consume this repo's documentation when exploring the codebase.

The project's knowledge lives in three layers: the **domain** (the true facts of how people learn a language), the **system design** (our opinion about how the app should support that, which any implementation must encode), and the **implementation** (the code). There is no decision-record layer — the reasons the design has its shape are written into the system-design docs themselves, in the present tense.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the ubiquitous language.
- **`docs/learning/`** — the domain ground truth for the area you're working in.
- **`docs/system-design/`** — the design that governs the area you're about to work in. Mechanisms, rules, and the reasons for them live here; read the documents that touch your area before changing code.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or design actually get resolved.

## File structure

```
/
├── CONTEXT.md                ← ubiquitous language
├── docs/
│   ├── learning/             ← domain ground truth
│   └── system-design/        ← the design (self-justifying)
└── main.py, app/             ← implementation (see architecture.md)
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag design conflicts

If your output contradicts the documented system design, surface it explicitly rather than silently overriding, and say why it is worth reopening.

If the design doc is silent on *why* it has its current shape and you need that to proceed, that's a gap in the system-design layer — note it for `/grill-with-docs` so the rationale gets written into the design doc itself.
