# Video Production Control Plane Stage 1 Verification

## Automated Verification

- `cd server && pytest`
- `cd web && npx vitest run`
- `cd web && npm run build`

Current local verification:

- `cd server && pytest` -> 603 passed.
- `cd web && npx vitest run` -> 72 passed.
- `cd web && npm run build` -> passed.
- `GET http://localhost:3000/video-production/run-smoke` -> 200, Vite HTML returned.
- `GET http://localhost:8000/openapi.json` -> 200.

## Manual Local Smoke

1. Open a Series detail page.
2. Lock style.
3. Start episode production from one visible action.
4. Confirm navigation to `/video-production/{runId}`.
5. Confirm run health, stage timeline, exception queue, production tree, Segment detail, and action panel render.
6. Confirm a retryable failed Segment opens retry impact before mutation.
7. Confirm final compose writes `Episode.video_url`.

## Paid Provider Smoke

Paid provider smoke is manual. Use a short test episode and verify Ark Plan V3 endpoints remain `/api/plan/v3`.
