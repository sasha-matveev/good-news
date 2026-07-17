# Domain Docs

How engineering skills should consume this repo's domain documentation while exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points to one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/`.

If any of these files do not exist, proceed silently. The `/domain-modeling` skill creates them lazily when terms or decisions are resolved.

## File structure

This is a single-context repository:

```
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

When naming a domain concept, use the term defined in `CONTEXT.md`. If a needed concept is absent, reconsider whether project language already covers it, or note the gap for `/domain-modeling`.

## Flag ADR conflicts

Surface any conflict with an existing ADR explicitly rather than silently overriding it.
