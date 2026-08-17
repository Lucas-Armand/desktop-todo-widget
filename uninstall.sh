#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
rm -rf -- "$DATA_HOME/desktop-todo/app"
rm -f -- "$HOME/.local/bin/desktop-todo" "$CONFIG_HOME/autostart/desktop-todo.desktop"
echo "Application removed. Configuration, tasks, and OAuth tokens were preserved."
