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

It sends the current JSON and instruction to the configured LLM with a system prompt that says to preserve the schema, keep unrelated fields stable where possible, apply only the requested changes, and return valid JSON only. The endpoint reuses the existing JSON cleanup and `replyExample` validation pattern from create generation.

The frontend adds a small AI rewrite panel in the edit dialog. It mirrors the current AI generation UX: request input, loading/status state, streamed output, and final replacement of `form.contentJson`.

## API Shape

`POST /api/prompt-templates/rewrite-stream`

Request:

```json
{
  "industry": "health",
  "instruction": "Make the tone warmer and less technical. Soften the DM stages.",
  "content": {}
}
```

SSE events follow the existing generation stream shape:

- `status`: human-readable progress
- `token`: streamed raw text for the editor
- `done`: parsed and validated full template JSON
- `error`: failure message

The endpoint does not persist changes and does not broadcast template updates.

## Frontend Design

`PromptTemplatesPage.vue` keeps the existing create-generation card for create mode.

For edit mode, add an AI rewrite card near the JSON editor:

- input bound to a saved prompt key such as `template_rewriter`
- button disabled while rewriting or when the instruction is empty
- call rewrite stream with parsed current JSON, current industry, and instruction
- while streaming, show status and allow tokens to fill the JSON textarea
- on `done`, replace the textarea with pretty-printed JSON and show a success toast
- if the stream fails before `done`, restore the previous editor content

If the current JSON is invalid before calling AI, show the existing-style JSON parse error and do not call the backend.

## Error Handling

- Invalid current editor JSON: frontend blocks the request.
- AI returns invalid JSON: backend emits `error`.
- AI returns invalid `replyExample`: backend emits `error`.
- Network or auth failure: frontend shows a toast and keeps the previous editor content where possible.

## Tests

Backend:

- rewrite endpoint sends current content and instruction to the AI service.
- valid AI JSON returns `done` content without saving the database row.
- invalid JSON returns an SSE `error`.
- invalid `replyExample` is rejected.

Frontend:

- prompt template API exports a rewrite helper.
- edit dialog exposes the rewrite action.
- invalid current JSON blocks the rewrite call.
- successful rewrite replaces `contentJson` but does not call `updateTemplate`.

## Out Of Scope

- JSON diff previews.
- Automatic saving after AI rewrite.
- Creating a new template copy from rewrite output.
- Version history or rollback UI.
