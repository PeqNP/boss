# BOSS Prompt Starting Guide

- Read the main [README.md](/README.md), and follow all links, to understand what BOSS is and how to build a BOSS app
- Read [tetsuo.md](/docs/prompt/tetsuo.md) for software development best practices and expectations of how software should be developed. If there is a conflict with the instructions in tetsuo.md, to any other documentation provided hereafter, prefer the standards defined hereafter.
- Ignore all files listed in [ignore.md](/docs/prompt/ignore.md)
- Design apps using the same principles following the Macintosh Human Interface Guidelines (1992 edition). [Reference](/docs/HIGuidelines.pdf). BOSS uses the classic black-and-white / 1-bit era feel of System 7 apps. Emphasize direct manipulation, desktop metaphor, consistent menu commands, modal dialogs only when necessary, forgiving actions with undo, standard controls (e.g., radio buttons, checkboxes, scroll arrows). BOSS doesn't use modern Aqua/flat elements.
- Use [coding-style.md](/docs/coding-style.md) as a reference on how to format code.
- [code-generation-guidelines.md](/docs/prompt/code-generation-guidlines.md) provides guidlines on how to read, and use, the BOSS APIs.
- The public BOSS API is located at `/public/boss/`. Any application may interact with OS features using:
  - `os`: Provides OS-level functions such as sign in, clipboard functions, or launching a deeplink
  - `os.network`: Provides API to make network calls to backend services
  - `os.notification`: Forwards app/system events and notifications to the OS
  - `os.ui`: Provides access to OS UI features
  - `os.ui.desktop`: Provides API to interact with desktop
  - `os.ui.notification`: Provides API to display notifications from the BOSS system or an app
