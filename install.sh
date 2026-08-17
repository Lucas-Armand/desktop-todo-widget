#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_HOME="$HOME/.local/bin"
APP_HOME="$DATA_HOME/desktop-todo/app"
AUTOSTART_HOME="$CONFIG_HOME/autostart"

[[ -x /usr/bin/python3 ]] || { echo "Missing dependency: /usr/bin/python3" >&2; exit 1; }
/usr/bin/python3 -c 'import gi, requests; gi.require_version("Gtk", "3.0")' 2>/dev/null || {
  echo "Install: sudo apt install python3-gi gir1.2-gtk-3.0 python3-requests" >&2
  exit 1
}

mkdir -p "$APP_HOME" "$BIN_HOME" "$CONFIG_HOME/desktop-todo" "$AUTOSTART_HOME"
cp -R "$SOURCE_DIR/src/desktop_todo" "$APP_HOME/"
if [[ ! -f "$CONFIG_HOME/desktop-todo/config.json" ]]; then
  cp "$SOURCE_DIR/config.example.json" "$CONFIG_HOME/desktop-todo/config.json"
fi
sed "s|@APP_HOME@|$APP_HOME|g" "$SOURCE_DIR/scripts/desktop-todo.in" > "$BIN_HOME/desktop-todo"
chmod 755 "$BIN_HOME/desktop-todo"
sed "s|@LAUNCHER@|$BIN_HOME/desktop-todo|g" "$SOURCE_DIR/scripts/desktop-todo.desktop.in" > "$AUTOSTART_HOME/desktop-todo.desktop"
chmod 644 "$AUTOSTART_HOME/desktop-todo.desktop"

echo "Installed. Run: desktop-todo"
