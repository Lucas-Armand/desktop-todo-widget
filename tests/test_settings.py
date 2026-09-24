import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_todo import app


@unittest.skipUnless(app.Gtk.init_check()[0], "Requires a graphical display")
class SettingsTests(unittest.TestCase):
    def test_apply_preserves_tasks_and_sync_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            note = root / "tasks.md"
            settings = dict(app.APP_CONFIG, google_sync=False,
                            markdown_file=str(note), custom_setting="preserve")
            config.write_text(json.dumps(settings))
            note.write_text("# Desktop Todo\n\n- [ ] Keep this task\n")
            with patch.multiple(app, CONFIG_FILE=config, DATA_DIR=root,
                                DATA_FILE=root / "tasks.json", MARKDOWN_TODO=note,
                                APP_CONFIG=settings):
                window = app.TodoWindow()
                try:
                    original = note.read_bytes()
                    window.show_settings()
                    dialog = window.settings_window
                    grid = dialog.get_content_area().get_children()[0]
                    grid.get_child_at(1, 0).set_value(12)
                    grid.get_child_at(1, 1).set_value(400)
                    # Simulate an external config update while the dialog is open.
                    current = json.loads(config.read_text())
                    current['google_task_list'] = 'Preserved list'
                    config.write_text(json.dumps(current))
                    dialog.response(app.Gtk.ResponseType.APPLY)
                    saved = json.loads(config.read_text())
                    self.assertEqual(saved, dict(current, font_size=12, max_width=400))
                    self.assertEqual(note.read_bytes(), original)
                    self.assertEqual(window.settings['font_size'], 12)
                    self.assertIsNone(window.settings_window)
                    window.show_settings()
                    dialog = window.settings_window
                    dialog.get_content_area().get_children()[0].get_child_at(0, 2).set_active(True)
                    dialog.response(app.Gtk.ResponseType.APPLY)
                    self.assertIsNone(json.loads(config.read_text())['max_width'])
                    window.show_settings()
                    dialog = window.settings_window
                    dialog.get_content_area().get_children()[0].get_child_at(1, 0).set_value(20)
                    dialog.response(app.Gtk.ResponseType.CANCEL)
                    self.assertEqual(json.loads(config.read_text())['font_size'], 12)
                    self.assertEqual(note.read_bytes(), original)
                finally:
                    window.disconnect_by_func(app.Gtk.main_quit)
                    window.destroy()
