---
description: "Task list for 008-workout-feedback-and-communication (US-63, US-64)"
---

# Tasks: Resumen de Sesión y Devolución sobre el Esfuerzo

**Input**: `taskify/specs/008-workout-feedback-and-communication/` (spec, plan, research, data-model, contracts)

**Tests**: Obligatorios para el backend (Principio VI). El frontend se valida con `npm run build`.

## Format: `[ID] [P?] [Story] Description`

- `US4` = US-63 (resumen de sesión), `US5` = US-64 (devolución sobre el esfuerzo). US-60 ya está implementada (PR #48); US-61/US-62 tienen plan propio.
- Cada story va en su propia rama y PR hacia `develop` (Principio VII).

## Phase 1: US-63 — Resumen de la sesión finalizada (rama `feature/063-us63-session-summary`)

- [x] T001 [US4] Agregar `SessionPersonalRecordResponse`, `SessionHistoryComparisonResponse` y `WorkoutSessionSummaryResponse` en `backend/src/schemas/routine_template.py` según `contracts/session-summary-api.yaml`.
- [x] T002 [US4] Crear `backend/src/services/session_summary_service.py` con `build_student_session_summary` (tonelaje R1, series programadas R2, PRs R3, comparación histórica R4; 404 sesión ajena, 422 sesión sin finalizar).
- [x] T003 [US4] Exponer `GET /students/me/routine-templates/assigned/workout-sessions/{session_id}/summary` en `backend/src/api/v1/routine_templates.py`.
- [x] T004 [P] [US4] Cubrir la API en `backend/tests/test_us63_session_summary_api.py` (tonelaje, reps no numéricas, duración, programadas vs completadas, rutina cambiada, PRs inicial/superado/no superado, historial vacío y con promedio, 404/422/403).
- [x] T005 [P] [US4] Agregar tipos `WorkoutSessionSummary` en `frontend/src/types/routineTemplate.ts` y `getWorkoutSessionSummary` en `frontend/src/services/routineTemplateService.ts`.
- [x] T006 [US4] Crear `frontend/src/components/SessionSummaryDialog.tsx` (métricas, PRs destacados, comparación histórica, estado de carga y error) y su CSS en `frontend/src/styles/session-summary.css`.
- [x] T007 [US4] En `frontend/src/pages/StudentRoutinesPage.tsx`, navegar con `completed=1` también al finalizar manualmente y reemplazar el diálogo de celebración por `SessionSummaryDialog`.
- [x] T008 [US4] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build`.

## Phase 2: US-64 — Devolución sobre el esfuerzo reportado (rama `feature/064-us64-effort-feedback`)

- [ ] T009 [US5] Crear el modelo `EffortFeedback` en `backend/src/models/effort_feedback.py` y registrarlo en `backend/src/models/__init__.py` y `backend/tests/conftest.py`.
- [ ] T010 [US5] Agregar `EffortFeedbackInput` y `EffortFeedbackResponse` en `backend/src/schemas/routine_template.py`.
- [ ] T011 [US5] Crear `backend/src/services/effort_feedback_service.py` con `upsert_effort_feedback` (vínculo activo, sesión finalizada con RPE, notificación `EFFORT_FEEDBACK`, reset de `seen_at`), `list_student_effort_feedback`, `mark_effort_feedback_seen` y `list_trainer_session_feedback`.
- [ ] T012 [US5] Exponer `PUT /routine-templates/assignments/{relationship_id}/workout-sessions/{session_id}/effort-feedback`, `GET /students/me/routine-templates/assigned/effort-feedback` y `POST .../effort-feedback/{feedback_id}/seen` en `backend/src/api/v1/routine_templates.py`; incluir `effort_feedback` en las sesiones del entrenador.
- [ ] T013 [P] [US5] Cubrir la API en `backend/tests/test_us64_effort_feedback_api.py` (alta, edición única, notificación, sin RPE, sesión ajena, vínculo inactivo, comentario > 500, historial vacío, marcar vista).
- [ ] T014 [P] [US5] Agregar tipos y servicios de devoluciones en `frontend/src/types/routineTemplate.ts` y `frontend/src/services/routineTemplateService.ts`.
- [ ] T015 [US5] Crear `frontend/src/components/EffortFeedbackForm.tsx` e integrarlo por sesión con RPE en `frontend/src/components/RoutineAssignmentPanel.tsx`.
- [ ] T016 [US5] Crear `frontend/src/components/EffortFeedbackList.tsx`; mostrar no vistas al abrir la sesión (y marcarlas) y el historial con estado vacío en `frontend/src/pages/StudentRoutinesPage.tsx`.
- [ ] T017 [US5] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build`.

## Dependencies

- Phase 1 y Phase 2 son independientes entre sí; ambas dependen de US-60 (mergeada).
- Dentro de cada fase: schemas → servicio → endpoint → tests; tipos → componente → página.
- US-63 escenario 3 (racha y logros) queda bloqueado por US-67/US-68.
