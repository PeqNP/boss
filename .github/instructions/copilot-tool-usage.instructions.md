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
