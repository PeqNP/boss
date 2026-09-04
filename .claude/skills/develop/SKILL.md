---
name: develop
description: Continue work on an existing BOSS app — the next stage of its plan.md, a new screen, a new endpoint group, or a medium/large change to a bundle that already exists. Use when building, extending, or resuming a BOSS app. Do not use for a brand-new app (new-app skill), for BOSS OS changes, or for a small fix that does not change a plan.
when-to-use: continue the app, next stage, add a screen, implement stage, resume the plan, extend the app
---

# Continue a BOSS app

The contract is [`process.md`](../../../docs/prompt/process.md). Read its index, then [Classify](../../../docs/prompt/process.md#classify-the-work) and the section for the current stage. Do not ingest the rest.

This skill is the procedure. Do not restate those sections here.

## Do this, in order

1. Classify size. If Classify says **small**, this skill does not apply: load the layer index, then the section that applies, and stop reading this file.
2. Read the app's `description.md`, `plan.md`, and `memory.md`. If `memory.md` is missing and a stage is open, create it.
3. A medium or large change that needs new decisions: Phase 0 for **those questions only**, amend `description.md` where the answers changed, then the relevant `plan.md` sections. Stop for confirmation before writing code.
4. Walk the **current** stage from [`process.md` § Development Order](../../../docs/prompt/process.md#development-order). For a medium slice, only the screens and routes that slice names. Load each layer document from its index, then the sections that apply.
5. Step 4 of Development Order uses the `private-service-tests` skill. Step 8 writes `ui-plan.md` first.
6. Run what the stage names (`bin/validate-app` at the end of Stage 1 and again before step 3; the stage's tests at the end of steps 4–5 and 8).
7. Update `memory.md` with the stage just finished and the next one. Report. Stop. Do not start the next stage in this turn.

## What this skill does not do

- Start a new app. That is `new-app`.
- Change BOSS OS. Ask first, as Classify says.
- Load `js.md` or `python.md` whole.
- Continue past the current stage because the user said "build the app".
