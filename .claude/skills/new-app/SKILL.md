---
name: new-app
description: Start a new BOSS application. Use when the user wants to build, create, or scaffold a BOSS app that does not yet exist, or arrives with an idea for an app. Interviews, writes description.md (the spec), then plan.md. Does not write code. Do not use for an app that already has a bundle (develop skill), for BOSS OS changes, or for the generic design-doc skill.
when-to-use: build a BOSS app, create a new app, new BOSS application, scaffold an app
---

# New BOSS app

The contract is [`process.md`](../../../docs/prompt/process.md). Read its index, then [Classify](../../../docs/prompt/process.md#classify-the-work), [Phase 0](../../../docs/prompt/process.md#phase-0--design-interview), and [Phase 1](../../../docs/prompt/process.md#phase-1--write-the-plan). Do not ingest the rest.

This skill is the procedure. Do not restate those sections here.

## Do this, in order

1. Confirm there is no bundle yet. If `public/boss/app/<bundle_id>/` exists, stop and use the `develop` skill.
2. Interview as Phase 0 says. Ask with the tool that section names for this environment. Branching questions first; follow-ups only when the answers invoke them.
3. Write `public/boss/app/<bundle_id>/description.md` in the shape Phase 0 gives. Propose `io.bithead.<slug>` from the name; ask only if the prefix is wrong.
4. Stop. Ask the developer to confirm or correct **that file**. Do not write `plan.md` until they have.
5. Write `private/app/<bundle_id>/plan.md` as Phase 1 says, derived from the spec. Ask only where Phase 1 already says a case is ambiguous.
6. Write `public/boss/app/<bundle_id>/memory.md`: plan confirmed, Stage 1 is next. See [`shared.md` § App memory.md Files](../../../docs/prompt/shared.md#17-app-memorymd-files).
7. Stop. Say Stage 1 is next and wait. Do not create `application.json`, controllers, or routes in this turn.

## What this skill does not do

- Write code, stubs, or `application.json`.
- Use the generic design-doc skill or Grok plan mode. Those write the wrong artifact.
- Start Stage 1 in the same turn the plan is confirmed.
