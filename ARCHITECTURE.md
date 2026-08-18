# Architecture

## Principle: minimal before extensible

This is a developer starter, not a task-management framework. It deliberately
keeps the implementation to three small modules:

```text
src/desktop_todo/
├── app.py             # GTK UI, configuration, Markdown storage
├── configure.py       # validated position and width commands
└── google_tasks.py    # optional OAuth PKCE and Google REST calls
```

`app.py` never implements HTTP. `google_tasks.py` never edits Markdown. Secrets,
task data, and user configuration live outside the repository. Local-only mode
is the default.

## Local model and files

A task has `text`, `done`, and optionally `google_id`. Remote IDs are stored in
HTML comments on their Markdown lines, which keeps the note readable in
Obsidian. A small JSON file mirrors the current state for recovery.

Completed tasks remain active until the user archives them. Archiving moves
them under `# DONE:` and a `## DD_MM_YYYY` heading. Archived remote IDs are
excluded from subsequent merges so completed Google Tasks do not reappear.

The configured Markdown file must be a dedicated note. The widget owns and
atomically rewrites its full contents; it does not preserve unrelated prose.

## Current sync rules

1. Save a user action locally before attempting a network request.
2. Display a network error without discarding the local file.
3. During merge, link an initial unlinked task once by identical text/status.
4. Use remote IDs for later updates, moves, completion, and deletion.

This starter intentionally has no offline operation queue or conflict-resolution
engine. Add those before relying on synchronization for important data.

## Desktop behavior

GTK 3 and GNOME/X11 support positioning and EWMH hints such as `DOCK`, `STICKY`,
and taskbar skipping. Wayland restricts client-controlled placement and stacking,
so identical behavior is not promised there.
