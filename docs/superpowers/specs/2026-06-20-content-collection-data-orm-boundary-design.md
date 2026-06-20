# Content Collection Data ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `CollectedComment`, `CollectedUser`, and `Conversation` ORM class bodies
from `app.db_models` into `app.db.models.content_collection`.

## Design

- `app.db.models.content_collection` owns content templates, sensitive words,
  reply dedupe, DM sequences, collected comments, collected users, and
  conversations.
- `app.db_models` remains a compatibility re-export surface.
- Content collection domain modules import these three data models from the
  domain ORM module.

## Out Of Scope

- Do not move `Account`, `Device`, `Task`, routers, or device bridge routes.
- Do not change table names, columns, indexes, response shapes, or realtime
  events.

## Verification

- Extend the content collection ORM boundary test to cover the three data
  models.
- Run focused content collection ORM/read-model/mutation tests.
