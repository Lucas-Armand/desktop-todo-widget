# Google Tasks Setup

Google synchronization is optional. Local Markdown mode should work without a
Google account, Cloud project, billing account, or OAuth credential.

## Cost and quota

Google currently documents a courtesy limit of 50,000 Tasks API queries per
day. A personal desktop widget syncing approximately once per minute should be
far below that limit. Do not request a quota increase or enable billing merely
for this starter project.

Official reference: [Google Tasks API quotas and limits](https://developers.google.com/workspace/tasks/limits).

## 1. Create or select a Google Cloud project

Open the [Google Cloud Console](https://console.cloud.google.com/) and create a
small dedicated project, or select one you control. A dedicated project makes
revocation and cleanup easier.

## 2. Enable Google Tasks API

Open the [Google Tasks API library page](https://console.cloud.google.com/apis/library/tasks.googleapis.com)
and select **Enable**.

## 3. Configure Google Auth Platform

Open **Google Auth Platform** in the project:

1. Set an application name such as `Desktop Todo Widget`.
2. Add your support and developer-contact email.
3. Choose **External** unless your managed Workspace organization specifically
   requires an Internal app.
4. Keep the app in Testing mode for personal development.
5. Under **Audience**, add every Google account that will authorize the widget
   as a test user.

If Google returns `403 access_denied` and says the app is limited to approved
testers, the signed-in account is missing from this list.

## 4. Create a Desktop OAuth client

Under **Clients**, create an OAuth client with application type **Desktop app**.
Do not create an API key, service account, web client, Android client, or Chrome
extension client.

Download the JSON and install it locally:

```bash
mkdir -p ~/.config/desktop-todo
install -m 600 ~/Downloads/client_secret_*.json \
  ~/.config/desktop-todo/client_secret.json
```

Confirm that the wildcard matched exactly one intended file before running the
command. Never rename or copy this credential into the Git repository.

## 5. Enable synchronization

Copy `config.example.json` to `~/.config/desktop-todo/config.json`, set
`google_sync` to `true`, and choose a dedicated `google_task_list` name.

On first launch, the widget should:

1. open Google's authorization page in the system browser;
2. request the official Tasks write scope;
3. receive the callback on a temporary `127.0.0.1` port;
4. store the resulting token with mode `0600`;
5. find or create the configured Google Tasks list;
6. merge local tasks without duplicating identical initial entries.

The requested scope permits creating, editing, organizing, and deleting Tasks:
[Google Tasks authorization scopes](https://developers.google.com/workspace/tasks/auth).

## 6. Find the list on mobile

In the Google Tasks mobile app, select the same Google account used during
OAuth authorization. Open the list selector and choose the configured list
name. Completed tasks may appear in a collapsed section.

## Troubleshooting

### The browser does not open

Ensure `gio` or `xdg-open` is available and that the widget runs inside the
graphical session. The authorization URL is opened directly and is not stored.

### `403 access_denied`

Add the signed-in email under Google Auth Platform **Audience → Test users**,
then restart authorization.

### Tasks exist in the API but not on the phone

Check both the selected Google account and selected task list. The widget should
use a dedicated list rather than the default `My Tasks` list.

### Authorization stops working after testing

Testing-mode OAuth policies can affect refresh-token lifetime. Reauthorize or
review the current Google Auth Platform publishing settings. Do not bypass this
by storing a Google password or browser cookies.
