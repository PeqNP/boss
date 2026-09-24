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
2. Read the app's `description.md`, its plan, and `memory.md`. The plan is `plan.md`, or `plans/01-plan.md` once that folder exists, plus the open `plans/NN-name.md` named in `memory.md`. If `memory.md` is missing and a stage is open, create it.
3. A medium or large change that needs new decisions: Phase 0 for **those questions only**. A second feature is a new `plans/NN-name.md`, per [`process.md` § Numbered plans](../../../docs/prompt/process.md#numbered-plans). Do not append it to the original plan. Amend `description.md` when the feature ships. Stop for confirmation before writing code.
4. Walk the **current** stage from [`process.md` § Development Order](../../../docs/prompt/process.md#development-order). After a confirmed plan, that is Stage 1 — the UI — even when every earlier stage of the app is done. See [`process.md` § Iteration](../../../docs/prompt/process.md#iteration--a-slice-on-a-finished-plan). For a medium slice, only the screens and routes that slice names. Load each layer document from its index, then the sections that apply. Do not write schema, routes, or private tests in the same turn as the first UI.
5. Step 4 of Development Order uses the `private-service-tests` skill. Step 8 writes `ui-plan.md` first.
6. Run what the stage names (`bin/validate-app` at the end of Stage 1 and again before step 3; the stage's tests at the end of steps 4–5 and 8).
7. Update `memory.md` with the stage just finished and the next one. Report
   (the report skill's Next section is that same answer). Stop. Do not start
   the next stage in this turn.

## What this skill does not do

- Start a new app. That is `new-app`.
- Change BOSS OS. Ask first, as Classify says.
- Load `js.md` or `python.md` whole.
- Continue past the current stage because the user said "build the app",
  "please begin", "implement it", or "do the slice". Those mean this stage.
