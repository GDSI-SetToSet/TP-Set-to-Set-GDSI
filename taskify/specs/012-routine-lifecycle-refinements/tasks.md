---
description: "Task list for 012-routine-lifecycle-refinements"
---

# Tasks: Ciclo de Vida de Rutinas

**Input**: `taskify/specs/012-routine-lifecycle-refinements/spec.md`

**Tests**: Obligatorios para el backend (Principio VI). El frontend se valida con `npm run build`.

## Format: `[ID] [P?] [Story] Description`

- `US1` = eliminar rutinas, `US2` = volver al origen, `US3` = seed de demo, `US4` = conservar rutinas con IA.

## Phase 1: Backend

- [x] T001 [US1] Agregar `preserve_student_copies` en `backend/src/services/student_routine_service.py`.
- [x] T002 [US1] Agregar `delete_template` y `DELETE /routine-templates/{id}`.
- [x] T003 [US1] Agregar `delete_assigned_routine` y `DELETE /routines/assigned/{id}`.
- [x] T004 [US4] Agregar `TrainerAIRoutineResponse`, `list_trainer_ai_routines` y `GET /routines/assigned`.
- [x] T005 [US4] Permitir asignar rutinas con IA aprobadas y soportarlas en `on_reassign` y `template_conflicts`.
- [x] T006 [P] [US1] [US4] Cubrir la API en `backend/tests/test_routine_lifecycle_api.py`.

## Phase 2: Seed

- [x] T007 [US3] Sembrar ejercicios, rutinas, asignación genérica y rutinas con IA en `backend/scripts/seed_demo.py`.
- [x] T008 [US3] Borrar las copias de alumno antes que los vínculos en `clean_demo_data`.
- [x] T009 [P] [US3] Cubrir contenido, idempotencia y limpieza en `backend/tests/test_seed_demo.py`.
- [x] T010 [P] [US3] Documentar los datos sembrados en `README.md`.
- [x] T010a [US3] Crear el esquema antes de `--clean` y `--reset` para que funcionen en una base nueva.

## Phase 3: Frontend

- [x] T011 [US2] Resolver "Volver" según el origen en `frontend/src/pages/GenerateAIRoutinePage.tsx`.
- [x] T012 [US4] Crear `frontend/src/components/AIRoutineCard.tsx` y la sección "Generadas con IA" en `RoutineTemplatesPage.tsx`.
- [x] T013 [US1] Agregar eliminación con confirmación e impacto en `RoutineTemplatesPage.tsx`.
- [x] T014 [US4] Avisar de rutinas ya generadas en `GenerateAIRoutinePage.tsx`.
- [x] T015 [US4] Ofrecer rutinas con IA aprobadas en `RoutineAssignmentPanel.tsx` y mostrar copias sin origen.

## Phase 4: Polish

- [x] T016 Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build`.
