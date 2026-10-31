---
description: "Task list for 006-routine-planning-and-adaptation (US-13)"
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
