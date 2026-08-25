import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_todo import google_tasks


class InvalidGrantResponse:
    ok = False
    status_code = 400
    text = '{"error":"invalid_grant"}'

    @staticmethod
    def json():
        return {"error": "invalid_grant",
                "error_description": "Token has been expired or revoked."}


class OAuthRecoveryTests(unittest.TestCase):
    def test_expired_refresh_token_is_removed_without_touching_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token = root / "google_token.json"
            client = root / "client_secret.json"
            tasks = root / "tasks.md"
            token.write_text(json.dumps({
                "access_token": "expired-access-token",
                "refresh_token": "expired-refresh-token",
                "expires_at": time.time() - 60,
            }), encoding="utf-8")
            client.write_text(json.dumps({"installed": {
                "client_id": "test-client",
                "client_secret": "test-secret",
            }}), encoding="utf-8")
            tasks.write_text("- [ ] Keep this task\n", encoding="utf-8")
            original = (google_tasks.TOKEN_FILE, google_tasks.CLIENT_FILE)
            google_tasks.TOKEN_FILE = token
            google_tasks.CLIENT_FILE = client
            try:
                with patch.object(google_tasks.requests, "post",
                                  return_value=InvalidGrantResponse()):
                    with self.assertRaises(google_tasks.GoogleAuthorizationExpired):
                        google_tasks.GoogleTasks()._access_token()
                self.assertFalse(token.exists())
                self.assertEqual("- [ ] Keep this task\n",
                                 tasks.read_text(encoding="utf-8"))
            finally:
                google_tasks.TOKEN_FILE, google_tasks.CLIENT_FILE = original


if __name__ == "__main__":
    unittest.main()
