# Why This Starter Does Not Use Google Keep

Google Keep was the first integration considered because a Keep checklist is a
natural visual match for the widget. It was rejected for reliability and
security reasons.

## Official API mismatch

The official Google Keep API is described as an enterprise administration API.
Its documented note methods include create, get, list, and delete, but do not
provide the ordinary content-update operation needed to check, rename, or
reorder items in an existing personal checklist.

Official references:

- [Google Keep API overview](https://developers.google.com/workspace/keep/api/guides)
- [Google Keep REST reference](https://developers.google.com/workspace/keep/api/reference/rest)

That makes it a poor foundation for predictable two-way personal task sync.

## Why not use an unofficial library?

Unofficial Keep clients typically depend on reverse-engineered private
endpoints, undocumented authentication flows, browser cookies, app passwords,
or long-lived account tokens. Those approaches can break without notice and
create unnecessary account-security risk for a small desktop widget.

This project does not ask users to paste Google passwords, browser cookies, or
private Keep session tokens into code.

## Why Google Tasks fits better

Google Tasks has an official public API with explicit operations to list,
insert, update, complete, move, and delete tasks. It supports standard OAuth for
Desktop applications and maps directly to the widget's data model.

Official reference: [Google Tasks REST API](https://developers.google.com/workspace/tasks/reference/rest).

The tradeoff is setup friction: every developer using this starter must manage
their own Google Cloud project and OAuth client. That is preferable to building
on an unsupported private Keep interface.

