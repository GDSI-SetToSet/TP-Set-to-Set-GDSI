---
description: "Task list for 005-exercise-library-and-templates (US-08 and US-09)"
---

# Tasks: Biblioteca de Ejercicios y Rutinas Genéricas (US-08 y US-09)

**Input**: Design documents from `taskify/specs/005-exercise-library-and-templates/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/exercise-library-api.yaml`, `quickstart.md`

**Tests**: Obligatorios para el backend por Constitución, Principio VI (cobertura $\ge 90\%$). El frontend se valida mediante compilación TypeScript y build de producción (`npm run build`).

**Organization**: Una rama y un PR hacia `develop` por historia (Principio VII). US-12 y US-52 se agregan a este archivo cuando se planifiquen.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos independientes, sin dependencias previas no satisfechas).
- **[Story]**: `US1` = US-08 (Biblioteca de ejercicios), `US2` = US-09 (Rutinas genéricas).
- Rutas relativas a la raíz del repositorio (`backend/`, `frontend/`, `taskify/`).

---

## Phase 1: Setup

**Purpose**: Dejar la spec lista para implementar (Definition of Ready).

- [x] T001 Integrar las respuestas de `/speckit-clarify` en `taskify/specs/005-exercise-library-and-templates/spec.md` y crear `taskify/specs/005-exercise-library-and-templates/checklists/requirements.md`
- [x] T002 Alinear `plan.md`, `research.md`, `data-model.md`, `quickstart.md` y `contracts/exercise-library-api.yaml` en `taskify/specs/005-exercise-library-and-templates/` con las clarificaciones

---

## Phase 2: User Story 1 — US-08 Biblioteca de ejercicios (Priority: P2, 4 SP)

**Rama**: `feature/005-us08-exercise-library`

**Goal**: Permitir al entrenador crear, listar, filtrar por músculo, consultar, editar y dar de baja ejercicios de su biblioteca personal.

**Independent Test**: Un entrenador crea ejercicios, los filtra por músculo, consulta el detalle, los edita y los da de baja. Otro entrenador recibe HTTP 404 sobre esos ejercicios y un alumno recibe HTTP 403.

### Tests for User Story 1 (US-08)

- [ ] T003 [P] [US1] Crear pruebas de integración en `backend/tests/test_exercise_api.py` para:
  - Alta válida con los 5 campos y `has_no_materials_alternative` en `false` por defecto.
  - HTTP 422 RFC 7807 con `errors[]` ante cada campo obligatorio faltante o vacío, categoría fuera de la lista y textos que superen los límites.
  - Listado solo de ejercicios propios, filtro `muscle_group` sin distinguir mayúsculas y exclusión de dados de baja.
  - Detalle y edición con HTTP 404 para ejercicios de otro entrenador.
  - Baja lógica con HTTP 204, conservando la fila con `deleted_at` y HTTP 404 en consultas posteriores.
  - HTTP 403 para alumnos y HTTP 401 sin autenticación.

### Implementation for User Story 1 (US-08)

- [ ] T004 [US1] Crear el modelo `Exercise` en `backend/src/models/exercise.py` con `trainer_id` no nulo a `trainer_profiles.id`, `name` String(150), `description` Text, `category` String(16), `target_muscle_group` String(100), `equipment_needed` String(150), `has_no_materials_alternative` Boolean por defecto `False`, `deleted_at` nulo, `created_at` y `updated_at`; registrarlo en `backend/src/models/__init__.py`, `backend/src/main.py` y `backend/tests/conftest.py`.
- [ ] T005 [P] [US1] Crear schemas `ExerciseInput` y `ExerciseResponse` en `backend/src/schemas/exercise.py`, con categoría `FUERZA`, `CARDIO`, `MOVILIDAD`, `FLEXIBILIDAD` o `EQUILIBRIO` y el mensaje "Este campo es obligatorio" para campos faltantes.
- [ ] T006 [US1] Crear `backend/src/services/exercise_service.py` con listado filtrado, detalle, alta, edición y baja lógica, restringidos al entrenador autenticado (depende de T004, T005).
- [ ] T007 [US1] Exponer `GET`/`POST /api/v1/exercises` y `GET`/`PUT`/`DELETE /api/v1/exercises/{exercise_id}` en `backend/src/api/v1/exercises.py` y registrar el router en `backend/src/main.py` (depende de T006).
- [ ] T008 [P] [US1] Agregar tipos y métodos de API en `frontend/src/types/exercise.ts` y `frontend/src/services/exerciseService.ts`.
- [ ] T009 [US1] Crear `frontend/src/components/ExerciseCard.tsx` y `frontend/src/pages/ExerciseLibraryPage.tsx` con formulario de alta y edición, filtro por músculo, detalle, baja con confirmación y estado vacío, usando estilos de `frontend/src/styles/exercise-library.css` importados en `frontend/src/styles.css`.
- [ ] T010 [US1] Registrar la ruta `trainerExercises: '/entrenador/ejercicios'` en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`, y agregar el acceso en `frontend/src/pages/HomePage.tsx`.
- [ ] T011 [US1] Ejecutar `pytest backend/tests --cov=backend/src --cov-fail-under=90`, `ruff check backend`, `npm run build` y validar el Escenario 1 de `taskify/specs/005-exercise-library-and-templates/quickstart.md`.

**Checkpoint**: US-08 está completa y lista para abrir PR hacia `develop`.

---

## Phase 3: User Story 2 — US-09 Rutinas genéricas (Priority: P2, 5 SP)

**Rama**: `feature/005-us09-routine-templates`, creada desde `develop` con US-08 mergeada.

**Goal**: Permitir al entrenador crear, editar y consultar rutinas por días y bloques, aplicar la regla "Sin materiales" y ofrecer las rutinas en solo lectura a alumnos con vínculo activo.

**Independent Test**: Un entrenador crea y edita una rutina con días y bloques. Un alumno con vínculo activo la ve en solo lectura, y un alumno sin vínculo recibe HTTP 404.

### Tests for User Story 2 (US-09)

- [ ] T012 [P] [US2] Crear pruebas de integración en `backend/tests/test_routine_template_api.py` para:
  - Alta con estructura completa, orden preservado, `exercise_count` y categoría de cada ejercicio en la respuesta.
  - HTTP 422 RFC 7807 ante campos faltantes, sin días, bloques o ejercicios, y fuera de los límites del data-model.
  - HTTP 422 al usar ejercicios ajenos, inexistentes o dados de baja.
  - Edición que reemplaza la estructura y permite conservar un ejercicio dado de baja que ya estaba en la rutina.
  - HTTP 422 con los ejercicios que incumplen si la rutina es apta "Sin materiales", y HTTP 409 al quitar la marca a un ejercicio incluido en una rutina apta.
  - Aislamiento entre entrenadores (HTTP 404) y HTTP 403 según rol.
  - Alumno con vínculo `ACTIVE` lista y consulta; sin vínculo o con vínculo terminado recibe lista vacía y HTTP 404.

### Implementation for User Story 2 (US-09)

- [ ] T013 [US2] Crear modelos `RoutineTemplate`, `RoutineTemplateDay`, `RoutineTemplateBlock` y `RoutineTemplateExercise` en `backend/src/models/routine_template.py` según `data-model.md`, con `cascade="all, delete-orphan"` y orden por `order_index`; registrarlos en `backend/src/models/__init__.py`, `backend/src/main.py` y `backend/tests/conftest.py`.
- [ ] T014 [P] [US2] Crear schemas en `backend/src/schemas/routine_template.py` con los límites: `name` hasta 150, `duration_weeks` de 1 a 52, intensidad `BAJA`, `MEDIA`, `ALTA` o `EXIGENTE`, 1 a 7 días, 1 a 10 bloques, 1 a 30 ejercicios, nombres de día y bloque hasta 100, `sets` de 1 a 20, `reps` hasta 50 y `rest_seconds` de 0 a 600.
- [ ] T015 [US2] Crear `backend/src/services/routine_template_service.py` con alta, edición, listado y detalle del entrenador, validación de ejercicios y regla "Sin materiales", y listado y detalle para alumnos filtrados por `TrainingRelationship.status == "ACTIVE"` (depende de T013, T014).
- [ ] T016 [US2] Rechazar con HTTP 409 en `backend/src/services/exercise_service.py` la edición que quita la marca a un ejercicio incluido en una rutina apta "Sin materiales" (depende de T013).
- [ ] T017 [US2] Exponer los endpoints de rutinas en `backend/src/api/v1/routine_templates.py` y registrar los routers en `backend/src/main.py` (depende de T015).
- [ ] T018 [P] [US2] Agregar tipos y métodos de API en `frontend/src/types/routineTemplate.ts` y `frontend/src/services/routineTemplateService.ts`.
- [ ] T019 [US2] Crear `frontend/src/components/RoutineTemplateCard.tsx`, `frontend/src/components/RoutineTemplateDetail.tsx` y `frontend/src/pages/RoutineTemplatesPage.tsx` con editor de días, bloques y ejercicios, usando estilos de `frontend/src/styles/routine-templates.css` importados en `frontend/src/styles.css`.
- [ ] T020 [US2] Crear `frontend/src/pages/StudentRoutinesPage.tsx` en solo lectura, con estado vacío.
- [ ] T021 [US2] Registrar las rutas `trainerRoutines: '/entrenador/rutinas'` y `studentRoutines: '/alumno/rutinas'` en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`, y agregar los accesos en `frontend/src/pages/HomePage.tsx`.
- [ ] T022 [US2] Ejecutar `pytest backend/tests --cov=backend/src --cov-fail-under=90`, `ruff check backend`, `npm run build` y validar el Escenario 2 de `taskify/specs/005-exercise-library-and-templates/quickstart.md`.

**Checkpoint**: US-09 está completa y lista para abrir PR hacia `develop`.

---

## Dependencies & Execution Order

- **Phase 1** no tiene dependencias y se entrega en el PR de US-08.
- **Phase 2 (US-08)** depende de Phase 1.
- **Phase 3 (US-09)** depende de US-08 mergeada en `develop` (Principio VII), porque las rutinas referencian ejercicios y la regla "Sin materiales" usa su marca.

## Parallel Opportunities

- US-08: T003, T005 y T008 tocan archivos independientes.
- US-09: T012, T014 y T018 tocan archivos independientes.

## Implementation Strategy

1. Completar Phase 1 y US-08, y mergear su PR con CI verde.
2. Actualizar `develop`, completar US-09 desde una rama nueva y abrir su PR.
3. Ejecutar `/speckit-converge` por story antes de abrir cada PR.
