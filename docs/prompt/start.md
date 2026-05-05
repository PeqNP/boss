# BOSS AI Code Generation Starting Guide

- Ignore all files listed in [ignore.md](/docs/prompt/ignore.md). If they are linked in any of the documents hereafter, they may be safely ignored.
- **Read [boss-reference.md](/docs/prompt/boss-reference.md) in full.** This is the primary reference document. It contains all critical information about building BOSS apps inline — project layout, app structure, controller patterns, OS APIs, UI components, backend conventions, and coding rules. Do not skip sections.
- Read [tetsuo.md](/docs/prompt/tetsuo.md) for software development best practices and expectations of how software should be developed. If there is a conflict with the instructions in tetsuo.md to any other documentation provided hereafter, prefer the standards defined hereafter.
- Design apps using the same principles following the Macintosh Human Interface Guidelines (1992 edition). BOSS uses the classic black-and-white / 1-bit era feel of System 7 apps. Emphasize direct manipulation, desktop metaphor, consistent menu commands, modal dialogs only when necessary, forgiving actions with undo, standard controls (e.g., radio buttons, checkboxes, scroll arrows). BOSS doesn't use modern Aqua/flat elements.
- Use [coding-style.md](/docs/coding-style.md) as a reference on how to format code.
- If the app you are working on has a `memory.md` file in its bundle directory (e.g. `/public/boss/app/<bundle_id>/memory.md`), read it before making any changes. It contains app-specific conventions, file locations, and decisions from previous sessions.
- Read [process.md](/docs/prompt/process.md) to understand the expected development workflow: layer responsibilities, when to write tests, test-first approach, and the required top-to-bottom development order.

