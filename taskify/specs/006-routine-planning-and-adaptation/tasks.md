---
description: "Task list for 006-routine-planning-and-adaptation (US-13, US-14, US-53 and US-54)"
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

# Tasks: Edición de Rutina (US-14) y Variantes Seguras (US-53)

**Input**: `plan.md`, `spec.md` (User Story 2 = US-14), `data-model.md`, `research.md`, `contracts/student-routine-edit-api.yaml`, `contracts/safe-variants-api.yaml`

**Alcance**: US-14 (Fases 1–4), US-53 (Fases 5–6) y US-54 (Fases 7–8). US-13 y US-55 quedan fuera de este documento (Principio VII, un PR por story).

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
- [X] T014 Recorrer manualmente `quickstart.md` y marcar `[x]` las tareas completadas.

## Phase 5: User Story US-53 — Variantes seguras (P1)

**Objetivo**: el alumno con restricciones ve una variante segura (con su video o explicación) de los ejercicios de riesgo; si no hay, el ejercicio se bloquea, puede saltearlo y el entrenador recibe una única notificación.

**Prueba independiente**: seguir los 6 escenarios de la sección US-53 de `quickstart.md`.

**Prerrequisito**: Fases 1–3 (US-14) completas: se reutilizan `Exercise.contraindicated_zones`, `find_conflicts` y `norm` de `backend/src/services/student_routine_service.py`.

### Tests

- [X] T015 [P] [US53] Tests de servicio (cubiertos en `backend/tests/test_safe_variant_api.py` junto con T016, vía la API) : resolución `SAFE` (sin conflicto) / `VARIANT` (variante con `covered_zones` ⊇ conflicto; si hay varias, la de menor `created_at`) / `BLOCKED` (ninguna cubre todas las zonas, p. ej. rodilla + hombro con variante solo de rodilla); notificación única por caso `PENDING` ante consultas repetidas; reapertura del caso `RESOLVED` → `PENDING` con nueva notificación; creación/edición de variante que cubre el conflicto → casos `PENDING` a `RESOLVED`; cambios de zonas protegidas o de variante reflejados en la consulta siguiente (sin snapshot).
- [X] T016 [P] [US53] Tests de API en `backend/tests/test_safe_variant_api.py` por escenario de aceptación 1–3 de US-53: variante mostrada con nombre, descripción y `video_url`/`video_platform` (esc. 1 y 3), `BLOCKED` con `can_skip: true` y una sola `Notification` al entrenador (esc. 2), `422` en alta con `covered_zones` fuera de `contraindicated_zones` del ejercicio de riesgo o con variante contraindicada para esas zonas, `409` por variante duplicada, `404` si el ejercicio no está en la rutina vigente del alumno o es ajeno, `403` sin vínculo ACTIVE o con otro entrenador.

### Implementación

- [X] T017 [P] [US53] Crear `backend/src/models/safe_variant.py` con `ExerciseSafeVariant` (`id`, `exercise_id` FK `exercises`, `variant_exercise_id` FK `exercises`, `covered_zones` JSON lista de textos normalizados no vacía, `created_at`, `updated_at` UTC; único por (`exercise_id`, `variant_exercise_id`)) y `SafeVariantCase` (`id`, `student_id` FK `student_profiles`, `exercise_id` FK `exercises`, `status` `PENDING` | `RESOLVED`, `created_at`, `resolved_at` nullable; único por (`student_id`, `exercise_id`)); registrarlos en `backend/src/models/__init__.py` y en los imports de `backend/src/main.py`.
- [X] T018 [P] [US53] Crear `backend/src/schemas/safe_variant.py`: `SafeVariantInput` (`variant_exercise_id`, `covered_zones` `minItems: 1`), `SafeVariantResponse`, `SafeVariantResolution` (`status` `SAFE` | `VARIANT` | `BLOCKED`, `variant` con `exercise_id`, `name`, `description`, `video_url`, `video_platform`, `message`, `can_skip`) según `contracts/safe-variants-api.yaml`.
- [X] T019 [US53] Implementar `backend/src/services/safe_variant_service.py`: alta/edición/baja de variantes (valida que ambos ejercicios sean del entrenador y no estén dados de baja, `exercise_id` ≠ `variant_exercise_id`, `covered_zones` ⊆ `contraindicated_zones` del ejercicio de riesgo, la variante sin contraindicación en esas zonas; normaliza con `norm`; errores `422`/`409` con la clase de error existente RFC 7807 `errors[]`) y `resolve_for_student(db, user, exercise_id)` que calcula `conflicto = zonas del ejercicio ∩ ProtectedZone.body_area` (misma normalización que `find_conflicts`), elige la variante activa más antigua con cobertura total, abre o reabre `SafeVariantCase` y emite una sola `create_notification` (`type="SAFE_VARIANT_MISSING"`, `related_entity_type="SAFE_VARIANT_CASE"`) solo al pasar a `PENDING`; al crear/editar/quitar variantes recalcula los casos `PENDING` del ejercicio (cubiertos → `RESOLVED`). Autoriza en backend: vínculo ACTIVE y ejercicio presente en la `StudentRoutine` vigente del alumno (`404` si no).
- [X] T020 [US53] Implementar `backend/src/api/v1/safe_variants.py` (`GET/POST /exercises/{exerciseId}/safe-variants`, `PUT/DELETE .../{variantId}`, `GET /students/me/exercises/{exerciseId}/safe-variant`) siguiendo el patrón de `backend/src/api/v1/student_routines.py` (`fail`, `CurrentUser`, `DbDep`); incluir el router en `backend/src/main.py`.
- [X] T021 [US53] Integrar con US-14: en `find_conflicts` de `backend/src/services/student_routine_service.py` completar `safe_variant` en cada conflicto con la variante resuelta (nombre y `exercise_id`) en lugar de `null`; actualizar `backend/src/schemas/student_routine.py` si hace falta y agregar un test en `backend/tests/test_student_routine_api.py`.
- [X] T022 [P] [US53] Tipos y cliente HTTP en `frontend/src/types/safeVariant.ts` y `frontend/src/services/safeVariantService.ts`.
- [X] T023 [US53] Gestión de variantes del entrenador en `frontend/src/pages/ExerciseLibraryPage.tsx`: listar, agregar (elegir ejercicio variante y zonas cubiertas con `BODY_AREAS` de `frontend/src/constants/bodyAreas.ts`), editar zonas y quitar; errores `422` por campo. Controles ≥ 44×44 px, contraste 4.5:1.
- [X] T024 [US53] Vista del alumno en `frontend/src/pages/StudentRoutinesPage.tsx`: para cada ejercicio de riesgo consultar `safe-variant`; `VARIANT` muestra la variante con su video embebido o explicación (sin redirigir fuera de la app, Principio V); `BLOCKED` muestra el aviso de que no hay variante segura y un botón "Saltear" (solo oculta el ejercicio en la vista; el registro del salto queda para la spec 007).

**Checkpoint**: US-53 funcional y probable por sí sola.

## Phase 6: Polish US-53

- [X] T025 [P] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build` en `frontend/`; corregir fallas.
- [X] T026 Recorrer manualmente la sección US-53 de `quickstart.md` y marcar `[x]` las tareas completadas.

## Dependencias

T001 → T002/T003/T004 (paralelas) → T005/T006 (paralelas) → T007 → T008 → T009 → T010 → T011; T012 depende solo de T002. T013–T014 al final.

## Estrategia

Todo es una sola story: entregar en un único PR hacia `develop`. Orden sugerido: backend completo (T002–T009) verificado con tests, luego frontend (T010–T012).

**US-53**: T015/T016 (tests, paralelos) y T017/T018 (paralelos) → T019 → T020 → T021; T022 paralelo desde T018; T023 y T024 dependen de T020 y T022. T025–T026 al final.

## Estrategia US-53

Un único PR hacia `develop`, separado del de US-14. Orden: modelos y schemas (T017–T018) → servicio con sus tests en rojo (T015–T016, T019) → API (T020) → integración con US-14 (T021) → frontend (T022–T024). MVP: backend completo hasta T021 verificado con tests; el frontend puede mergearse en el mismo PR.

## Phase 7: User Story US-54 — Alternativa o reemplazo de ejercicio (P2)

**Objetivo**: el alumno pide alternativas calculadas (mismo `target_muscle_group`, biblioteca del entrenador, sin zonas de riesgo propias), elige o saltea; el reemplazo vale solo para la sesión del día, se registra para el entrenador y no modifica la rutina.

**Prueba independiente**: seguir los 8 escenarios de la sección US-54 de `quickstart.md`.

**Prerrequisito**: US-14 y US-53 mergeadas en `develop` (se reutilizan `norm`, `find_conflicts` de `backend/src/services/student_routine_service.py` y la resolución de `backend/src/services/safe_variant_service.py`). No depende de la spec 007 (research D16).

### Tests

- [ ] T027 [P] [US54] Tests de servicio en `backend/tests/test_exercise_alternative_service.py`: alternativas = mismo `target_muscle_group`, mismo entrenador, `deleted_at` nulo, distintas del original, sin intersección entre `contraindicated_zones` y `ProtectedZone.body_area` normalizadas; independientes de la modalidad GYM/HOME; lista vacía → `can_skip: true`; sobrescritura: una sola fila por (`student_id`, `routine_id`, `day_name`, `session_date`, `original_exercise_id`) con la última elección; salto = `replacement_exercise_id` nulo; la `StudentRoutine` vigente no cambia.
- [ ] T028 [P] [US54] Tests de API en `backend/tests/test_exercise_alternative_api.py` por escenario de aceptación 1–4 de US-54 (esc. 1 lista de alternativas, esc. 2 filtro por grupo y zonas de riesgo, esc. 3 elección registrada sin tocar la rutina y sin notificación, esc. 4 sin alternativas → salto registrado) más: ejercicio fuera de la rutina vigente → `404`; sin vínculo ACTIVE → `403`; alternativa fuera de la lista → `422` problem+json con `errors[]`; la respuesta no expone zonas protegidas.
- [ ] T029 [P] [US54] Test de rendimiento (SC-003) en `backend/tests/test_exercise_alternative_api.py`: biblioteca de ~300 ejercicios, `GET .../alternatives` responde en < 2 s.

### Implementación

- [ ] T030 [P] [US54] Crear `backend/src/models/exercise_replacement_log.py` con `ExerciseReplacementLog`: `id` (String(36)), `student_id` FK `student_profiles`, `routine_id`, `day_name` (String(100)), `session_date` (fecha UTC), `original_exercise_id` FK `exercises`, `replacement_exercise_id` FK `exercises` nullable (nulo = salto), `updated_at` UTC; único por (`student_id`, `routine_id`, `day_name`, `session_date`, `original_exercise_id`); registrarlo en `backend/src/models/__init__.py` y en los imports de `backend/src/main.py`.
- [ ] T031 [P] [US54] Crear `backend/src/schemas/exercise_alternative.py` según `contracts/exercise-alternatives-api.yaml`: `Alternative` (`exercise_id`, `name`, `equipment_needed`, `variant` nullable), respuesta con `alternatives[]` y `can_skip`, y `ReplacementInput` (`routine_id`, `day_name`, `original_exercise_id`, `replacement_exercise_id` nullable).
- [ ] T032 [US54] Implementar `backend/src/services/exercise_alternative_service.py`: `list_alternatives` (valida vínculo ACTIVE y que el ejercicio esté en la rutina vigente; consulta única filtrada por `trainer_id` y `target_muscle_group`; excluye original y dados de baja; excluye zonas de riesgo reutilizando `norm`; completa `variant` con la resolución de US-53 si la alternativa lo requiere) y `record_replacement` (upsert; valida que la alternativa figure en la lista vigente; `session_date` = hoy UTC; no modifica `StudentRoutine`). Errores con la clase RFC 7807 existente.
- [ ] T033 [US54] Implementar `backend/src/api/v1/exercise_alternatives.py` (`GET /students/me/exercises/{exerciseId}/alternatives`, `PUT /students/me/exercise-replacements`) reutilizando `deps.py` según el patrón de `backend/src/api/v1/safe_variants.py`, y registrar el router en `backend/src/main.py`.
- [ ] T034 [P] [US54] Tipos y cliente HTTP en `frontend/src/types/exerciseAlternative.ts` y `frontend/src/services/exerciseAlternativeService.ts`.
- [ ] T035 [US54] Interfaz del alumno en `frontend/src/pages/StudentRoutinesPage.tsx` (y componente `frontend/src/components/ExerciseAlternativesPanel.tsx`): botón "Sustituir" por ejercicio (≥ 44×44 px), lista de alternativas, elegir (reemplaza la elección previa), aviso y botón "Saltear" cuando la lista está vacía; las series se registran con el `exercise_id` elegido; estilos en `frontend/src/styles/`.

**Checkpoint**: US-54 funcional y probable por sí sola.

## Phase 8: Polish US-54

- [ ] T036 [P] Correr `ruff check backend`, `pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build` en `frontend/`; corregir fallas.
- [ ] T037 Recorrer manualmente la sección US-54 de `quickstart.md` y marcar `[x]` las tareas completadas.

## Estrategia US-54

Un único PR hacia `develop`, separado de US-14 y US-53. Orden: T030/T031 (paralelas) → T027–T029 (tests en rojo, paralelos) → T032 → T033 → T034 → T035 → T036–T037. MVP: backend completo hasta T033; la UI (T034–T035) cierra la story.

**Decisión abierta (E2)**: si el original ya tiene variante segura (US-53), se muestra primero esa variante y las alternativas se piden aparte con "Sustituir"; confirmar al implementar T035.
