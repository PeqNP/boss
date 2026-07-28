---
description: "Rules for how GitHub Copilot should use its editing and file-manipulation tools in this repository."
applyTo: "**"
---

## replace_string_in_file — chained method calls

When inserting a new block *after* an existing block that ends with chained calls (e.g. `.addScope(.user)`, `.deprecationMessage(...)`), always extend `oldString` to include those trailing chained calls. Reproduce them at the correct position in `newString`. Failing to do so leaves the original trailing call outside the replaced region, where it silently chains onto the newly inserted block instead.

**Wrong** — `oldString` stops before `.addScope(.user)`:
```swift
        }.openAPI(
            summary: "Get notification triggers for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
// .addScope(.user) was NOT included — it will orphan onto the new block
```

**Correct** — `oldString` includes `.addScope(.user)`:
```swift
        }.openAPI(
            summary: "Get notification triggers for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
// Now consumed and reproduced correctly in newString
```

## replace_string_in_file — full-file rewrites

When rewriting an entire controller or file, use a **single** `replace_string_in_file` where `oldString` is the complete original file content. Never anchor on just the opening block — partial anchors leave an orphaned tail below the replaced region that requires a separate cleanup pass.

If the file is too large to include the full content in one call, write the replacement to disk using `create_file` after deleting the original, or use `run_in_terminal` to overwrite atomically.

## multi_replace_string_in_file — post-edit verification

After any call that edits multiple files simultaneously, spot-check each affected file to verify no stray characters (e.g. extra `}`, truncated lines) were introduced by boundary errors in `oldString`/`newString` construction.

## replace_string_in_file — content inside oldString must be reproduced in newString

Any content that appears inside `oldString` but is not reproduced in `newString` is silently dropped. This is the most common source of data loss.

**Rule:** Keep `oldString` as narrow as possible — anchor only on the exact line(s) being changed, plus 3–5 lines of surrounding context for uniqueness. Content that should be preserved must either be kept outside `oldString` or reproduced verbatim in `newString`.

**Wrong** — `oldString` includes the first child element but `newString` does not reproduce it:
```html
<!-- oldString -->
<div class="vbox gap-20">
  <div class="read-only">
    <label>Job Code</label>
    <span name="job-code"></span>
  </div>

<!-- newString — child element is gone -->
<div class="vbox gap-20 wider-labels">
```

**Correct** — anchor only on the line being changed; the child element is outside the replaced region:
```html
<!-- oldString (just the class attribute line + minimal context) -->
      <fieldset>
        <legend>Details</legend>
        <div class="vbox gap-20">

<!-- newString — only the class value changes -->
      <fieldset>
        <legend>Details</legend>
        <div class="vbox gap-20 wider-labels">
```
