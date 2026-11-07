---
description: "Task list for 006-routine-planning-and-adaptation (US-13 and US-14)"
---

# Tasks: Generación de Rutina Particular con IA (US-13)

**Input**: Design documents from `taskify/specs/006-routine-planning-and-adaptation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/routine-adaptation-api.yaml`, `quickstart.md`

**Tests**: Obligatorios para el backend por Constitución, Principio VI (cobertura $\ge 90\%$). El frontend se valida mediante compilación TypeScript y build de producción (`npm run build`).

**Organization**: Una rama y un PR hacia `develop` por historia (Principio VII). Exclusivo para US-13 (US-14 y resto del sprint excluidos).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos independientes).
- **[Story]**: `US13` = US-13 (Generar rutina particular con IA).
- Rutas relativas a la raíz del repositorio (`backend/`, `frontend/`, `taskify/`).

---

## Phase 1: Setup & Data Modeling

**Purpose**: Formalización del modelo de datos de rutinas particulares y adaptaciones.

- [x] T001 [P] [US13] Crear modelos `AssignedRoutine`, `AssignedRoutineDay`, `AssignedRoutineBlock` y `AssignedRoutineExercise` en `backend/src/models/assigned_routine.py` con estados `PENDING_REVIEW` y `APPROVED`, campos `adaptation_summary` y `adaptation_notes`, relaciones en cascada y claves foráneas a `trainer_profiles`, `student_profiles`, `routine_templates` y `exercises`.
- [x] T002 [US13] Registrar los nuevos modelos en `backend/src/models/__init__.py`, `backend/src/main.py` y `backend/tests/conftest.py`.
- [x] T003 [P] [US13] Crear schemas Pydantic en `backend/src/schemas/assigned_routine.py`: `GenerateAIRoutineInput`, `AssignedRoutineResponse`, `AssignedRoutineDayResponse`, `AssignedRoutineBlockResponse`, `AssignedRoutineExerciseResponse` y `ActiveStudentResponse`.

---

## Phase 2: AI Adaptation Engine & Backend Services

**Purpose**: Implementar el motor de adaptación biomecánica y el servicio de rutinas particulares.

- [x] T004 [P] [US13] Crear interfaz abstracta `AIRoutineAdapter` e implementación determinista `HeuristicAIRoutineAdapter` en `backend/src/services/ai_routine_adapter.py`:
  - Detección de incompatibilidades biomecánicas contra `protected_zones` del alumno.
  - Sustitución por ejercicio alternativo seguro de la biblioteca del entrenador o eliminación segura.
  - Modificación de series, repeticiones y tiempo de descanso según objetivos del alumno (`fitness_goals`).
  - Adaptación de intensidad y descansos ante contraindicaciones del `health_questionnaire`.
  - Generación de resumen explicativo `adaptation_summary` y notas por ejercicio `adaptation_notes`.
- [x] T005 [US13] Crear `backend/src/services/assigned_routine_service.py` con:
  - `list_active_students_for_trainer(db, trainer_user)`: retorna alumnos con relación activa (`TrainingRelationship.status == "ACTIVE"`).
  - `generate_ai_routine_proposal(db, trainer_user, payload)`: valida relación activa y pertenencia de la plantilla, invoca el adaptador de IA, persiste la propuesta en estado `PENDING_REVIEW` y conserva intacta la plantilla genérica.
  - `approve_assigned_routine(db, trainer_user, routine_id)`: valida que el usuario sea el entrenador autor, transiciona el estado a `APPROVED`, registra `approved_at`, y enlaza `initial_routine_id` en `TrainingRelationship` si estaba vacío.
  - `get_assigned_routine_detail(db, user, routine_id)`: consulta permitida para el entrenador creador o para el alumno destinatario (solo si está aprobada).
  - `get_active_routine_for_student(db, student_user)`: retorna la rutina aprobada actual del alumno autenticado.
- [x] T006 [US13] Exponer los endpoints en `backend/src/api/v1/assigned_routines.py` (`POST /api/v1/routines/generate-ai`, `POST /api/v1/routines/assigned/{id}/approve`, `GET /api/v1/routines/assigned/{id}`, `GET /api/v1/trainers/me/active-students`, `GET /api/v1/students/me/assigned-routine`) con respuestas RFC 7807 y registrar el router en `backend/src/main.py`.

---

## Phase 3: Backend Automated Tests (DoD Quality Gate)

**Purpose**: Verificar exhaustivamente todos los escenarios de aceptación y casos de borde requeridos.

- [x] T007 [US13] Implementar suite completa de pruebas en `backend/tests/test_ai_routine_api.py`:
  - Generación exitosa de propuesta a partir de una plantilla genérica con alumno activo.
  - Modificación de series, repeticiones e intensidad según objetivos del alumno.
  - Eliminación o sustitución de ejercicios incompatibles con zonas protegidas o salud.
  - Preservación intacta de la plantilla genérica original tras la generación y tras la aprobación.
  - Estado `PENDING_REVIEW` inicial: el alumno no puede ver la rutina antes de la aprobación.
  - Aprobación explícita del entrenador (`APPROVED` con timestamp `approved_at`) y visibilidad para el alumno tras aprobarse.
  - Bloqueo y rechazo con HTTP 403 Forbidden para entrenadores sin vínculo activo con el alumno.
  - Manejo de errores RFC 7807 ante datos inválidos, alumno inexistente o falla en el mecanismo de IA.
  - Verificación de regresión: comprobación de que los 220 tests existentes de US-08, US-09, US-12 sigan en verde y cobertura $\ge 90\%$.

---

## Phase 4: Frontend Implementation

**Purpose**: Pantalla de generación, revisión interactiva y aprobación para el entrenador.

- [x] T008 [P] [US13] Crear definiciones TypeScript en `frontend/src/types/assignedRoutine.ts` y métodos de API en `frontend/src/services/assignedRoutineService.ts`.
- [x] T009 [US13] Crear componente de página `frontend/src/pages/GenerateAIRoutinePage.tsx`:
  - Selector de alumno activo (con objetivos y zonas protegidas destacadas).
  - Selector de plantilla genérica de la biblioteca del entrenador.
  - Botón de generación con IA con estado de carga accesible.
  - Vista previa de la propuesta: badge de `PENDING_REVIEW`, panel de resumen de adaptaciones de IA (motivos de cambios/sustituciones/eliminaciones), detalle de días, bloques y ejercicios adaptados.
  - Botón de aprobación explícita "Aprobar rutina para el alumno" con confirmación y retroalimentación accesible.
- [x] T010 [US13] Registrar la ruta `trainerGenerateAIRoutine: '/entrenador/rutinas/generar-ia'` en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`, y enlazar el acceso desde `frontend/src/pages/HomePage.tsx` y `frontend/src/pages/RoutineTemplatesPage.tsx`.
- [x] T011 [US13] Agregar estilos dedicados en `frontend/src/styles/generate-ai-routine.css` e importarlos en `frontend/src/styles.css`, garantizando áreas de toque $\ge 44 \times 44$ px y contraste WCAG 2.1 AA.

---

## Phase 5: Verification & Delivery

**Purpose**: Validación integral de calidad, análisis estático y entrega.

- [x] T012 [US13] Ejecutar `pytest backend/tests --cov=backend/src --cov-fail-under=90`.
- [x] T013 [US13] Ejecutar `ruff check backend`.
- [x] T014 [US13] Ejecutar `npm run build` en `frontend/`.
- [x] T015 [US13] Ejecutar `/speckit-analyze` para verificar consistencia y ausencia de requisitos huérfanos.
- [x] T016 [US13] Auditoría final de cambios con `git status` y `git diff`, comprobando estricta exclusión de US-14 y elaboración del informe final.

---

# Tasks: Edición de Rutina según Objetivos y Limitaciones del Alumno (US-14)

**Input**: `plan.md`, `spec.md` (User Story 2 = US-14), `data-model.md`, `research.md`, `contracts/student-routine-edit-api.yaml`

**Alcance**: solo US-14. US-13, US-53, US-54 y US-55 quedan fuera (Principio VII, un PR por story).

**Tests**: obligatorios (Principio VI, cobertura ≥ 90 %). Rutas relativas a la raíz del repo (`backend/`, `frontend/`).

**Formato**: `- [ ] T### [P] [US14] descripción con ruta`. `[P]` = paralelizable (archivos distintos, sin dependencia pendiente).

## Phase 1: Setup

- [X] T001 Confirmar rama de trabajo actualizada con `develop` y US-09 mergeada (precedente); correr `pytest backend/tests` como línea base.

## Phase 2: Foundational (bloquea la story)

- [X] T002 [P] Agregar `contraindicated_zones` (lista de textos normalizados en minúsculas, sin espacios extremos; opcional, vacía por defecto) a `Exercise` en `backend/src/models/exercise.py` y exponerlo en `backend/src/schemas/exercise.py` y `backend/src/services/exercise_service.py` (alta y edición).
- [X] T003 [P] Crear modelos `StudentRoutine` (+ días/bloques/ejercicios vigente y borrador; `status` ACTIVE|DRAFT_PENDING; `draft_version` entero +1 por guardado; `desired_weekly_volume` entero entre 1 y 7 o null; `sets` > 0, `reps` texto ≤ 50, `rest_seconds` ≥ 0, `target_weight_kg` ≥ 0 opcional) y `RoutineChangeLog` (inmutable, sin delete) en `backend/src/models/student_routine.py`; registrarlos en `backend/src/models/__init__.py` y en los imports de `backend/src/main.py`.
- [X] T004 [P] Crear schemas de entrada/salida (`RoutineDraftInput`, `DraftResponse` con `warnings[]`, vista del alumno solo vigente) en `backend/src/schemas/student_routine.py` según el contrato.

**Checkpoint**: modelos y schemas listos.

## Phase 3: User Story US-14 — Editar rutina según objetivos y limitaciones (P2)

**Objetivo**: el entrenador edita en borrador, con bloqueos de seguridad, y confirma; el alumno ve solo lo vigente.

**Prueba independiente**: seguir los 6 escenarios de `quickstart.md`.

### Tests

- [X] T005 [P] [US14] Tests de servicio en `backend/tests/test_student_routine_service.py`: clonado de plantilla al primer guardado, borrador vs. vigente, confirmación atómica con log, descarte, `409` por `draft_version` desactualizada, valores inválidos, vínculo no ACTIVE o `TERMINATED` → `403`.
- [X] T006 [P] [US14] Tests de API en `backend/tests/test_student_routine_api.py` por escenario de aceptación 1–5 de la US-14: edición libre (esc. 1), "Sin materiales" bloquea confirmar pero permite guardar borrador (esc. 2), ejercicio contraindicado → `422` problem+json sin opción de forzar (esc. 3), volumen semanal e intensidad (esc. 4), el alumno no ve el borrador (esc. 5), otro entrenador → `403`.

### Implementación

- [X] T007 [US14] Implementar `backend/src/services/student_routine_service.py`: `get_routine`, `save_draft` (crea copia por alumno desde `initial_routine_id`; valida propiedad del ejercicio y no dado de baja; compara `contraindicated_zones` normalizadas contra `ProtectedZone.body_area` del alumno y bloquea sin forzar; `safe_variant` null si no existe), `discard_draft`, `confirm_draft` (exige alternativa "Sin materiales" por ejercicio editado si la rutina es "Sin materiales" y al menos un ejercicio; reemplaza vigente en una transacción; escribe `RoutineChangeLog` con autor, fecha UTC y diferencias antes→después). Errores con la clase de error existente (RFC 7807, `errors[]`).
- [X] T008 [US14] Implementar router en `backend/src/api/v1/student_routines.py` (`GET/PUT/DELETE .../routine[/draft]`, `POST .../draft/confirm` bajo `/trainers/me/students/{studentId}`, y `GET /students/me/routine` solo vigente) reutilizando `deps.py`; incluirlo en `backend/src/main.py`.
- [X] T009 [US14] Hacer que `backend/src/services/routine_template_service.py` (`get_assigned_student_template`) devuelva la `StudentRoutine` vigente cuando exista, para no romper la vista actual del alumno.
- [X] T010 [P] [US14] Cliente HTTP y tipos en `frontend/src/services/studentRoutine.ts` y `frontend/src/types/studentRoutine.ts`.
- [X] T011 [US14] Pantalla de edición en `frontend/src/pages/StudentRoutineEditPage.tsx` (+ ruta en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`, enlace desde `RoutineAssignmentPanel.tsx`): editar ejercicios/series/reps/carga/intensidad/volumen, guardar borrador, descartar, confirmar, alertas de bloqueo por limitación y por "Sin materiales", manejo de `409`. Controles ≥ 44×44 px, contraste 4.5:1.
- [X] T012 [P] [US14] Campo de zonas contraindicadas en el formulario de ejercicios `frontend/src/pages/ExerciseLibraryPage.tsx`.

**Checkpoint**: US-14 funcional y probable por sí sola.

## Phase 4: Polish

- [X] T013 [P] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build` en `frontend/`; corregir fallas.
- [ ] T014 Recorrer manualmente `quickstart.md` y marcar `[x]` las tareas completadas.

## Dependencias

T001 → T002/T003/T004 (paralelas) → T005/T006 (paralelas) → T007 → T008 → T009 → T010 → T011; T012 depende solo de T002. T013–T014 al final.

## Estrategia

Todo es una sola story: entregar en un único PR hacia `develop`. Orden sugerido: backend completo (T002–T009) verificado con tests, luego frontend (T010–T012).
