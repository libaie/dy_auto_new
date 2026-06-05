<!-- /autoplan rerun restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-rerun-restore-20260528-103437.md -->
<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260528-095743.md -->
# Prompt Template AI Rewrite Design

## Context

The prompt template page already supports AI-assisted creation through `/api/prompt-templates/generate-stream`. That flow creates a full template JSON from a natural-language description, streams progress to the editor, and leaves the result unsaved until the user reviews it and clicks create.

Editing an existing template currently requires manual JSON edits. The requested addition is an AI rewrite action for existing templates: the user describes the desired adjustment in plain language, and the AI updates the current template JSON accordingly.

## Confirmed Behavior

- The feature appears when editing an existing prompt template.
- The user enters a natural-language rewrite request, such as changing tone, industry focus, forbidden words, reply rules, or DM stage behavior.
- AI returns a complete prompt template JSON, not a partial patch.
- The returned JSON replaces only the current dialog editor content.
- The template is not saved automatically. The user must review the JSON and click the existing update button.
- Template name remains immutable in edit mode.
- Existing template validation still applies before the final update can be saved.

## Recommended Approach

Add a dedicated rewrite API instead of overloading the existing create-generation endpoint.

The backend receives:

- `industry`
- current template `content`
- plain-language rewrite `instruction`

The backend does not receive template `name` or `version`. Rewrite is a stateless editor-draft transform, not a template persistence or conflict-check endpoint. Existing update flow remains responsible for saving and any future stale-version behavior.

It sends the current JSON and instruction to the configured LLM with a system prompt that says to preserve the schema, keep unrelated fields stable where possible, apply only the requested changes, and return valid JSON only. The endpoint reuses the existing JSON cleanup pattern from create generation, then runs the full prompt template content validation before emitting `done`. This includes required fields, semantic guide fields, analysis rules, and `replyExample` validation.

Keep the route thin. Put no-side-effect rewrite validation and prompt construction in `PromptTemplateService` helpers, for example request content validation, output validation, serialized-size checks, and rewrite prompt building. The router should only handle auth, HTTP/SSE framing, AI streaming orchestration, and logging.

Add lightweight backend logs for rewrite start/success/failure with industry and error type. Do not log the full template JSON or user instruction.

Before returning the rewrite `StreamingResponse`, snapshot the selected AI configuration while the request still has a normal database session. The stream should call the LLM through a config-based helper rather than holding the SQLAlchemy session open for the whole SSE response. Existing create-generation streaming may keep its current path; the rewrite endpoint should avoid extending that coupling.

The frontend adds a small AI rewrite panel in the edit dialog. It mirrors the current AI generation UX: request input, loading/status state, streamed output, and final replacement of `form.contentJson`.

## API Shape

`POST /api/prompt-templates/rewrite-stream`

Authorization:

- use `require_role("admin")`, matching template mutation endpoints rather than the looser `verify_admin_token` used by the existing create-generation preview endpoint
- auth failures remain HTTP 401/403 and do not enter the SSE business stream

Request:

```json
{
  "industry": "health",
  "instruction": "Make the tone warmer and less technical. Soften the DM stages.",
  "content": {}
}
```

Request validation:

- `instruction` must be non-empty after trimming.
- `instruction` must stay under a simple bounded length, default target 2,000 characters. The frontend should set the same `maxlength`; the backend remains authoritative and returns an SSE `error` after auth without calling AI when the limit is exceeded.
- `content` must be an object and must pass the same prompt template content validation used by create/update before it is sent to the AI.
- serialized `content` should stay below a simple backend size limit; default target is about 50 KB unless implementation evidence suggests a better threshold.
- the rewritten AI result must pass full prompt template content validation before `done`.
- use permissive request parsing for rewrite fields, then validate inside the stream, so syntactically valid JSON requests with wrong `instruction` or `content` shape can return SSE `error` after auth; malformed HTTP JSON may still fail before the route

SSE events follow the existing generation stream shape:

- `status`: human-readable progress
- `token`: streamed raw text for the editor
- `done`: parsed and validated full template JSON
- `error`: failure message; validation failures use `error`, not `warning`

The endpoint does not persist changes and does not broadcast template updates.
After the request passes auth and starts the streaming response, business validation failures should use SSE `error` events so the frontend has one recovery path. Auth failures still use existing HTTP 401/403 behavior.

## Frontend Design

`PromptTemplatesPage.vue` keeps the existing create-generation card for create mode.

For edit mode, add an AI rewrite card above the JSON editor, after the metadata fields:

- input bound to a saved prompt key such as `template_rewriter`
- button disabled while rewriting or when the instruction is empty
- call rewrite stream with parsed current JSON, current industry, and instruction
- while streaming, use a rewrite-specific token buffer; token chunks may fill the JSON textarea from that buffer, but only `done` is success. Throttle textarea rendering to at most every 50ms or one animation frame, then pretty-print the validated JSON on `done`.
- on `done`, replace the textarea with pretty-printed JSON and show a success toast
- if the stream ends or fails before `done`, restore the previous editor content
- after a successful rewrite, expose a one-click local restore action for the previous editor content; this is in-memory only and disappears when the dialog closes or another rewrite begins
- while rewriting, keep the rewrite input/button, save button, cancel button, and dialog close action disabled so only one rewrite stream can modify or persist the editor at a time

If the current JSON is invalid before calling AI, show the existing-style JSON parse error and do not call the backend.

Streaming implementation should not use the axios JSON client abstraction. Export a small raw-`fetch` SSE helper from `promptTemplates.js`, so create generation and rewrite can share parsing behavior without treating SSE as a normal JSON request. `PromptTemplatesPage.vue` should only provide event callbacks and UI state updates. That helper owns the `/api` base path, `Authorization: Bearer <token>` header, non-OK response parsing, explicit 401 behavior, and SSE frame parsing because it bypasses the axios interceptors.

## Error Handling

- Invalid current editor JSON: frontend blocks the request.
- Empty or whitespace-only instruction: frontend blocks the request, backend rejects direct calls.
- Invalid current template JSON shape: backend emits `error`.
- AI returns invalid JSON: backend emits `error`.
- AI returns invalid `replyExample`: backend emits `error`.
- Network or auth failure: frontend shows a toast and keeps the previous editor content where possible.
- Stream disconnects, ends early, or receives `error` before `done`: frontend restores the previous editor content.
- Prompt injection-like instructions are not blocked with brittle keyword filters; safety relies on admin auth, no auto-save, full output validation, manual review, and local restore.

## Tests

Backend:

- rewrite endpoint sends current content and instruction to the AI service.
- rewrite requires admin role via `require_role("admin")`.
- valid AI JSON returns `done` content without saving the database row.
- invalid JSON returns an SSE `error`.
- incomplete template JSON returns an SSE `error` instead of `done`.
- invalid `replyExample` is rejected.
- empty or whitespace-only instruction is rejected before calling AI.
- instruction over the configured length limit is rejected with SSE `error` before calling AI.
- oversized current content is rejected with SSE `error`.
- rewrite snapshots AI configuration before returning the stream and does not keep the DB session as an input to the long-running LLM stream helper.
- `PromptTemplateService` rewrite helpers have unit coverage for request validation, output validation, serialized-size checks, and prompt construction.
- rewrite does not read or write `PromptTemplate` rows, does not bump template revision, and does not broadcast WebSocket updates.
- rewrite does not call create/update/delete/toggle/version/broadcast paths; tests should fail if these side-effect paths are invoked.
- rewrite logs success and failure without logging full template content or instruction.

Frontend:

- SSE rewrite behavior is covered through a raw-fetch helper or page-level test, not an axios JSON helper.
- edit dialog exposes the rewrite action.
- invalid current JSON blocks the rewrite call.
- successful rewrite replaces `contentJson` but does not call `updateTemplate`.
- failed rewrite restores the previous editor content.
- successful rewrite exposes one-click local restore for the previous editor content.
- rewrite input/button, save, cancel, and dialog close are disabled while a stream is in flight.
- rewrite card appears above the JSON editor in edit mode and does not appear in create mode.
- raw-fetch helper includes `/api` prefix, Authorization header, non-OK parsing, and explicit 401 behavior.
- raw-fetch helper parses SSE frames split across network chunks.
- raw-fetch helper treats SSE `error` as failure, not success; only `done` marks rewrite completion.

## Out Of Scope

- JSON diff previews.
- Automatic saving after AI rewrite.
- Creating a new template copy from rewrite output.
- Version history or rollback UI.

---

## GSTACK AUTOPLAN REVIEW REPORT

Review target: prompt template AI rewrite plan.

Base branch detection: no `origin` remote was configured, so review used local context and treated `main` as the fallback base.

Scope detection:

- UI scope: yes. The plan changes an edit dialog, input, button, textarea, status, and restore interaction.
- DX scope: yes. The plan adds a new backend endpoint and frontend streaming API behavior.
- Dual voices: Codex CLI completed a read-only review. Claude subagent voice was unavailable in this environment, so consensus tables mark it as N/A.

### Phase 1 - CEO Review

Premise challenge:

- Premise accepted: users need to adjust existing prompt templates with plain-language instructions instead of manually editing a large JSON object.
- Premise accepted: no auto-save is the right default because these templates affect production AI behavior and device sync.
- Premise corrected: "validated JSON" must mean full template schema validation before `done`, not only JSON parse and `replyExample` validation.
- Premise corrected: a successful rewrite can still destroy unsaved manual edits in the dialog, so the minimum safe experience needs a local restore affordance.

What already exists:

- Create mode already streams AI-generated full template JSON through `/api/prompt-templates/generate-stream`.
- Existing create/update persistence paths validate template content through `PromptTemplateService._validate_content`.
- The prompt template page already keeps AI output unsaved until the user explicitly clicks create/update.
- WebSocket broadcasts already happen only on create/update/delete/toggle and should not happen for rewrite preview.

NOT in scope:

- Diff previews.
- Server-side version history.
- Automatic save.
- New template copy flow.
- Device-side behavior changes.

Dream state delta:

- Current plan: user asks AI to rewrite the current template, reviews JSON, and manually saves.
- 10/10 version: same flow plus full pre-save validation, no persistence side effects, one-click local restore for accidental successful rewrites, and clear separation between streaming preview and persistence.
- Accepted delta: add full validation, backend request guards, raw-fetch SSE handling, and local restore.
- Deferred delta: diff preview and durable version history remain out of scope.

Error and rescue registry:

| Failure | User impact | Rescue in plan |
|---|---|---|
| AI emits invalid JSON | Editor could become unusable or save fails later | Backend emits `error`; frontend restores previous editor content |
| AI emits incomplete template JSON | User sees success but update fails later | Backend runs full content validation before `done` |
| AI emits forbidden `replyExample` format | Bad examples leak into production behavior | Backend emits `error`, not `warning` |
| User has unsaved manual edits before rewrite | Successful rewrite overwrites edits | One-click local restore after successful rewrite |
| Direct API caller sends empty instruction | Wasteful AI call or ambiguous output | Backend rejects before AI call |
| Rewrite preview accidentally persists | Device behavior changes without review | Endpoint does not commit, bump version, or broadcast |

Failure modes registry:

| Mode | Severity | Critical gap? | Decision |
|---|---:|---|---|
| `done` emitted after only partial validation | High | Yes | Fixed in plan with full content validation |
| Existing `warning` event copied from create stream | High | Yes | Fixed in plan: validation failures emit `error` |
| Duplicate local SSE parsers drift | Medium | No | Fixed in plan: raw-fetch SSE helper or shared page helper |
| No restore after successful rewrite | Medium | No | Fixed in plan as in-memory local restore |
| Empty instruction allowed server-side | Medium | No | Fixed in plan with backend guard |

CEO dual voices - consensus table:

| Dimension | Local review | Codex voice | Consensus |
|---|---|---|---|
| Right problem? | Yes | Yes | Confirmed |
| Scope controlled? | Yes with restore addition | Yes with restore addition | Confirmed |
| Premises explicit? | Mostly, after validation clarification | Missing full-validation premise | Confirmed fix |
| Regret scenario covered? | Needs no-save and restore | Needs validation and restore | Confirmed fix |
| User safety adequate? | Adequate after edits | Adequate after edits | Confirmed |
| Business impact worth it? | Yes | Yes | Confirmed |

Phase 1 complete. Codex: 6 concerns. Claude subagent: unavailable. Consensus: 6/6 confirmed, 0 disagreements.

### Phase 2 - Design Review

Initial design rating: 8/10 after review edits.

Seven-pass design scorecard:

| Pass | Score | Review |
|---|---:|---|
| Information architecture | 8 | Create and edit modes remain distinct. Rewrite belongs near the JSON editor because it affects editor content, not template metadata. |
| Interaction state coverage | 8 | Loading, token streaming, done, error, invalid JSON, and local restore are specified. Cancellation is not specified but not required for MVP. |
| User journey | 8 | The flow preserves the key trust step: review before update. Restore reduces anxiety after a successful but unwanted rewrite. |
| AI slop risk | 8 | Full validation and no auto-save prevent obvious bad AI output from becoming production config. Diff preview would improve trust but is out of scope. |
| Design system alignment | 7 | Reusing the existing AI generate card pattern is consistent. Implementation should avoid adding a second visually dominant panel. |
| Responsive and accessibility | 7 | The existing dialog is compact. Add labels, disabled states, and avoid fixed-width controls that squeeze on small screens. |
| Unresolved design decisions | 8 | Only taste decision is restore affordance; accepted as small safety control. |

Design findings:

- The rewrite card should appear only in edit mode.
- The restore control should be visually secondary and local to the AI rewrite card/status area.
- Do not add explanatory onboarding text beyond concise labels and placeholders.
- Preserve the existing manual JSON editor as the primary source of truth.

Design dual voices - consensus table:

| Dimension | Local review | Codex voice | Consensus |
|---|---|---|---|
| Hierarchy sound? | Yes | Not directly disputed | Confirmed |
| Missing states? | Restore state needed | Restore state needed | Confirmed fix |
| Emotional arc safe? | Safer with review + restore | Safer with restore | Confirmed |
| AI slop controlled? | Needs full validation | Needs full validation | Confirmed fix |
| Design system fit? | Existing card pattern | Existing card pattern acceptable | Confirmed |
| Responsive/a11y covered? | Needs focused tests | Not flagged | Partial |
| Ambiguity resolved? | Mostly | API helper ambiguity flagged | Confirmed fix |

Phase 2 complete. Codex: 2 UI/DX concerns. Claude subagent: unavailable. Consensus: 6/7 confirmed, 1 partial.

### Phase 3 - Engineering Review

Architecture graph:

```text
PromptTemplatesPage.vue
  |-- parse current form.contentJson
  |-- raw fetch SSE helper
  |     |-- POST /api/prompt-templates/rewrite-stream
  |     |-- status/token/done/error events
  |
  |-- on done: replace editor JSON, keep local restore snapshot
  |-- on save: existing api.updateTemplate(...)

prompt_templates.py
  |-- TemplateRewriteRequest
  |-- validate instruction/content
  |-- ai_generator.generate_custom_stream(...)
  |-- strip fenced JSON
  |-- json.loads
  |-- prompt_template_service._validate_content(...)
  |-- emit done/error

prompt_template_service.py
  |-- _validate_content
        |-- required fields
        |-- semanticGuide rules
        |-- analysis rules
        |-- _validate_reply_example
```

Architecture assessment:

- Coupling is acceptable. The new endpoint belongs beside existing generate endpoints because it shares schema and AI generation behavior.
- Persistence boundary is clear. Rewrite preview must not call service create/update methods and must not broadcast WebSocket events.
- Validation should be centralized through `_validate_content` to avoid two definitions of a valid template.
- The SSE parser should be shared or narrowly extracted to avoid duplicating create-stream parsing in a second handler.

Code quality review:

- Reusing the existing create-generation prompt text without rewrite-specific instructions would be wrong; the rewrite system prompt needs explicit "preserve unrelated fields" language.
- Existing `generate-stream` uses a `warning` event for `replyExample`; rewrite must not inherit that event type because frontend restore logic depends on `error`.
- The new frontend state should be separate from create generation state unless a small shared state object makes the code clearer. Avoid a broad dialog refactor.

Test diagram:

| Codepath / branch | Test type | Required coverage |
|---|---|---|
| Edit dialog shows rewrite card | Vue component test | Mount page, open edit, assert rewrite control exists |
| Create dialog hides rewrite card | Vue component test | Open create, assert only create-generation panel exists |
| Invalid editor JSON before rewrite | Vue component test | No fetch call, error toast shown |
| Successful stream | Vue/helper test | status/token/done parsed, editor replaced, update not called |
| Stream error before done | Vue/helper test | prior editor content restored |
| Successful local restore | Vue component test | click restore, previous content returns |
| Empty instruction | Backend API test | rejects before AI call |
| Invalid current content | Backend API test | SSE `error`, AI not called |
| Valid AI result | Backend API test | SSE `done`, DB row unchanged |
| Invalid AI JSON | Backend API test | SSE `error` |
| Missing required AI field | Backend API test | SSE `error` |
| Invalid `replyExample` | Backend API test | SSE `error`, not `warning` |

Test plan artifact:

- `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-prompt-template-ai-rewrite-test-plan-20260528.md`

Performance:

- No database writes on rewrite preview.
- One LLM streaming request per click; no polling loop.
- Payload size is bounded by a single template JSON. Add server-side size guard only if current template sizes are observed to become large; not required for MVP if request body limits already apply globally.

Security:

- Endpoint must use the same admin auth dependency as existing generation endpoints.
- Server-side instruction/content validation is required because frontend disabled states are not a security boundary.
- Do not echo secrets from AI config; the endpoint only sends template JSON and user instruction.

Phase 3 complete. Codex: 5 engineering concerns. Claude subagent: unavailable. Consensus: 6/6 confirmed, 0 disagreements.

### Phase 3.5 - DX Review

Product type: internal admin API plus Vue admin interface.

Developer persona card:

- Persona: dy_auto maintainer adding a small admin feature across FastAPI and Vue.
- Goal: implement the feature without changing device behavior or production template persistence semantics.
- Main risk: mistaking preview streaming for persistence or treating SSE like normal axios JSON.

Developer empathy narrative:

A maintainer opening this plan needs to know where the new endpoint lives, what is allowed to change, and how to prove it did not save anything. The plan now gives a clear path: add a rewrite stream beside generation, validate with the existing service, keep persistence in the existing update button, and test the SSE branches directly.

Developer journey map:

| Stage | Expected path | Friction |
|---|---|---|
| Find feature entry | Prompt template edit dialog | Low |
| Find backend location | `prompt_templates.py` generate endpoints | Low |
| Understand validation | `_validate_content` in service | Low after plan edit |
| Add request model | Router request class | Low |
| Add streaming behavior | Existing SSE pattern | Medium because current parser is local to page |
| Add frontend state | PromptTemplatesPage edit mode | Medium because component is already large |
| Add tests | New prompt-template backend/page tests | Medium because no dedicated files exist |
| Verify no persistence | DB unchanged and no update call tests | Low |
| Debug failures | SSE error events and toast | Low |

DX scorecard:

| Dimension | Score | Notes |
|---|---:|---|
| Getting started | 8 | Relevant files are named directly. |
| API naming | 8 | `/rewrite-stream` is guessable and mirrors `/generate-stream`. |
| Error messages | 7 | Plan requires `error`, but implementation should include concise validation details. |
| Documentation | 8 | Spec has enough implementation guidance. |
| Upgrade path | 9 | No migration or device changes. |
| Dev environment | 7 | Backend/frontend tests are clear, but test files need to be created. |
| Ecosystem | 8 | Reuses existing AI generator and template service. |
| Feedback loops | 8 | SSE status/error and tests cover loop. |

TTHW assessment:

- Current maintainer time to first working path: about 25-40 minutes.
- Target after this reviewed plan: about 20-30 minutes.
- Main remaining friction: component test setup for a page that currently has no dedicated test file.

DX implementation checklist:

- Add rewrite request model with backend validation.
- Add rewrite stream endpoint with full content validation before `done`.
- Ensure validation failures emit `error`.
- Add raw-fetch SSE helper or page-level shared parser.
- Add edit-mode rewrite UI.
- Add previous-content restore state.
- Add backend and frontend tests listed in Phase 3.

Phase 3.5 complete. DX overall: 8/10. TTHW: 25-40 min -> 20-30 min. Codex: 1 API abstraction concern. Claude subagent: unavailable. Consensus: 5/6 confirmed, 1 N/A.

### Cross-Phase Themes

- Theme: full validation before success. Flagged in CEO, engineering, and Codex voice. High-confidence signal.
- Theme: preview must not persist. Flagged in CEO, engineering, and DX. High-confidence signal.
- Theme: restore previous editor content. Flagged in design, CEO, and Codex voice. Medium-confidence scope expansion, accepted because it is small and in blast radius.
- Theme: SSE is not axios JSON. Flagged in engineering and DX. High-confidence implementation detail.

### Deferred To TODO

- JSON diff preview: deferred because local restore covers the MVP safety risk at lower complexity.
- Durable version history: deferred because update persistence and version bump already exist; rewrite preview should not expand storage behavior.
- Device-side validation changes: deferred because rewrite affects admin preview only.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep no-auto-save as hard boundary | Mechanical | Explicit over clever | User chose review-then-save and production template changes affect device behavior | Auto-save |
| 2 | CEO/Eng | Require full `_validate_content` before `done` | Mechanical | Choose completeness | Parsed JSON alone can still fail update or ship malformed template semantics | ReplyExample-only validation |
| 3 | Design | Add in-memory one-click restore after successful rewrite | Taste | Choose completeness | Small UI addition prevents accidental loss of unsaved editor content without adding version history | No restore |
| 4 | Eng | Emit `error` for rewrite validation failures | Mechanical | Explicit over clever | Frontend failure handling can restore content only on a clear failure event | Reusing create stream `warning` |
| 5 | Eng/DX | Do not model SSE rewrite as axios JSON helper | Mechanical | DRY | Existing axios client returns JSON promises; SSE needs raw stream handling | `client.post` helper |
| 6 | Eng | Reject empty instruction server-side | Mechanical | Explicit over clever | Disabled frontend controls are not an API boundary | Frontend-only validation |
| 7 | Eng | Keep rewrite endpoint side-effect free | Mechanical | Choose completeness | No DB write, version bump, or WebSocket broadcast until existing update button is clicked | Calling update from rewrite |

### Final Gate

User challenges: none. No review voice recommends changing the user's selected behavior that AI rewrite only updates the editor and does not save.

Taste decisions:

1. Add one-click local restore after a successful rewrite. Recommended. This is not a diff preview or version history; it is only an in-memory undo for the last rewrite in the open dialog.

Auto-decided decisions: 7. See Decision Audit Trail above.

Review scores:

- CEO: pass after validation and restore clarifications.
- Design: 8/10.
- Engineering: pass with required backend/frontend tests.
- DX: 8/10.

Approval recommendation: approve the reviewed plan as-is and proceed to implementation planning.

---

## GSTACK AUTOPLAN RERUN REVIEW REPORT

Review target: OpenClaw-reviewed Bulletproof MVP plan.

Restore point:

- `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-rerun-restore-20260528-103437.md`

Scope detection:

- UI scope: yes. The rerun focused on rewrite card placement, streaming states, dialog close/save safety, and restore behavior.
- DX/API scope: yes. The rerun focused on auth dependency, SSE transport, raw-fetch helper responsibilities, and negative tests.
- Codex voice: completed read-only review. Claude subagent voice unavailable.

### Rerun Phase 1 - CEO / Scope

Premise challenge:

- The plan says safety relies on admin auth, so rewrite must use `require_role("admin")`, not merely a valid token check.
- Stateless rewrite remains the right framing. The new auth requirement does not make rewrite a persistence endpoint.
- The 50 KB content limit is still scope-compatible because it prevents accidental oversized AI calls rather than adding product behavior.

What already exists:

- Mutation endpoints already use `require_role("admin")`.
- Axios client owns token attachment and 401 handling for ordinary JSON calls.
- Existing create stream hand-rolls raw fetch and is therefore an implementation precedent but not a complete abstraction.

NOT in scope:

- Changing existing create generation auth.
- Adding route-level permissions beyond admin role.
- Adding abort/cancel stream controls.

CEO decision:

- Use `require_role("admin")` for rewrite. This aligns the endpoint with template mutation risk even though rewrite is preview-only.

### Rerun Phase 2 - Design

Design findings:

- Disabling only the rewrite button while streaming is insufficient; save/cancel/dialog close also need protection or stale chunks can mutate the editor after user intent changed.
- Because abort/cancel remains deferred, the simplest UI rule is: rewrite in flight disables save, cancel, and dialog close.
- This is a temporary modal lock during an explicit AI operation, not a new workflow.

Design score: 8/10 after adding in-flight modal protection.

### Rerun Phase 3 - Engineering

Architecture delta:

```text
PromptTemplatesPage.vue
  |-- handleRewrite()
  |-- previousContent snapshot
  |-- rewriteTokenBuffer
  |-- rewriting disables rewrite/save/cancel/close
  |-- only done => success
  |-- error/early EOF => restore previousContent

raw fetch SSE helper
  |-- /api base path
  |-- Authorization bearer token
  |-- non-OK response parsing
  |-- explicit 401 behavior

prompt_templates.py
  |-- require_role("admin")
  |-- permissive request parsing
  |-- stream-level business validation
  |-- full template validation
  |-- no CRUD/version/broadcast calls
```

Engineering findings:

- Do not copy create-stream's `receivedDone = true` behavior for `error`; rewrite treats only `done` as success.
- Do not append rewrite tokens to the pre-existing JSON. Use a rewrite-specific token buffer.
- Pydantic should not preempt the stream contract for syntactically valid but semantically wrong rewrite payloads. Use permissive field types and validate in the stream.
- Negative tests should fail if rewrite calls template CRUD, version bump, or WebSocket broadcast paths.

Failure modes registry update:

| Mode | Severity | Decision |
|---|---:|---|
| Valid token but non-admin role calls rewrite | High | Require `require_role("admin")` |
| Error event leaves half JSON in editor | High | Only `done` is success; otherwise restore |
| User saves while stream is writing | High | Disable save while rewriting |
| User closes dialog while stream is writing | Medium | Disable cancel/dialog close while rewriting |
| Wrong-shape payload returns unexpected HTTP 422 | Medium | Validate semantically inside stream after auth |
| Raw fetch silently loses auth behavior | Medium | Helper owns base path, token, non-OK parsing, 401 behavior |

### Rerun Phase 3.5 - DX/API

DX findings:

- The API contract is now precise: auth failures are HTTP 401/403; post-auth business/template validation failures are SSE `error`.
- The raw-fetch helper must document that it intentionally bypasses axios and therefore reimplements the small subset of axios behavior needed by SSE.
- Tests need to cover both transport layers: HTTP auth failure and SSE business failure.

DX score: 8/10.

### Rerun Cross-Phase Themes

- Theme: auth boundary. CEO, DX, and Codex voice all flagged that "admin auth" must be exact.
- Theme: stream success semantics. Design, engineering, and Codex voice all flagged that `error` cannot count as done.
- Theme: in-flight modal safety. Design and engineering both flagged save/close while streaming as a real corruption path.
- Theme: raw fetch owns its missing axios behavior. Engineering and DX both flagged this.

### Rerun Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 8 | CEO/API | Use `require_role("admin")` for rewrite | Mechanical | Choose completeness | Safety boundary says admin auth and template mutations already require admin role | `verify_admin_token` only |
| 9 | Eng | Rewrite uses a separate token buffer | Mechanical | Explicit over clever | Prevents old JSON and streamed partial JSON from mixing | Appending tokens to existing editor content |
| 10 | Eng/UI | Only `done` marks rewrite success | Mechanical | Explicit over clever | `error` or early EOF must restore previous content | Marking `error` as receivedDone |
| 11 | Design/Eng | Disable save, cancel, and dialog close while rewriting | Mechanical | Choose completeness | Prevents persisting or abandoning partial streamed content without abort support | Only disabling rewrite button |
| 12 | DX/API | Validate wrong-shape post-auth payloads inside stream where possible | Mechanical | Explicit over clever | Keeps one SSE business failure path for syntactically valid JSON requests | Strict Pydantic shape causing HTTP 422 for business errors |
| 13 | Eng/tests | Add negative tests for CRUD/version/broadcast side effects | Mechanical | Choose completeness | Row unchanged alone does not prove rewrite avoided side-effect paths | DB-row-only assertion |
| 14 | DX/API | Raw-fetch helper owns base path, Authorization, non-OK, and 401 behavior | Mechanical | DRY | SSE bypasses axios interceptors and must not silently lose auth behavior | Bare local fetch |

### Rerun Final Gate

User challenges: none.

Taste decisions: none newly introduced. The previous local restore affordance remains the only taste decision and stays accepted.

Auto-decided decisions in rerun: 7.

Review scores:

- CEO: pass after admin-role clarification.
- Design: 8/10.
- Engineering: pass with added stream buffer, modal safety, and negative tests.
- DX: 8/10.

Approval recommendation: approve the rerun-reviewed plan as-is and proceed to implementation planning.

---

## OpenClaw CEO Review Summary

Status: DONE.

Mode: SELECTIVE EXPANSION.

Selected approach: Bulletproof MVP.

Strongest challenges:

1. The feature must be framed as safe production-template preview, not generic AI JSON editing.
2. `rewrite-stream` must stay stateless and side-effect free: no template name/version, no template table read/write, no revision bump, no broadcast.
3. Streaming failure must be impossible to confuse with success: no `done` means restore previous editor content.

Recommended path:

- Implement `POST /api/prompt-templates/rewrite-stream` as a stateless draft transform that accepts `industry`, `content`, and `instruction`.
- Use full template content validation before calling AI for current content and before emitting `done` for AI output.
- Add a small raw-fetch SSE helper rather than copying parser logic or forcing SSE through axios.
- Add focused backend and frontend rewrite tests.

Accepted scope:

- Dedicated rewrite stream endpoint.
- Full `_validate_content` equivalent before `done`.
- SSE `error` for business/template validation failures after auth.
- No instruction blacklist.
- Single in-flight rewrite request; disable rewrite controls while streaming.
- `PromptTemplateService` no-side-effect rewrite validation and prompt helpers.
- Dedicated backend and frontend rewrite tests.
- Lightweight backend logs without full template/instruction payloads.
- No template table read/write; AI config is snapshotted before streaming and the long-running LLM stream does not hold the DB session.
- `status/token/done/error` stream contract.
- Instruction length limit, default target 2,000 characters.
- Simple backend serialized-content size limit, default target about 50 KB.
- Edit-mode AI rewrite card above the JSON editor.
- In-memory restore of the previous editor content after failed or successful rewrite.

Deferred:

- Diff preview.
- Durable version history or rollback.
- Stale version conflict UI.
- Abort/cancel running stream.
- Prompt-instruction blacklist.
- Metrics, dashboard, or alerting.
- Token budget accounting.
- Device-side behavior changes.

NOT in scope:

- Automatic saving.
- Creating a new template copy.
- Template persistence inside rewrite endpoint.
- Broader PromptTemplatesPage refactor.
- Full prompt template CRUD test suite expansion.

---

## GSTACK PLAN ENG REVIEW REPORT

Status: CLEAR.

Review target: prompt template AI rewrite plan.

Step 0 scope challenge:

- No scope reduction needed. The complete version should touch the existing prompt template router, prompt template service, prompt template page/API helper, and focused tests.
- No new database table, new service class, background job, version-history UI, or device-side behavior is needed.
- `TODOS.md` does not exist in this repo; deferred items remain listed in this plan instead of silently creating a new backlog file.

Architecture review:

1. Accepted: snapshot AI configuration before returning the rewrite `StreamingResponse`; do not hold a SQLAlchemy session inside the long-running LLM stream.
2. Accepted: add a bounded `instruction` length, default target 2,000 characters, enforced by frontend and backend.

Code quality review:

1. Accepted: export a raw-fetch SSE helper from `promptTemplates.js`; `PromptTemplatesPage.vue` should only handle callbacks and UI state.
2. Accepted: put no-side-effect rewrite validation and prompt construction in `PromptTemplateService`; keep the route focused on HTTP/SSE orchestration.

Test review:

```text
CODE PATHS                                      USER FLOWS
[+] server/app/routers/prompt_templates.py      [+] Edit template AI rewrite
  |-- [PLAN] require_role("admin")                |-- [PLAN] edit mode shows rewrite card
  |-- [PLAN] empty instruction -> SSE error       |-- [PLAN] invalid JSON blocks network call
  |-- [PLAN] instruction > 2000 -> SSE error      |-- [PLAN] token stream updates editor buffer
  |-- [PLAN] invalid content -> no AI call        |-- [PLAN] done replaces JSON, no auto-save
  |-- [PLAN] AI config snapshot before stream     |-- [PLAN] error/early EOF restores old JSON
  |-- [PLAN] valid AI output -> done              |-- [PLAN] successful rewrite exposes restore
  |-- [PLAN] invalid AI JSON -> error             |-- [PLAN] rewrite disables save/cancel/close
  `-- [PLAN] no DB write/version/broadcast

[+] server/app/services/prompt_template_service.py
  |-- [PLAN] rewrite request helper unit tests
  |-- [PLAN] rewrite output validation unit tests
  `-- [PLAN] rewrite prompt builder preserves current content and instruction

[+] web/src/api/promptTemplates.js
  |-- [PLAN] raw SSE helper parses split frames
  |-- [PLAN] /api prefix + Authorization
  |-- [PLAN] non-OK + 401 behavior
  `-- [PLAN] error event is not success
```

Test plan artifact:

- `C:\Users\HNXE\.gstack\projects\dy_auto\HNXE-feature-video-review-fixes-prompt-template-ai-rewrite-eng-review-test-plan-20260528-112456.md`

Performance review:

1. Accepted: throttle rewrite token-buffer rendering to at most every 50ms or one animation frame; final `done` pretty-prints the validated JSON.

NOT in scope:

- JSON diff preview: useful trust feature, deferred because local restore covers MVP safety at lower complexity.
- Durable version history or rollback: existing update/version path remains the persistence boundary.
- Abort/cancel running stream: deferred because modal lock is simpler and keeps stream state deterministic.
- Metrics, dashboard, token budget accounting, and alerting: useful operations work, not required for first safe preview.

Completion summary:

- Scope Challenge: no reduction needed.
- Architecture Review: 2 issues found, 2 accepted.
- Code Quality Review: 2 issues found, 2 accepted.
- Test Review: coverage diagram produced, 7 concrete gaps converted into plan requirements.
- Performance Review: 1 issue found, 1 accepted.
- Critical gaps remaining: 0.
- Unresolved decisions: 0.
