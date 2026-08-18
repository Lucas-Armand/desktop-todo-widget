import unittest

from desktop_todo.google_tasks import GoogleTasks


class FakeGoogleTasks(GoogleTasks):
    def __init__(self, remote):
        super().__init__("Desktop Todo")
        self.remote = list(remote)
        self.created = []

    def list_tasks(self):
        return list(self.remote)

    def create_task(self, text, done=False):
        item = {
            "id": f"new-{len(self.created) + 1}",
            "title": text,
            "status": "completed" if done else "needsAction",
        }
        self.created.append(item)
        return item


class MergeTests(unittest.TestCase):
    def test_links_matching_initial_task_without_duplicate(self):
        client = FakeGoogleTasks([
            {"id": "remote-1", "title": "Review", "status": "needsAction"}
        ])
        merged = client.merge([{"text": "Review", "done": False}])
        self.assertEqual("remote-1", merged[0]["google_id"])
        self.assertEqual([], client.created)

    def test_creates_missing_local_task(self):
        client = FakeGoogleTasks([])
        merged = client.merge([{"text": "Write docs", "done": False}])
        self.assertEqual("new-1", merged[0]["google_id"])
        self.assertEqual(1, len(client.created))

    def test_imports_unclaimed_remote_task(self):
        client = FakeGoogleTasks([
            {"id": "remote-1", "title": "From phone", "status": "completed"}
        ])
        merged = client.merge([])
        self.assertEqual(
            [{"text": "From phone", "done": True, "google_id": "remote-1"}],
            merged,
        )

    def test_does_not_restore_archived_remote_task(self):
        client = FakeGoogleTasks([
            {"id": "archived-1", "title": "Already done", "status": "completed"}
        ])
        self.assertEqual([], client.merge([], {"archived-1"}))


if __name__ == "__main__":
    unittest.main()
