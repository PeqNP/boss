# Agent Instructions

This repository uses a centralized rule system to keep Copilot and Claude in sync.

## General Guidelines
- When making technical decisions, do not give much weight to development cost. Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.

## Tooling Preferences
- Use `rg` (`ripgrep`) first for repository text and file discovery.
- Prefer this tool order for speed and reliability: `rg` -> file reads -> minimal patches -> diagnostics.
- Prefer `apply_patch` for code edits; use scripted rewrites only for large mechanical transformations where patching is impractical.
- Parallelize independent read-only discovery when possible.
- If `rg` is unavailable in a given environment, fall back to `grep`.

## GitHub Operations
- For GitHub tasks (issues, PRs, workflow runs, releases, API queries), use the `gh-axi` workflow.
- Development machine setup requirements for `gh` and `gh-axi` are documented in [`docs/install-instructions.md`](docs/install-instructions.md).

## Primary Rule Sources
Coding conventions, patterns, lifecycle rules, delegate patterns, and UI guidelines are split into focused files under `docs/prompt/`:

| File | Contents |
|---|---|
| [`docs/prompt/shared.md`](docs/prompt/shared.md) | Project layout, application.json, coding rules, memory.md conventions, quick reference |
| [`docs/prompt/js.md`](docs/prompt/js.md) | JS controller patterns, UI components, OS APIs, Godot integration |
| [`docs/prompt/swift.md`](docs/prompt/swift.md) | Vapor web layer (routes, fragments, forms), bosslib private API |
| [`docs/prompt/python.md`](docs/prompt/python.md) | Python private services |


## Instruction Triggers
Lightweight files in `.github/instructions/` use `applyTo` globs to automatically tell agents which rules apply to a given file:

| Trigger File                            | `applyTo` Pattern                                      | Required Action |
|-----------------------------------------|--------------------------------------------------------|-----------------|
| `boss-app-controllers.instructions.md`  | `public/boss/app/**/*.html`                            | Read `docs/prompt/shared.md` and `docs/prompt/js.md` |
| `lean-app.instructions.md`              | `public/boss/app/io.bithead.lean/**`, server routes    | Read `docs/prompt/shared.md` and `public/boss/app/io.bithead.lean/memory.md` |
| `godot.instructions.md`                 | `public/boss/app/**/controller/*.js`                   | Read `docs/prompt/shared.md` and `docs/prompt/js.md` |
| `swift.instructions.md`                 | `server/**/*.swift`                                    | Read `docs/prompt/shared.md` and `docs/prompt/swift.md` |
| `python.instructions.md`                | `private/**/*.py`                                      | Read `docs/prompt/shared.md` and `docs/prompt/python.md` |
| `copilot-tool-usage.instructions.md`    | `**`                                                   | Follow tool usage rules (GitHub Copilot) |

## Recommended Workflow
1. When you begin editing any file, check whether its path matches an `applyTo` pattern in `.github/instructions/`.
2. Load the referenced documentation or memory file **before** making changes.
3. Follow the rules defined in the loaded files.

This structure ensures both agents always operate from the same source of truth without duplicating rules.
