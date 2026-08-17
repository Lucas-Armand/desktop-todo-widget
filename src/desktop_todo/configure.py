#!/usr/bin/python3
import json
import os
import sys
from pathlib import Path


CONFIG_FILE = (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
               / "desktop-todo" / "config.json")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("position", "width"):
        raise SystemExit("Usage: desktop-todo position X Y | width PIXELS|auto")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}

    if sys.argv[1] == "position":
        if len(sys.argv) != 4:
            raise SystemExit("Usage: desktop-todo position X Y")
        try:
            x, y = int(sys.argv[2]), int(sys.argv[3])
        except ValueError:
            raise SystemExit("X and Y must be integers")
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            raise SystemExit("X and Y must be between 0 and 10000")
        config.update({"x": x, "y": y})
        message = f"Position saved: x={x}, y={y}"
    else:
        if len(sys.argv) != 3:
            raise SystemExit("Usage: desktop-todo width PIXELS|auto")
        if sys.argv[2].lower() == "auto":
            config["max_width"] = None
            message = "Maximum width disabled"
        else:
            try:
                width = int(sys.argv[2])
            except ValueError:
                raise SystemExit("Width must be an integer or auto")
            if not 280 <= width <= 1200:
                raise SystemExit("Width must be between 280 and 1200 pixels")
            config["max_width"] = width
            message = f"Maximum width saved: {width}px"

    temporary = CONFIG_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(CONFIG_FILE)
    print(message)


if __name__ == "__main__":
    main()
