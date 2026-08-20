#!/usr/bin/python3
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango
from .google_tasks import GoogleTasks


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "desktop-todo"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "desktop-todo"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_FILE = DATA_DIR / "tasks.json"


def read_config():
    defaults = {
        "markdown_file": str(DATA_DIR / "tasks.md"),
        "google_sync": False,
        "google_task_list": "Desktop Todo",
        "x": 88,
        "y": 72,
        "max_width": 350,
    }
    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            defaults.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


APP_CONFIG = read_config()
MARKDOWN_TODO = Path(os.path.expanduser(APP_CONFIG["markdown_file"]))
TASK_LINE = re.compile(
    r"^(\s*)-\s*\[([ xX])\]\s*(.*?)\s*(?:<!--\s*google-task:([^\s>]+)\s*-->)?\s*$"
)
DONE_HEADING = re.compile(r"^#\s+DONE:?\s*$", re.IGNORECASE)
DATE_HEADING = re.compile(r"^##\s+(.+?)\s*$")


CSS = b"""
window { background-color: transparent; }
#panel {
  background-color: rgba(24, 26, 31, 0.78);
  border: 1px solid rgba(138, 180, 248, 0.28);
  border-radius: 16px;
  padding: 18px;
}
#title { color: #8ab4f8; font-size: 20px; font-weight: bold; }
#empty { color: #9aa0a6; padding: 14px 0; }
.header-row { min-height: 34px; }
.add-row { min-height: 48px; }
.task-row { min-height: 27px; }
.footer-row { min-height: 28px; }
entry {
  color: #f1f3f4;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  padding: 8px;
}
button { border-radius: 8px; }
.add-button { color: #202124; background: #8ab4f8; font-weight: bold; }
.new-task-button {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  padding: 9px;
}
.new-task-button label { color: #ffffff; }
.sync-button { color: #202124; background: #8ab4f8; }
.sync-button label { color: #202124; }
.task-check { font-size: 14px; }
.task-check label { color: #ffffff; }
.task-check.completed label { color: #b0b4ba; text-decoration: line-through; }
.delete-button { color: #9aa0a6; background: transparent; border: 0; padding: 2px 7px; }
.delete-button label { color: #9aa0a6; }
.reorder-button { color: #8b9098; background: transparent; border: 0; padding: 1px 3px; }
.reorder-button label { color: #8b9098; }
.reorder-button:disabled { color: #454950; background: transparent; }
.reorder-button:disabled label { color: #454950; }
.clear-button {
  color: #d2d5da;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 7px;
  padding: 4px 8px;
}
.clear-button label { color: #d2d5da; }
"""


class TodoWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Desktop Todo")
        self.settings = self.load_settings()
        self.google = GoogleTasks(APP_CONFIG["google_task_list"])
        self.syncing = False
        self.editor_window = None
        self.archive = self.read_archive()
        self.tasks = self.load_tasks()
        self.markdown_mtime = self.markdown_timestamp()
        self.set_default_size(self.settings["max_width"] or 350, 100)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_below(True)
        self.set_accept_focus(False)
        self.stick()

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_name("panel")
        self.add(panel)

        header = Gtk.Box(spacing=8)
        header.get_style_context().add_class("header-row")
        title = Gtk.Label(label="MY TASKS", xalign=0)
        title.set_name("title")
        title.set_hexpand(True)
        header.pack_start(title, True, True, 0)
        self.sync_button = Gtk.Button(label="⟳")
        self.sync_button.get_style_context().add_class("sync-button")
        self.sync_button.set_tooltip_text("Connect or sync Google Tasks")
        self.sync_button.connect("clicked", self.google_clicked)
        header.pack_start(self.sync_button, False, False, 0)
        self.sync_button.set_no_show_all(not APP_CONFIG["google_sync"])
        self.sync_button.set_visible(APP_CONFIG["google_sync"])
        panel.pack_start(header, False, False, 0)

        self.sync_status = Gtk.Label(label="Local", xalign=0)
        self.sync_status.set_name("empty")
        panel.pack_start(self.sync_status, False, False, 0)

        add_box = Gtk.Box(spacing=8)
        add_box.get_style_context().add_class("add-row")
        add_button = Gtk.Button(label="+  Add task")
        add_button.set_hexpand(True)
        add_button.get_style_context().add_class("new-task-button")
        add_button.set_tooltip_text("Add task")
        add_button.connect("clicked", self.show_task_editor)
        add_box.pack_start(add_button, True, True, 0)
        panel.pack_start(add_box, False, False, 0)

        self.task_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        panel.pack_start(self.task_box, False, False, 0)

        self.clear_button = Gtk.Button(label="Archive completed")
        self.clear_button.set_halign(Gtk.Align.END)
        self.clear_button.get_style_context().add_class("clear-button")
        self.clear_button.get_style_context().add_class("footer-row")
        self.clear_button.connect("clicked", self.clear_completed)
        panel.pack_start(self.clear_button, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", lambda *_: GLib.idle_add(self.place_window))
        self.render_tasks()
        GLib.timeout_add_seconds(60, self.auto_sync)
        GLib.timeout_add_seconds(3, self.check_markdown)
        if APP_CONFIG["google_sync"] and self.google.authorized:
            GLib.idle_add(self.sync_google)
        GLib.timeout_add(80, self.enforce_below)

    def load_tasks(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if MARKDOWN_TODO.exists():
            tasks = self.read_markdown()
            if tasks is not None:
                self.write_tasks(tasks)
                return tasks
        if DATA_FILE.exists():
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                data = data if isinstance(data, list) else []
                self.write_tasks(data)
                return data
            except (OSError, json.JSONDecodeError):
                return []

        tasks = []
        self.write_tasks(tasks)
        return tasks

    @staticmethod
    def load_settings():
        defaults = {"x": APP_CONFIG["x"], "y": APP_CONFIG["y"],
                    "max_width": APP_CONFIG["max_width"]}
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            defaults.update({key: int(data[key]) for key in ("x", "y") if key in data})
            if "max_width" in data:
                defaults["max_width"] = (None if data["max_width"] is None
                                         else int(data["max_width"]))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return defaults

    def write_tasks(self, tasks):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = DATA_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(DATA_FILE)
        lines = ["# Desktop Todo", "",
                 "> Synced with the desktop widget and Google Tasks.", ""]
        for task in tasks:
            marker = "x" if task.get("done") else " "
            indent = "  " if task.get("level") else ""
            text = str(task.get("text", "")).replace("\n", " ").strip()
            google_id = task.get("google_id")
            suffix = f" <!-- google-task:{google_id} -->" if google_id else ""
            lines.append(f"{indent}- [{marker}] {text}{suffix}")
        if self.archive:
            lines.extend(["", "# DONE:"])
            for group in self.archive:
                lines.extend(["", f"## {group['date']}"])
                for task in group["tasks"]:
                    indent = "  " if task.get("level") else ""
                    text = str(task.get("text", "")).replace("\n", " ").strip()
                    google_id = task.get("google_id")
                    suffix = f" <!-- google-task:{google_id} -->" if google_id else ""
                    lines.append(f"{indent}- [x] {text}{suffix}")
        MARKDOWN_TODO.parent.mkdir(parents=True, exist_ok=True)
        temporary_md = MARKDOWN_TODO.with_suffix(".md.tmp")
        temporary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary_md.replace(MARKDOWN_TODO)

    @staticmethod
    def read_markdown():
        try:
            tasks = []
            in_done = False
            for line in MARKDOWN_TODO.read_text(encoding="utf-8").splitlines():
                if DONE_HEADING.match(line.strip()):
                    in_done = True
                    continue
                if in_done:
                    continue
                match = TASK_LINE.match(line)
                if match:
                    task = {"text": match.group(3).strip(),
                            "done": match.group(2).lower() == "x",
                            "level": 1 if match.group(1) else 0}
                    if match.group(4):
                        task["google_id"] = match.group(4)
                    tasks.append(task)
            return tasks
        except OSError:
            return None

    @staticmethod
    def read_archive():
        try:
            groups = []
            current = None
            in_done = False
            for line in MARKDOWN_TODO.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if DONE_HEADING.match(stripped):
                    in_done = True
                    continue
                if not in_done:
                    continue
                heading = DATE_HEADING.match(stripped)
                if heading:
                    current = {"date": heading.group(1), "tasks": []}
                    groups.append(current)
                    continue
                match = TASK_LINE.match(line)
                if current is not None and match:
                    task = {"text": match.group(3).strip(), "done": True,
                            "level": 1 if match.group(1) else 0}
                    if match.group(4):
                        task["google_id"] = match.group(4)
                    current["tasks"].append(task)
            return [group for group in groups if group["tasks"]]
        except OSError:
            return []

    def archived_google_ids(self):
        return {task["google_id"] for group in self.archive
                for task in group["tasks"] if task.get("google_id")}

    @staticmethod
    def markdown_timestamp():
        try:
            return MARKDOWN_TODO.stat().st_mtime_ns
        except OSError:
            return 0

    def save_tasks(self):
        self.write_tasks(self.tasks)
        self.markdown_mtime = self.markdown_timestamp()

    def place_window(self):
        self.move(self.settings["x"], self.settings["y"])
        return False

    def enforce_below(self):
        self.set_keep_below(True)
        native_window = self.get_window()
        if native_window:
            native_window.set_keep_below(True)
        return False

    def show_task_editor(self, _widget=None, event=None):
        if self.editor_window:
            self.editor_window.destroy()
        editor = Gtk.Window(title="Add task")
        self.editor_window = editor
        editor.set_decorated(False)
        editor.set_resizable(False)
        editor.set_transient_for(self)
        editor.set_modal(True)
        editor.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        editor.set_skip_taskbar_hint(True)
        editor.set_accept_focus(True)
        editor.set_keep_above(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_name("panel")
        editor.add(box)
        label = Gtk.Label(label="ADD A TASK", xalign=0)
        label.set_name("title")
        box.pack_start(label, False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("What needs to be done?")
        entry.set_size_request(290, -1)
        entry.connect("activate", self.commit_task_editor)
        entry.connect("key-press-event", self.editor_key_press)
        box.pack_start(entry, False, False, 0)
        buttons = Gtk.Box(spacing=8)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: editor.destroy())
        add = Gtk.Button(label="Add")
        add.get_style_context().add_class("add-button")
        add.connect("clicked", self.commit_task_editor)
        buttons.pack_end(add, False, False, 0)
        buttons.pack_end(cancel, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        editor.connect("destroy", self.editor_destroyed)
        editor.show_all()
        editor.move(self.settings["x"] + 18, self.settings["y"] + 110)
        timestamp = event.get_time() if event is not None else Gdk.CURRENT_TIME
        editor.present_with_time(timestamp)
        editor.present()
        GLib.idle_add(entry.grab_focus)
        self.editor_entry = entry
        return True

    def editor_key_press(self, _entry, event):
        if event.keyval == Gdk.KEY_Escape and self.editor_window:
            self.editor_window.destroy()
            return True
        return False

    def editor_destroyed(self, *_args):
        self.editor_window = None
        return False

    def commit_task_editor(self, _widget):
        if not self.editor_window:
            return
        text = self.editor_entry.get_text().strip()
        if text:
            self.create_task(text)
            self.editor_window.destroy()

    def render_tasks(self):
        max_width = self.settings["max_width"]
        self.set_size_request(max_width or -1, -1)
        for child in self.task_box.get_children():
            self.task_box.remove(child)

        if not self.tasks:
            empty = Gtk.Label(label="No tasks yet", xalign=0)
            empty.set_name("empty")
            self.task_box.pack_start(empty, False, False, 0)

        for index, task in enumerate(self.tasks):
            row = Gtk.Box(spacing=5)
            row.get_style_context().add_class("task-row")
            check = Gtk.CheckButton(label=task["text"])
            check.set_margin_start(18 if task.get("level") else 0)
            check.set_active(bool(task.get("done")))
            check.set_hexpand(True)
            check.get_style_context().add_class("task-check")
            label = check.get_child()
            if max_width and isinstance(label, Gtk.Label):
                label.set_line_wrap(True)
                label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                label.set_max_width_chars(max(12, (max_width - 150) // 7))
            if task.get("done"):
                check.get_style_context().add_class("completed")
            check.connect("toggled", self.toggle_task, index)
            row.pack_start(check, True, True, 0)

            hierarchy = Gtk.Button(label="←" if task.get("level") else "↳")
            hierarchy.set_tooltip_text(
                "Move to top level" if task.get("level") else "Make subtask"
            )
            can_indent = (not task.get("level") and index > 0
                          and not self.has_children(index)
                          and self.parent_before(index) is not None)
            hierarchy.set_sensitive(bool(task.get("level")) or can_indent)
            hierarchy.get_style_context().add_class("reorder-button")
            hierarchy.connect("clicked", self.toggle_hierarchy, index)
            row.pack_start(hierarchy, False, False, 0)

            up = Gtk.Button(label="↑")
            up.set_tooltip_text("Move up")
            up.set_sensitive(self.can_move_task(index, -1))
            up.get_style_context().add_class("reorder-button")
            up.connect("clicked", self.move_task_step, index, -1)
            row.pack_start(up, False, False, 0)

            down = Gtk.Button(label="↓")
            down.set_tooltip_text("Move down")
            down.set_sensitive(self.can_move_task(index, 1))
            down.get_style_context().add_class("reorder-button")
            down.connect("clicked", self.move_task_step, index, 1)
            row.pack_start(down, False, False, 0)

            delete = Gtk.Button(label="×")
            delete.get_style_context().add_class("delete-button")
            delete.set_tooltip_text("Delete task")
            delete.connect("clicked", self.delete_task, index)
            row.pack_start(delete, False, False, 0)
            self.task_box.pack_start(row, False, False, 0)

        self.clear_button.set_visible(any(t.get("done") for t in self.tasks))
        self.task_box.show_all()
        self.clear_button.set_visible(any(t.get("done") for t in self.tasks))
        GLib.timeout_add(80, self.enforce_below)

    def move_task_step(self, _button, index, direction):
        if not self.can_move_task(index, direction):
            return
        task = self.tasks[index]
        if task.get("level"):
            target = index + direction
            self.tasks[index], self.tasks[target] = self.tasks[target], self.tasks[index]
        else:
            end = index + 1
            while end < len(self.tasks) and self.tasks[end].get("level"):
                end += 1
            block = self.tasks[index:end]
            if direction < 0:
                target = self.parent_before(index)
                self.tasks[index:end] = []
                self.tasks[target:target] = block
            else:
                next_end = end + 1
                while next_end < len(self.tasks) and self.tasks[next_end].get("level"):
                    next_end += 1
                next_block = self.tasks[end:next_end]
                self.tasks[index:next_end] = next_block + block
        self.save_tasks()
        self.render_tasks()

        if APP_CONFIG["google_sync"] and self.google.authorized:
            self.run_google(self.sync_google_positions)

    def can_move_task(self, index, direction):
        if not 0 <= index < len(self.tasks):
            return False
        task = self.tasks[index]
        if task.get("level"):
            target = index + direction
            return (0 <= target < len(self.tasks)
                    and bool(self.tasks[target].get("level")))
        if direction < 0:
            return self.parent_before(index) is not None
        end = index + 1
        while end < len(self.tasks) and self.tasks[end].get("level"):
            end += 1
        return end < len(self.tasks)

    def sync_google_positions(self):
        for index, task in enumerate(self.tasks):
            if not task.get("google_id"):
                continue
            parent_id, previous_id = self.google_position(index)
            self.google.move_task(task["google_id"], previous_id, parent_id)

    def parent_before(self, index):
        for candidate in range(index - 1, -1, -1):
            if not self.tasks[candidate].get("level"):
                return candidate
        return None

    def has_children(self, index):
        return index + 1 < len(self.tasks) and bool(self.tasks[index + 1].get("level"))

    def google_position(self, index):
        task = self.tasks[index]
        parent_id = None
        boundary = -1
        if task.get("level"):
            parent_index = self.parent_before(index)
            if parent_index is not None:
                parent_id = self.tasks[parent_index].get("google_id")
                boundary = parent_index
        previous_id = None
        for candidate in range(index - 1, boundary, -1):
            if bool(self.tasks[candidate].get("level")) == bool(task.get("level")):
                previous_id = self.tasks[candidate].get("google_id")
                break
        return parent_id, previous_id

    def toggle_hierarchy(self, _button, index):
        task = self.tasks[index]
        if task.get("level"):
            task["level"] = 0
            end = index + 1
            while end < len(self.tasks) and self.tasks[end].get("level"):
                end += 1
            if end > index + 1:
                self.tasks.pop(index)
                self.tasks.insert(end - 1, task)
                index = end - 1
        elif self.parent_before(index) is not None and not self.has_children(index):
            task["level"] = 1
        else:
            return
        self.save_tasks()
        self.render_tasks()
        google_id = task.get("google_id")
        if APP_CONFIG["google_sync"] and self.google.authorized and google_id:
            parent_id, previous_id = self.google_position(index)
            self.run_google(
                lambda: self.google.move_task(google_id, previous_id, parent_id)
            )

    def create_task(self, text):
        text = text.strip()
        if not text:
            return
        task = {"text": text, "done": False, "level": 0}
        self.tasks.append(task)
        self.save_tasks()
        self.render_tasks()
        if APP_CONFIG["google_sync"] and self.google.authorized:
            self.run_google(
                lambda: self.google.create_task(text, False),
                lambda item: self.attach_google_id(task, item),
            )

    def toggle_task(self, check, index):
        self.tasks[index]["done"] = check.get_active()
        task = self.tasks[index]
        self.save_tasks()
        self.render_tasks()
        if APP_CONFIG["google_sync"] and self.google.authorized and task.get("google_id"):
            self.run_google(lambda: self.google.set_done(task["google_id"], task["done"]))

    def delete_task(self, _button, index):
        google_id = self.tasks[index].get("google_id")
        del self.tasks[index]
        self.save_tasks()
        self.render_tasks()
        if APP_CONFIG["google_sync"] and self.google.authorized and google_id:
            self.run_google(lambda: self.google.delete_task(google_id))

    def clear_completed(self, _button):
        completed = [task for task in self.tasks if task.get("done")]
        if not completed:
            return
        today = datetime.now().strftime("%d_%m_%Y")
        group = next((item for item in self.archive if item["date"] == today), None)
        if group is None:
            group = {"date": today, "tasks": []}
            self.archive.insert(0, group)
        completed_ids = {id(task) for task in completed}
        for index, task in enumerate(self.tasks):
            if id(task) not in completed_ids:
                continue
            archived = dict(task)
            parent_index = self.parent_before(index) if task.get("level") else None
            if parent_index is None or id(self.tasks[parent_index]) not in completed_ids:
                archived["level"] = 0
            group["tasks"].append(archived)
        self.tasks = [task for task in self.tasks if not task.get("done")]
        self.save_tasks()
        self.render_tasks()

    def set_sync_status(self, text):
        self.sync_status.set_text(text)
        return False

    def run_google(self, operation, success=None):
        def worker():
            try:
                result = operation()
                if success:
                    GLib.idle_add(success, result)
                GLib.idle_add(self.set_sync_status, "Google Tasks synced")
            except Exception as exc:
                GLib.idle_add(self.set_sync_status, "Error: " + str(exc)[:90])
        threading.Thread(target=worker, daemon=True).start()

    def attach_google_id(self, task, item):
        task["google_id"] = item["id"]
        self.save_tasks()
        return False

    def google_clicked(self, _button):
        if not APP_CONFIG["google_sync"]:
            return
        if self.google.authorized:
            self.sync_google()
            return
        self.set_sync_status("Authorize access in your browser...")

        def authorize_and_sync():
            self.google.authorize()
            return self.google.merge(self.tasks, self.archived_google_ids())
        self.run_google(authorize_and_sync, self.apply_google_tasks)

    def sync_google(self):
        if not APP_CONFIG["google_sync"] or self.syncing or not self.google.authorized:
            return False
        self.syncing = True
        self.set_sync_status("Syncing...")

        def worker():
            try:
                tasks = self.google.merge(self.tasks, self.archived_google_ids())
                GLib.idle_add(self.apply_google_tasks, tasks)
            except Exception as exc:
                GLib.idle_add(self.sync_failed, exc)
        threading.Thread(target=worker, daemon=True).start()
        return False

    def apply_google_tasks(self, tasks):
        self.tasks = tasks
        self.save_tasks()
        self.render_tasks()
        self.syncing = False
        self.set_sync_status("Google Tasks synced")
        return False

    def sync_failed(self, error):
        self.syncing = False
        self.set_sync_status("Error: " + str(error)[:90])
        return False

    def auto_sync(self):
        if APP_CONFIG["google_sync"] and self.google.authorized:
            self.sync_google()
        return True

    def check_markdown(self):
        timestamp = self.markdown_timestamp()
        if not timestamp or timestamp == self.markdown_mtime:
            return True
        incoming = self.read_markdown()
        incoming_archive = self.read_archive()
        self.markdown_mtime = timestamp
        if incoming is None or incoming == self.tasks:
            self.archive = incoming_archive
            return True

        old_by_id = {task.get("google_id"): task for task in self.tasks
                     if task.get("google_id")}
        new_ids = {task.get("google_id") for task in incoming if task.get("google_id")}
        archived_ids = {task.get("google_id") for group in incoming_archive
                        for task in group["tasks"] if task.get("google_id")}
        deleted = [item for item in old_by_id
                   if item not in new_ids and item not in archived_ids]
        changed = [task for task in incoming if task.get("google_id") in old_by_id
                   and (task.get("text") != old_by_id[task["google_id"]].get("text")
                        or bool(task.get("done")) != bool(old_by_id[task["google_id"]].get("done")))]
        hierarchy_changed = [index for index, task in enumerate(incoming)
                             if task.get("google_id") in old_by_id
                             and bool(task.get("level")) != bool(
                                 old_by_id[task["google_id"]].get("level"))]
        self.tasks = incoming
        self.archive = incoming_archive
        self.save_tasks()
        self.render_tasks()
        self.set_sync_status("Obsidian changes detected")

        if APP_CONFIG["google_sync"] and self.google.authorized:
            def update_google():
                for task_id in deleted:
                    self.google.delete_task(task_id)
                for task in changed:
                    self.google.update_task(task["google_id"], task["text"], task["done"])
                for index in hierarchy_changed:
                    task = self.tasks[index]
                    parent_id, previous_id = self.google_position(index)
                    self.google.move_task(task["google_id"], previous_id, parent_id)
                return self.google.merge(self.tasks, self.archived_google_ids())
            self.run_google(update_google, self.apply_google_tasks)
        return True


def main():
    window = TodoWindow()
    window.show_all()
    window.clear_button.set_visible(any(t.get("done") for t in window.tasks))
    if APP_CONFIG["google_sync"] and window.google.configured and not window.google.authorized:
        GLib.idle_add(window.google_clicked, None)
    Gtk.main()


if __name__ == "__main__":
    main()
