# Agent Instructions

This repository uses a centralized rule system to keep Copilot and Claude in sync.

## General Guidelines
- When making technical decisions, do not give much weight to development cost. Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.

## Response Style
- Keep responses concise by default.
- Do not use validation filler phrasing (for example: "you're right", "you are right to think that").

## Tooling Preferences
- Use `rg` (`ripgrep`) first for repository text and file discovery.
- Prefer this tool order for speed and reliability: `rg` -> file reads -> minimal patches -> diagnostics.
- Prefer `apply_patch` for code edits; use scripted rewrites only for large mechanical transformations where patching is impractical.
- Parallelize independent read-only discovery when possible.
- If `rg` is unavailable in a given environment, fall back to `grep`.

## GitHub Operations
- For GitHub tasks (issues, PRs, workflow runs, releases, API queries), use the `gh-axi` workflow.
- Development machine setup requirements for `gh` and `gh-axi` are documented in [`docs/install-instructions.md`](docs/install-instructions.md).

## Where to Start

`AGENTS.md` is the entry point. Read the rule source for the layer you are
working in (below), plus the app's `memory.md` if it has one. Files listed in
[`docs/prompt/ignore.md`](docs/prompt/ignore.md) may be skipped.

## Primary Rule Sources
Coding conventions, patterns, lifecycle rules, delegate patterns, and UI guidelines are split into focused files under `docs/prompt/`:

| File | Contents |
|---|---|
| [`docs/prompt/shared.md`](docs/prompt/shared.md) | Project layout, application.json, coding rules, memory.md conventions, quick reference |
| [`docs/prompt/js.md`](docs/prompt/js.md) | JS controller patterns, UI components, OS APIs, Godot integration |
| [`docs/prompt/js-api.md`](docs/prompt/js-api.md) | Generated index of every BOSS JS method, grouped by the component that defines it. Consult before calling a method you have not used before — do not infer a method exists on one component because another defines it. |
| [`docs/prompt/swift.md`](docs/prompt/swift.md) | Vapor web layer (routes, fragments, forms), bosslib private API |
| [`docs/prompt/python.md`](docs/prompt/python.md) | Python private services |
| [`docs/prompt/process.md`](docs/prompt/process.md) | Development process: design interview, plan.md, layer responsibilities, when to write tests |
| [`docs/coding-style.md`](docs/coding-style.md) | Code formatting |


## Instruction Triggers

Lightweight files in `.github/instructions/` map path globs to the rules that apply.

> **These fire automatically only for GitHub Copilot.** `applyTo` frontmatter is
> a Copilot feature. Other agents — including Claude Code — receive no automatic
> injection: nothing loads `js.md` when you edit a controller. For those agents
> this table is a **checklist you must consult yourself**, before writing, not
> after getting stuck. Treating it as automation is how documented APIs get
> rediscovered from OS source.



| Trigger File                            | `applyTo` Pattern                                      | Required Action |
|-----------------------------------------|--------------------------------------------------------|-----------------|
| `boss-app-controllers.instructions.md`  | `public/boss/app/**/*.html`                            | Read `docs/prompt/shared.md` and `docs/prompt/js.md` |
| `lean-app.instructions.md`              | `public/boss/app/io.bithead.lean/**`, server routes    | Read `docs/prompt/shared.md` and `public/boss/app/io.bithead.lean/memory.md` |
| `godot.instructions.md`                 | `public/boss/app/**/controller/*.js`                   | Read `docs/prompt/shared.md` and `docs/prompt/js.md` |
| `swift.instructions.md`                 | `server/**/*.swift`                                    | Read `docs/prompt/shared.md` and `docs/prompt/swift.md` |
| `python.instructions.md`                | `private/**/*.py`                                      | Read `docs/prompt/shared.md` and `docs/prompt/python.md` |
| `copilot-tool-usage.instructions.md`    | `**`                                                   | Follow tool usage rules (GitHub Copilot) |

## Recommended Workflow
1. When you begin editing any file, check whether its path matches an `applyTo` pattern in `.github/instructions/`. Nothing does this for you — see the note above.
2. Load the referenced documentation or memory file **before** making changes. In a long session, load it again when starting a new implementation phase: context established early is summarized as the session grows, and detail is lost.
3. Follow the rules defined in the loaded files.
4. Before reading OS source to answer "what API does this component have", check [`docs/prompt/js-api.md`](docs/prompt/js-api.md). Reading `ui.js` (~6,400 lines) to rediscover a documented API is the single largest avoidable time cost in app work.
5. Run `bin/validate-app <bundle_id>` before reporting an app bundle as complete.
6. A rule belongs in one document. If it is already stated elsewhere, link to it rather than restating it — a second copy drifts. Run `bin/check-docs` after moving or renaming a document.

This structure ensures both agents always operate from the same source of truth without duplicating rules.
