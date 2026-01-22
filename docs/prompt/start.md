# BOSS Prompt Starting Guide

- Read the main [README.md](/README.md) to understand what BOSS is and links to all documentation on how to build a BOSS app
- Read [tetsuo.md](/docs/prompt/tetsuo.md) for software development best practices and expectations of how software should be developed. If there is a conflict with the instructions in tetsuo.md, to any other documentation provided hereafter, prefer the standards defined hereafter.
- Read [App Specification](/docs/app-spec.md) to understand how high-level UI/UX specs can be translated into their respective BOSS source.
- Applications can follow the original Classic macOS [Human Interface Guidelines](/docs/HIGuidelines.pdf) when designing UI. If there is a more simple UI/UX alternative, please use it instead. Even though the PDF explicitly states it's for anyone programming for a Macintosh computer, the UI/UX of BOSS closely matches that of the Classic macOS 2 UI/UX. Therefore, the concepts explained in the HIG are (mostly) interchangeable with BOSS.
- Use [coding-style.md](/docs/coding-style.md) as a reference on how to format code.
- The public BOSS API is located at `/public/boss/*.js`. Any application may interact with OS features using:
  - `os`: Provides OS-level functions such as sign in, clipboard functions, or launching a deeplink
  - `os.network`: Provides API to make network calls to backend services
  - `os.notification`: Forwards app/system events and notifications to the OS
  - `os.ui`: Provides access to OS UI features
  - `os.ui.desktop`: Provides API to interact with desktop
  - `os.ui.notification`: Provides API to display notifications from the BOSS system or an app
