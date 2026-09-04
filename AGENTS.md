# Agent Instructions

This repository uses a centralized rule system to keep Copilot, Claude, and Grok in sync.

## Classify first

Name the **kind** and the **size** before reading a layer document or writing anything. The full table is [`docs/prompt/process.md`](docs/prompt/process.md) § Classify the work.

| Kind | Then |
|---|---|
| **New app** — no bundle yet | `new-app` skill. No code until `plan.md` is confirmed. |
| **Existing app, small** — copy, one control, a bug, a field whose contract does not change | Layer index, then the section that applies. No interview. Amend `plan.md` only if a signature, actor, or window kind changes. |
| **Existing app, medium or large** | `develop` skill. Read `process.md` from Classify through the current stage, not the rest. |
| **BOSS OS** — `public/boss/*.js`, `public/boss/*.css` | Ask before changing. An existing API likely covers it. |
| **Process / docs / checks** | A rule lives in one document; others point at it. |

A layer document is read from its **index**, then the sections that apply — never whole. [`js-api.md`](docs/prompt/js-api.md) is a lookup: consult the component's own entry before calling a method you have not used.

Do not use the generic design-doc skill or Grok plan mode for a BOSS app. The spec is `description.md`; the contract is `private/app/<bundle_id>/plan.md`.

## General Guidelines
- When making technical decisions, weigh quality, simplicity, robustness, scalability, and long term maintainability above development cost.

## Response Style
- Keep responses concise by default.
- Open with the substance. Validation filler ("you're right", "you are right to think that") goes.

## Tooling Preferences
- Use `rg` (`ripgrep`) first for repository text and file discovery.
- Prefer this tool order for speed and reliability: `rg` -> file reads -> minimal patches -> diagnostics.
- Prefer `apply_patch` for code edits; use scripted rewrites only for large mechanical transformations where patching is impractical.
- Parallelize independent read-only discovery when possible.
- If `rg` is unavailable in a given environment, fall back to `grep`.

## GitHub Operations
- For GitHub tasks (issues, PRs, workflow runs, releases, API queries), use the `gh-axi` workflow.
- Development machine setup requirements for `gh` and `gh-axi` are documented in [`docs/install-instructions.md`](docs/install-instructions.md).

## Reporting Work

Every response that changed something ends with a report. The `report` skill
carries its shape, and the `commit` skill the message that goes at the end of
it. A response that changed nothing reports nothing.

## Where to Start

`AGENTS.md` is the entry point. Classify, then load only what the kind requires
— plus the app's `memory.md` if it has one. Files listed in
[`docs/prompt/ignore.md`](docs/prompt/ignore.md) may be skipped.

## Primary Rule Sources

Coding conventions, patterns, lifecycle rules, delegate patterns, and UI guidelines are split into focused files under `docs/prompt/`. Read each from its index.

| File | Contents |
|---|---|
| [`docs/prompt/process.md`](docs/prompt/process.md) | Size and kind, interview, spec, `plan.md`, layers, when to write tests, stages |
| [`docs/prompt/shared.md`](docs/prompt/shared.md) | Project layout, application.json, coding rules, memory.md, how to run and check |
| [`docs/prompt/js.md`](docs/prompt/js.md) | JS controller patterns, UI components, OS APIs, Godot integration |
| [`docs/prompt/js-api.md`](docs/prompt/js-api.md) | Generated index of every BOSS JS method, grouped by the component that defines it |
| [`docs/prompt/swift.md`](docs/prompt/swift.md) | Vapor web layer (routes, fragments, forms), bosslib private API |
| [`docs/prompt/python.md`](docs/prompt/python.md) | Python private services |
| `new-app` skill | New BOSS app: interview, spec, plan, stop |
| `develop` skill | Existing app: current stage or slice, then stop |
| `private-service-tests` skill | Stage 3 / step 4 of a private service |
| `report` skill | How every response that changed something ends |
| `commit` skill | The message that goes at the end of it |
| [`docs/coding-style.md`](docs/coding-style.md) | Code formatting |

Skills live in [`.claude/skills/`](.claude/skills/). Grok loads them via Claude compatibility.

## Instruction Triggers

Lightweight files in `.github/instructions/` map path globs to the rules that apply.

> **These fire automatically only for GitHub Copilot.** `applyTo` frontmatter is
> a Copilot feature. Other agents — including Claude Code and Grok — receive no
> automatic injection: nothing loads `js.md` when you edit a controller. For
> those agents this table is a **checklist you must consult yourself**, before
> writing, not after getting stuck. Treating it as automation is how documented
> APIs get rediscovered from OS source. Skills (`new-app`, `develop`) are the
> equivalent for process, and they do auto-invoke from their descriptions.

| Trigger File                            | `applyTo` Pattern                                      | Required Action |
|-----------------------------------------|--------------------------------------------------------|-----------------|
| `boss-app-controllers.instructions.md`  | `public/boss/app/**/*.html`                            | `shared.md` and `js.md` indexes, then the sections that apply |
| `godot.instructions.md`                 | `public/boss/app/**/controller/*.js`                   | `shared.md` index; `js.md` § Godot Integration and any other section that applies |
| `swift.instructions.md`                 | `server/**/*.swift`                                    | `shared.md` and `swift.md` indexes, then the sections that apply |
| `python.instructions.md`                | `private/**/*.py`                                      | `shared.md` and `python.md` indexes, then the sections that apply |
| `copilot-tool-usage.instructions.md`    | `**`                                                   | Follow tool usage rules (GitHub Copilot) |

## Recommended Workflow
1. Classify the kind and size. Load the matching skill, or the layer index, not both by default.
2. When editing a file, check whether its path matches an `applyTo` pattern in `.github/instructions/`. Nothing does this for you — see the note above.
3. Load the referenced **index**, then the sections that apply, plus `memory.md` when the work is an existing app. In a long session, load the section again when starting a new implementation phase: context established early is summarized as the session grows, and detail is lost.
4. Follow the rules defined in the loaded sections.
5. Before reading OS source to answer "what API does this component have", check [`docs/prompt/js-api.md`](docs/prompt/js-api.md). Reading `ui.js` (~6,400 lines) to rediscover a documented API is the single largest avoidable time cost in app work.
6. Run `bin/validate-app <bundle_id>` before reporting an app bundle as complete, and before calling a UI stage finished.
7. A rule belongs in one document. Where it is already stated elsewhere, link to it. Run `bin/check-docs` after moving or renaming a document.

This structure ensures agents always operate from the same source of truth without duplicating rules.
