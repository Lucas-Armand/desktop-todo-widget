import tempfile
import unittest
from pathlib import Path

from desktop_todo import app


class MarkdownArchiveTests(unittest.TestCase):
    def test_markdown_indentation_round_trips_as_subtask(self):
        with tempfile.TemporaryDirectory() as directory:
            original = app.MARKDOWN_TODO
            app.MARKDOWN_TODO = Path(directory) / "tasks.md"
            try:
                app.MARKDOWN_TODO.write_text(
                    "# Desktop Todo\n\n- [ ] Topic\n  - [ ] Subtopic\n",
                    encoding="utf-8",
                )
                self.assertEqual(
                    [
                        {"text": "Topic", "done": False, "level": 0},
                        {"text": "Subtopic", "done": False, "level": 1},
                    ],
                    app.TodoWindow.read_markdown(),
                )
            finally:
                app.MARKDOWN_TODO = original

    def test_top_level_reorder_moves_its_subtasks_as_a_block(self):
        store = type("Store", (), {})()
        store.tasks = [
            {"text": "Topic A", "level": 0},
            {"text": "Child A", "level": 1},
            {"text": "Topic B", "level": 0},
        ]
        store.can_move_task = app.TodoWindow.can_move_task.__get__(store)
        store.parent_before = app.TodoWindow.parent_before.__get__(store)
        store.save_tasks = lambda: None
        store.render_tasks = lambda: None
        store.google = type("Google", (), {"authorized": False})()

        app.TodoWindow.move_task_step(store, None, 0, 1)

        self.assertEqual(["Topic B", "Topic A", "Child A"],
                         [task["text"] for task in store.tasks])

    def test_outdent_does_not_adopt_following_siblings(self):
        store = type("Store", (), {})()
        store.tasks = [
            {"text": "Topic", "level": 0},
            {"text": "First child", "level": 1},
            {"text": "Second child", "level": 1},
        ]
        store.save_tasks = lambda: None
        store.render_tasks = lambda: None
        store.google = type("Google", (), {"authorized": False})()

        app.TodoWindow.toggle_hierarchy(store, None, 1)

        self.assertEqual(["Topic", "Second child", "First child"],
                         [task["text"] for task in store.tasks])
        self.assertEqual([0, 1, 0], [task["level"] for task in store.tasks])

    def test_clear_completed_archives_instead_of_deleting(self):
        store = type("Store", (), {})()
        store.tasks = [
            {"text": "Keep", "done": False},
            {"text": "Archive", "done": True, "google_id": "remote-1"},
        ]
        store.archive = []
        store.save_tasks = lambda: None
        store.render_tasks = lambda: None

        app.TodoWindow.clear_completed(store, None)

        self.assertEqual([{"text": "Keep", "done": False}], store.tasks)
        self.assertEqual("Archive", store.archive[0]["tasks"][0]["text"])
        self.assertRegex(store.archive[0]["date"], r"^\d{2}_\d{2}_\d{4}$")

    def test_archived_tasks_are_written_but_not_loaded_as_active(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = (app.DATA_DIR, app.DATA_FILE, app.MARKDOWN_TODO)
            app.DATA_DIR = root
            app.DATA_FILE = root / "tasks.json"
            app.MARKDOWN_TODO = root / "tasks.md"
            try:
                store = type("Store", (), {})()
                store.archive = [{
                    "date": "18_08_2026",
                    "tasks": [{"text": "Recorded result", "done": True,
                               "google_id": "remote-1"}],
                }]
                app.TodoWindow.write_tasks(
                    store, [{"text": "Still active", "done": False}]
                )
                markdown = app.MARKDOWN_TODO.read_text(encoding="utf-8")
                self.assertIn("# DONE:", markdown)
                self.assertIn("## 18_08_2026", markdown)
                self.assertEqual(
                    [{"text": "Still active", "done": False, "level": 0}],
                    app.TodoWindow.read_markdown(),
                )
                expected_archive = [{
                    "date": "18_08_2026",
                    "tasks": [{"text": "Recorded result", "done": True,
                               "level": 0, "google_id": "remote-1"}],
                }]
                self.assertEqual(expected_archive, app.TodoWindow.read_archive())
            finally:
                app.DATA_DIR, app.DATA_FILE, app.MARKDOWN_TODO = original


if __name__ == "__main__":
    unittest.main()
