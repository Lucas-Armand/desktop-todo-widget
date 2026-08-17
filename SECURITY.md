# Security Policy

## Scope and maturity

This repository is a developer starter and has not received an independent
security audit. Review the code and OAuth scopes before using it with important
or sensitive tasks.

## Sensitive files

Never commit or attach any of the following:

- OAuth client JSON files;
- access or refresh tokens;
- real task data or Markdown notes;
- personal vault paths and email addresses;
- logs or screenshots containing private tasks.

Recommended local locations:

```text
~/.config/desktop-todo/client_secret.json
~/.local/share/desktop-todo/google_token.json
```

Both files should have mode `0600`.

## OAuth requirements

- Use the system browser, never an embedded username/password form.
- Use Authorization Code flow for Desktop apps with PKCE.
- Generate and validate a cryptographically random `state` value.
- Bind the callback server to `127.0.0.1`, choose a random port, and stop it
  immediately after authorization or timeout.
- Request only `https://www.googleapis.com/auth/tasks` when write access is
  enabled.
- Never log authorization URLs, codes, access tokens, or refresh tokens.

## Local-data requirements

- Save Markdown before attempting remote synchronization.
- Use atomic writes.
- Use a dedicated Markdown note. The widget owns and rewrites its complete
  contents; do not point it at a note containing unrelated information.
- Treat note content as untrusted text; do not evaluate shell commands, Conky
  syntax, HTML, or Python contained in task titles.
- Avoid shell interpolation when launching the application or opening paths.

## Revocation and removal

Users can revoke access from their Google Account connections page. An
uninstaller should remove the local token only after explicit confirmation and
must preserve Markdown notes by default.

## Reporting a vulnerability

Do not include credentials or personal data in an issue. Provide a minimal
reproduction with synthetic tasks and redact identifiers from logs.
