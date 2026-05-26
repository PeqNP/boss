# Agent Instructions

This repository uses a centralized rule system to keep Copilot and Claude in sync.

## Primary Rule Source
All coding conventions, patterns, lifecycle rules, delegate patterns, and UI guidelines live in one place:

**`docs/prompt/boss-reference.md`**

## Instruction Triggers
Lightweight files in `.github/instructions/` use `applyTo` globs to automatically tell agents which rules apply to a given file:

| Trigger File                            | `applyTo` Pattern                                      | Required Action |
|-----------------------------------------|--------------------------------------------------------|-----------------|
| `boss-app-controllers.instructions.md`  | `public/boss/app/**/*.html`                            | Read `docs/prompt/boss-reference.md` |
| `lean-app.instructions.md`              | `public/boss/app/io.bithead.lean/**`, server routes    | Read `public/boss/app/io.bithead.lean/memory.md` |
| `swift.instructions.md`                 | `server/**/*.swift`                                    | Read §13 (Swift Web Layer) and §14 (bosslib) of `boss-reference.md` |
| `python.instructions.md`                | `private/**/*.py`                                      | Read §15 (Python Private Services) of `boss-reference.md` |
| `copilot-tool-usage.instructions.md`    | `**`                                                   | Follow tool usage rules (GitHub Copilot) |

## Recommended Workflow
1. When you begin editing any file, check whether its path matches an `applyTo` pattern in `.github/instructions/`.
2. Load the referenced documentation or memory file **before** making changes.
3. Follow the rules defined in the central `boss-reference.md`.

This structure ensures both agents always operate from the same source of truth without duplicating rules.