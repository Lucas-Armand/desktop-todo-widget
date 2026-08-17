#!/usr/bin/python3
"""OAuth and Google Tasks REST access without additional Google packages."""
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "desktop-todo"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "desktop-todo"
CLIENT_FILE = CONFIG_DIR / "client_secret.json"
TOKEN_FILE = DATA_DIR / "google_token.json"
SCOPE = "https://www.googleapis.com/auth/tasks"
API = "https://tasks.googleapis.com/tasks/v1"


class GoogleTasksError(RuntimeError):
    pass


class GoogleTasks:
    def __init__(self, list_name="Desktop Todo"):
        self.list_name = list_name
        self.tasklist_id = None

    @property
    def configured(self):
        return CLIENT_FILE.exists()

    @property
    def authorized(self):
        return TOKEN_FILE.exists()

    def _client(self):
        try:
            data = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))["installed"]
            return data["client_id"], data.get("client_secret", "")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise GoogleTasksError("Invalid OAuth credential") from exc

    @staticmethod
    def _write_private(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)

    def authorize(self):
        client_id, client_secret = self._client()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        result = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                params = parse_qs(urlparse(handler.path).query)
                result.update({key: values[0] for key, values in params.items()})
                body = (
                    "<html><body style='font-family:sans-serif;padding:40px'>"
                    "<h2>Authorization complete</h2>"
                    "<p>You can close this tab and return to the widget.</p></body></html>"
                ).encode()
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)

            def log_message(self, _format, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 300
        redirect = f"http://127.0.0.1:{server.server_port}"
        query = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + query
        opener = shutil.which("gio") or shutil.which("xdg-open")
        if not opener:
            server.server_close()
            raise GoogleTasksError("Neither gio nor xdg-open is available")
        subprocess.Popen(
            [opener, "open", authorization_url] if Path(opener).name == "gio"
            else [opener, authorization_url],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        server.handle_request()
        server.server_close()
        if result.get("state") != state or "code" not in result:
            raise GoogleTasksError(result.get("error", "Authorization canceled"))
        response = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": result["code"],
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        }, timeout=30)
        self._check(response)
        token = response.json()
        token["expires_at"] = time.time() + token.get("expires_in", 3600)
        self._write_private(TOKEN_FILE, token)

    def _access_token(self):
        try:
            token = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GoogleTasksError("Google Tasks has not been authorized yet") from exc
        if token.get("expires_at", 0) > time.time() + 60:
            return token["access_token"]
        client_id, client_secret = self._client()
        response = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token.get("refresh_token"),
            "grant_type": "refresh_token",
        }, timeout=30)
        self._check(response)
        refreshed = response.json()
        token.update(refreshed)
        token["expires_at"] = time.time() + refreshed.get("expires_in", 3600)
        self._write_private(TOKEN_FILE, token)
        return token["access_token"]

    @staticmethod
    def _check(response):
        if response.ok:
            return
        try:
            message = response.json().get("error", {}).get("message") or response.text
        except (ValueError, AttributeError):
            message = response.text
        raise GoogleTasksError(f"Google returned {response.status_code}: {message[:180]}")

    def _request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = "Bearer " + self._access_token()
        response = requests.request(method, API + path, headers=headers, timeout=30, **kwargs)
        self._check(response)
        return response.json() if response.content else None

    def ensure_tasklist(self):
        if self.tasklist_id:
            return self.tasklist_id
        data = self._request("GET", "/users/@me/lists", params={"maxResults": 100})
        for item in data.get("items", []):
            if item.get("title") == self.list_name:
                self.tasklist_id = item["id"]
                return self.tasklist_id
        item = self._request("POST", "/users/@me/lists", json={"title": self.list_name})
        self.tasklist_id = item["id"]
        return self.tasklist_id

    def list_tasks(self):
        list_id = self.ensure_tasklist()
        items, page = [], None
        while True:
            params = {"maxResults": 100, "showCompleted": "true", "showHidden": "true"}
            if page:
                params["pageToken"] = page
            data = self._request("GET", f"/lists/{list_id}/tasks", params=params)
            items.extend(item for item in data.get("items", []) if not item.get("deleted"))
            page = data.get("nextPageToken")
            if not page:
                return items

    def create_task(self, text, done=False):
        body = {"title": text, "status": "completed" if done else "needsAction"}
        return self._request("POST", f"/lists/{self.ensure_tasklist()}/tasks", json=body)

    def set_done(self, task_id, done):
        body = {"status": "completed" if done else "needsAction"}
        return self._request("PATCH", f"/lists/{self.ensure_tasklist()}/tasks/{task_id}", json=body)

    def update_task(self, task_id, text, done):
        body = {"title": text, "status": "completed" if done else "needsAction"}
        return self._request("PATCH", f"/lists/{self.ensure_tasklist()}/tasks/{task_id}", json=body)

    def delete_task(self, task_id):
        self._request("DELETE", f"/lists/{self.ensure_tasklist()}/tasks/{task_id}")

    def move_task(self, task_id, previous_id=None):
        params = {"previous": previous_id} if previous_id else {}
        return self._request(
            "POST",
            f"/lists/{self.ensure_tasklist()}/tasks/{task_id}/move",
            params=params,
        )

    def merge(self, local_tasks):
        """Initial merge avoids duplicates; Google then becomes the remote source."""
        remote = self.list_tasks()
        by_id = {item["id"]: item for item in remote}
        claimed = set()
        merged = []
        for task in local_tasks:
            item = by_id.get(task.get("google_id"))
            if item is None and not task.get("google_id"):
                item = next((candidate for candidate in remote
                    if candidate["id"] not in claimed
                    and candidate.get("title", "") == task.get("text", "")
                    and (candidate.get("status") == "completed") == bool(task.get("done"))), None)
            if item is None:
                item = self.create_task(task.get("text", ""), bool(task.get("done")))
            claimed.add(item["id"])
            merged.append({"text": item.get("title", ""),
                           "done": item.get("status") == "completed",
                           "google_id": item["id"]})
        for item in remote:
            if item["id"] not in claimed:
                merged.append({"text": item.get("title", ""),
                               "done": item.get("status") == "completed",
                               "google_id": item["id"]})
        return merged
