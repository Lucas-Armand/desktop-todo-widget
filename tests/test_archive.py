import tempfile
import unittest
from pathlib import Path

from desktop_todo import app


class MarkdownArchiveTests(unittest.TestCase):
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
                    [{"text": "Still active", "done": False}],
                    app.TodoWindow.read_markdown(),
                )
                self.assertEqual(store.archive, app.TodoWindow.read_archive())
            finally:
                app.DATA_DIR, app.DATA_FILE, app.MARKDOWN_TODO = original


if __name__ == "__main__":
    unittest.main()
