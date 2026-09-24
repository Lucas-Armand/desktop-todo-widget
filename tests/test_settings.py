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
                    grid.get_child_at(1, 3).set_active_id("green")
                    grid.get_child_at(1, 4).set_value(55)
                    # Simulate an external config update while the dialog is open.
                    current = json.loads(config.read_text())
                    current['google_task_list'] = 'Preserved list'
                    config.write_text(json.dumps(current))
                    dialog.response(app.Gtk.ResponseType.APPLY)
                    saved = json.loads(config.read_text())
                    self.assertEqual(saved, dict(current, font_size=12, max_width=400, color_theme="green", background_opacity=55, light_checkboxes=False))
                    self.assertEqual(note.read_bytes(), original)
                    self.assertEqual(window.settings['font_size'], 12)
                    self.assertEqual(app.TodoWindow.load_settings()["color_theme"], "green")
                    self.assertEqual(app.TodoWindow.load_settings()["background_opacity"], 55)
                    for theme_name in app.PALETTES:
                        window.settings["color_theme"] = theme_name
                        for opacity in (0, 55, 100):
                            window.settings["background_opacity"] = opacity
                            window.apply_appearance()
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
                    window.show_settings()
                    dialog = window.settings_window
                    grid = dialog.get_content_area().get_children()[0]
                    grid.get_child_at(1, 3).set_active_id("original")
                    self.assertFalse(grid.get_child_at(1, 0).get_sensitive())
                    self.assertFalse(grid.get_child_at(1, 4).get_sensitive())
                    dialog.response(app.Gtk.ResponseType.APPLY)
                    restored = json.loads(config.read_text())
                    self.assertEqual(restored["color_theme"], "original")
                    self.assertEqual(restored["font_size"], 14)
                    self.assertEqual(restored["background_opacity"], 78)
                    self.assertNotIn(b"#todo-widget", window.appearance_provider.to_string().encode())
                    self.assertEqual(note.read_bytes(), original)
                    window.show_settings()
                    dialog = window.settings_window
                    dialog.get_content_area().get_children()[0].get_child_at(0, 5).set_active(True)
                    dialog.response(app.Gtk.ResponseType.APPLY)
                    self.assertTrue(app.TodoWindow.load_settings()["light_checkboxes"])
                    self.assertEqual(window.settings["color_theme"], "original")
                    self.assertIn("#todo-widget .task-check check", window.appearance_provider.to_string())
                    self.assertEqual(note.read_bytes(), original)
                    restored.pop("color_theme")
                    config.write_text(json.dumps(restored))
                    self.assertEqual(app.TodoWindow.load_settings()["color_theme"], "original")
                finally:
                    window.disconnect_by_func(app.Gtk.main_quit)
                    window.destroy()
