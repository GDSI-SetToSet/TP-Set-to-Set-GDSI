---
description: "Tareas de la US-14: edición de rutina según objetivos y limitaciones del alumno"
---

# Tasks: Edición de Rutina según Objetivos y Limitaciones del Alumno (US-14)

**Input**: `plan.md`, `spec.md` (User Story 2 = US-14), `data-model.md`, `research.md`, `contracts/student-routine-edit-api.yaml`

**Alcance**: solo US-14. US-13, US-53, US-54 y US-55 quedan fuera (Principio VII, un PR por story).

**Tests**: obligatorios (Principio VI, cobertura ≥ 90 %). Rutas relativas a la raíz del repo (`backend/`, `frontend/`).

**Formato**: `- [ ] T### [P] [US14] descripción con ruta`. `[P]` = paralelizable (archivos distintos, sin dependencia pendiente).

## Phase 1: Setup

- [ ] T001 Confirmar rama `feature/us14` actualizada con `develop` y US-09 mergeada (precedente); correr `pytest backend/tests` como línea base.

## Phase 2: Foundational (bloquea la story)

- [ ] T002 [P] Agregar `contraindicated_zones` (lista de textos normalizados en minúsculas, sin espacios extremos; opcional, vacía por defecto) a `Exercise` en `backend/src/models/exercise.py` y exponerlo en `backend/src/schemas/exercise.py` y `backend/src/services/exercise_service.py` (alta y edición).
- [ ] T003 [P] Crear modelos `StudentRoutine` (+ días/bloques/ejercicios vigente y borrador; `status` ACTIVE|DRAFT_PENDING; `draft_version` entero +1 por guardado; `desired_weekly_volume` entero entre 1 y 7 o null; `sets` > 0, `reps` texto ≤ 50, `rest_seconds` ≥ 0, `target_weight_kg` ≥ 0 opcional) y `RoutineChangeLog` (inmutable, sin delete) en `backend/src/models/student_routine.py`; registrarlos en `backend/src/models/__init__.py` y en los imports de `backend/src/main.py`.
- [ ] T004 [P] Crear schemas de entrada/salida (`RoutineDraftInput`, `DraftResponse` con `warnings[]`, vista del alumno solo vigente) en `backend/src/schemas/student_routine.py` según el contrato.

**Checkpoint**: modelos y schemas listos.

## Phase 3: User Story US-14 — Editar rutina según objetivos y limitaciones (P2)

**Objetivo**: el entrenador edita en borrador, con bloqueos de seguridad, y confirma; el alumno ve solo lo vigente.

**Prueba independiente**: seguir los 6 escenarios de `quickstart.md`.

### Tests

- [ ] T005 [P] [US14] Tests de servicio en `backend/tests/test_student_routine_service.py`: clonado de plantilla al primer guardado, borrador vs. vigente, confirmación atómica con log, descarte, `409` por `draft_version` desactualizada, valores inválidos, vínculo no ACTIVE o `TERMINATED` → `403`.
- [ ] T006 [P] [US14] Tests de API en `backend/tests/test_student_routine_api.py` por escenario de aceptación 1–5 de la US-14: edición libre (esc. 1), "Sin materiales" bloquea confirmar pero permite guardar borrador (esc. 2), ejercicio contraindicado → `422` problem+json sin opción de forzar (esc. 3), volumen semanal e intensidad (esc. 4), el alumno no ve el borrador (esc. 5), otro entrenador → `403`.

### Implementación

- [ ] T007 [US14] Implementar `backend/src/services/student_routine_service.py`: `get_routine`, `save_draft` (crea copia por alumno desde `initial_routine_id`; valida propiedad del ejercicio y no dado de baja; compara `contraindicated_zones` normalizadas contra `ProtectedZone.body_area` del alumno y bloquea sin forzar; `safe_variant` null si no existe), `discard_draft`, `confirm_draft` (exige alternativa "Sin materiales" por ejercicio editado si la rutina es "Sin materiales" y al menos un ejercicio; reemplaza vigente en una transacción; escribe `RoutineChangeLog` con autor, fecha UTC y diferencias antes→después). Errores con la clase de error existente (RFC 7807, `errors[]`).
- [ ] T008 [US14] Implementar router en `backend/src/api/v1/student_routines.py` (`GET/PUT/DELETE .../routine[/draft]`, `POST .../draft/confirm` bajo `/trainers/me/students/{studentId}`, y `GET /students/me/routine` solo vigente) reutilizando `deps.py`; incluirlo en `backend/src/main.py`.
- [ ] T009 [US14] Hacer que `backend/src/services/routine_template_service.py` (`get_assigned_student_template`) devuelva la `StudentRoutine` vigente cuando exista, para no romper la vista actual del alumno.
- [ ] T010 [P] [US14] Cliente HTTP y tipos en `frontend/src/services/studentRoutine.ts` y `frontend/src/types/studentRoutine.ts`.
- [ ] T011 [US14] Pantalla de edición en `frontend/src/pages/StudentRoutineEditPage.tsx` (+ ruta en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`, enlace desde `RoutineAssignmentPanel.tsx`): editar ejercicios/series/reps/carga/intensidad/volumen, guardar borrador, descartar, confirmar, alertas de bloqueo por limitación y por "Sin materiales", manejo de `409`. Controles ≥ 44×44 px, contraste 4.5:1.
- [ ] T012 [P] [US14] Campo de zonas contraindicadas en el formulario de ejercicios `frontend/src/pages/ExerciseLibraryPage.tsx`.

**Checkpoint**: US-14 funcional y probable por sí sola.

## Phase 4: Polish

- [ ] T013 [P] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build` en `frontend/`; corregir fallas.
- [ ] T014 Recorrer manualmente `quickstart.md` y marcar `[x]` las tareas completadas.

## Dependencias

T001 → T002/T003/T004 (paralelas) → T005/T006 (paralelas) → T007 → T008 → T009 → T010 → T011; T012 depende solo de T002. T013–T014 al final.

## Estrategia

Todo es una sola story: entregar en un único PR hacia `develop`. Orden sugerido: backend completo (T002–T009) verificado con tests, luego frontend (T010–T012).
