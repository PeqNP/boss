# Omarchy Config

## Configure Input

- Swap "Caps Lock" with "Escape"
- Enable natural scrolling
- Configure scrolling speed

Super + alt + Space > Setup > Input

Add the following:

```
input {
  kb_options = caps:escape

  touchpad {
    natural_scrolle = yes
    scroll_factor = 0.2
  }
}

device {
  name = logitech-gaming-mouse-g400
  sensitivity = -0.8
}
```

### Configure Escape in VS code

- Open VS Code
- Ctrl+Shift+p
- Preferences: Open Keyboard Shortcuts
- Tap the "Open Keyboard Shortcuts (JSON)" button on top right
- Add the following

```
[
  {
    "key": "capslock",
    "command": "extension.vim_escape",
    "when": "editorTextFocus && vim.active && !inDebugRepl"
  }
]
```

## Show code blocks

```
n ~/.config/nvim/lua/config/options.lua
```

And add:

```
vim.opt.conceallevel = 0
```

## Configure Monitors

This moves all windows to connected monitor when clamshell is closed (laptops).

- Setup
- Monitors

```
env = GDK_SCALE,2
monitor=eDP-1,preferred,auto,auto
monitor=DP-2,2560x1440@120.00,0x0,1

# LAPTOP LID
bindl=,switch:on:Lid Switch,exec,hyprctl keyword monitor "eDP-1,disable"
bindl=,switch:off:Lid Switch,exec,hyprctl keyword monitor "eDP-1,preferred,auto,auto"
```
