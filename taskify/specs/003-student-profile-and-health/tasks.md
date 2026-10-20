# Tasks: Perfil del Alumno, Cuestionario de Salud y Apto Médico (alcance: US-39 ajuste + US-40 + US-41)

**Input**: `specs/003-student-profile-and-health/` (plan.md, spec.md, data-model.md, research.md §4-5, contracts/student-health-api.yaml, quickstart.md)

**Alcance de este tasks.md**: ajuste de US-39 (nombre/apellido) y US-40 completa, según las clarificaciones del 2026-10-20. Se agrega US-41 (cuestionario de salud, clarificaciones del 2026-10-21; T013–T022). US-42 y US-43 no se incluyen; se generan en una corrida posterior. T001–T012 (US-39/US-40) ya están implementadas y mergeadas (PR #10).

**Estado previo**: ya existen `StudentProfile` (con `full_name`), `GET/PUT /students/me/profile`, `StudentProfileEditPage.tsx` y `backend/tests/test_student_api.py`. El esquema se crea con `Base.metadata.create_all` (no hay Alembic): ver T001.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivos distintos, sin dependencias pendientes)
- **[US1]** = US-39 (ajuste de nombre/teléfono), **[US2]** = US-40 (objetivos y onboarding), **[US3]** = US-41 (cuestionario de salud)

---

## Phase 1: Foundational (bloquea ambas historias)

- [X] T001 Reemplazar `full_name` por `first_name` (String(100), obligatorio para publicar) y `last_name` (String(100), obligatorio para publicar) en `backend/src/models/student_profile.py`; agregar `fitness_goals` (JSON, no nulo, default `[]`) y `personal_motivation` (Text, nulo). Como no hay Alembic, documentar en el PR que las bases locales existentes deben recrearse (`create_all` no altera tablas).
- [X] T002 [P] Agregar el catálogo cerrado en `backend/src/core/constants.py`: `FITNESS_GOALS = frozenset({"fuerza", "hipertrofia", "resistencia", "perdida_de_peso", "salud_general", "movilidad_rehabilitacion"})`.
- [X] T003 Actualizar `backend/src/schemas/student.py`: `StudentProfileUpdate` y `StudentProfileResponse` con `first_name`, `last_name`, `fitness_goals: list[str]` (sin repetidos; cada valor debe pertenecer a `FITNESS_GOALS`, si no 422) y `personal_motivation: str | None`; mantener `PHONE_PATTERN = ^\+?[0-9]{10,15}$` y corregir el mensaje a "El teléfono debe tener entre 10 y 15 dígitos, con '+' opcional al inicio".

**Checkpoint**: modelo y schemas listos.

---

## Phase 2: User Story 1 — Nombre y apellido separados (US-39, P1)

**Goal**: el perfil usa nombre y apellido obligatorios y teléfono con formato `+` opcional + 10-15 dígitos.
**Independent Test**: `PUT /students/me/profile` con `first_name`/`last_name` válidos devuelve 200; sin apellido no publica; teléfono con espacios devuelve 422.

- [X] T004 [US1] Actualizar `backend/tests/test_student_api.py` a `first_name`/`last_name` (reemplaza `full_name` en los 3 tests existentes) y agregar casos: falta `last_name` → perfil queda `DRAFT`; teléfono `+54 9 11 4444-5555` → 422; teléfono de 16 dígitos → 422.
- [X] T005 [US1] Actualizar `backend/src/services/student_service.py` (`update_profile`): usar `first_name` y `last_name` en `proposed` y en los campos requeridos del mensaje de error 422 ("must keep first name, last name, birth date and contact phone").
- [X] T006 [P] [US1] Actualizar `frontend/src/types/student.ts` y `frontend/src/pages/StudentProfileEditPage.tsx`: reemplazar `full_name` por dos inputs (`first_name`, `last_name`, `maxLength={100}`, "Este campo es obligatorio" en rojo) y mostrar el mensaje de teléfono nuevo.

**Checkpoint**: US-39 funciona con el modelo de nombre aclarado.

---

## Phase 3: User Story 2 — Objetivos y onboarding (US-40, P1)

**Goal**: el alumno elige ≥1 objetivo del catálogo cerrado y una motivación opcional; el perfil solo pasa a `PUBLISHED` con datos personales + ≥1 objetivo; los entrenadores autorizados pueden leerlos.
**Independent Test**: `quickstart.md` Escenario 1 (200 `PUBLISHED`; `[]` → 422; objetivo fuera de catálogo → 422; edición refleja cambios de inmediato).

- [X] T007 [P] [US2] Tests en `backend/tests/test_student_api.py`: (a) con datos personales + `["fuerza","salud_general"]` → 200 y `status == "PUBLISHED"`; (b) `fitness_goals=[]` → perfil `DRAFT`, no publicado; (c) objetivo `"yoga"` → 422; (d) duplicados `["fuerza","fuerza"]` → 422; (e) PUT posterior con otros objetivos → GET inmediato devuelve los nuevos; (f) `personal_motivation` ausente no impide publicar; (g) un perfil `PUBLISHED` no puede quedar con `fitness_goals=[]` (422).
- [X] T008 [US2] En `backend/src/services/student_service.py`: agregar `fitness_goals` a la regla de completitud (`complete` = nombre, apellido, fecha de nacimiento, teléfono y `len(fitness_goals) >= 1`); un perfil `PUBLISHED` que quede incompleto devuelve 422 con `{"field": "fitness_goals", ...}`.
- [X] T009 [P] [US2] Tests de visibilidad en `backend/tests/test_student_api.py` para `GET /api/v1/students/{student_id}/goals`: el propio alumno → 200; entrenador sin relación → 403; alumno inexistente → 404.
- [X] T010 [US2] Implementar `GET /students/{student_id}/goals` en `backend/src/api/v1/students.py` y `get_goals_for_viewer(db, viewer, student_id)` en `backend/src/services/student_service.py`: permitir al propio alumno; para un entrenador, consultar una función `trainer_has_access(db, trainer_id, student_id)` que **hoy devuelve `False`** (`# ponytail: stub hasta que exista TrainingRequest/TrainingRelationship en la spec 004; reemplazar por la consulta real de solicitud pendiente o relación ACTIVE`). Respuesta: `{fitness_goals, personal_motivation}`; 403 si no hay acceso.
- [X] T011 [P] [US2] Frontend: en `frontend/src/types/student.ts` agregar `FitnessGoal` (los 6 valores) y `fitness_goals`/`personal_motivation`; en `frontend/src/pages/StudentProfileEditPage.tsx` agregar selector múltiple de los 6 objetivos con etiquetas en español (Fuerza, Hipertrofia, Resistencia, Pérdida de peso, Salud general, Movilidad/rehabilitación), textarea opcional de motivación, y mostrar el mensaje "Elegí al menos un objetivo para publicar tu perfil" si no hay ninguno (Guardar sigue habilitado para borradores; el perfil queda `DRAFT`).
- [X] T012 [US2] Validar el Escenario 1 de `specs/003-student-profile-and-health/quickstart.md` contra la API local y correr `pytest --cov` verificando cobertura ≥ 90 % (Principio VI). *(Hecho: los casos del Escenario 1 están cubiertos por tests automatizados y cobertura 97 %; el recorrido manual con curl no se ejecutó.)*

**Checkpoint**: US-40 completa salvo la lectura real por entrenadores (depende de la spec 004).

---

## Phase 4: User Story 3 — Cuestionario de salud (US-41, P1)

**Goal**: el alumno completa un cuestionario de salud de 5 preguntas Sí/No; cada envío crea una versión vigente; el perfil expone si está completo; existe una validación reutilizable para las specs 004 y 006; el entrenador autorizado lee solo la versión vigente con aviso de riesgo.
**Independent Test**: `quickstart.md` Escenario 1, paso 2 (201 con `CURRENT`; pregunta omitida → 422; reenvío deja una sola `CURRENT`; `health_questionnaire_completed` pasa a `true`).

- [ ] T013 [US3] Crear `backend/src/models/health_questionnaire.py` con `HealthQuestionnaire` (tabla `health_questionnaires`) y exportarlo en `backend/src/models/__init__.py`. Campos según `data-model.md` §2: `id` String(36) PK default `new_id`; `student_id` FK a `student_profiles.id` (String(36), no nulo, índice, 1:N); `status` String(16) no nulo default `CURRENT` (`CURRENT` o `ARCHIVED`); `has_heart_condition`, `has_chest_pain_activity`, `has_dizziness_or_balance_loss`, `has_bone_joint_problem`, `takes_prescription_meds` Boolean no nulos **sin valor por defecto** (respuesta explícita obligatoria); `other_medical_conditions` Text nulo; `completed_at` DateTime no nulo (fecha de creación de la versión). Sin campos de objetivos.
- [ ] T014 [P] [US3] Crear `backend/src/schemas/student_health.py`: `HealthQuestionnaireInput` con las 5 preguntas como `bool` **requeridas** (omitida → 422, no se asume "No"; `null` también 422) y `other_medical_conditions: str | None = None`; `HealthQuestionnaireResponse` con `id`, las 5 preguntas, `other_medical_conditions`, `status`, `has_risk_answers` (derivado: alguna de las 5 en `true`) y `completed_at`. Mensajes de error en inglés, como el resto del backend.
- [ ] T015 [US3] Tests en `backend/tests/test_student_health_api.py` (reutilizar fixtures de `conftest.py`): (a) POST con las 5 respuestas → 201, `status == "CURRENT"`, `has_risk_answers` correcto (true con algún Sí, false con todos No); (b) omitir cualquiera de las 5 → 422, y `null` → 422; (c) sin `other_medical_conditions` → 201; (d) segundo POST → 201 y `GET /students/me/health-questionnaire` devuelve solo la nueva, con una única fila `CURRENT` y la anterior `ARCHIVED` en base; (e) GET propio sin cuestionario → 404; (f) `GET /students/me/profile` devuelve `health_questionnaire_completed` `false` antes y `true` después; (g) rol TRAINER en `/students/me/health-questionnaire` → 403; (h) `GET /students/{student_profile_id}/health-questionnaire`: propio alumno → 200, otro alumno → 403, entrenador sin relación → 403 (stub), alumno inexistente → 404; (i) `require_health_questionnaire` lanza `StudentProfileError` 403 sin cuestionario y no lanza con `CURRENT`.
- [ ] T016 [US3] En `backend/src/services/student_service.py` agregar: `save_health_questionnaire(db, user, payload)` (exige alumno; en una sola transacción pasa la `CURRENT` previa a `ARCHIVED` e inserta la nueva `CURRENT`); `get_current_questionnaire(db, profile)` (404 si no hay); `is_questionnaire_completed(profile)` (existe fila `CURRENT`); `require_health_questionnaire(db, profile)` que lanza `StudentProfileError(403, "You must complete the health questionnaire first.")` si falta (reutilizable por las specs 004 y 006); y `get_questionnaire_for_viewer(db, viewer, student_profile_id)` con la misma regla de acceso que `get_goals_for_viewer` (propio alumno, o entrenador vía `trainer_has_access`; si no, 403; inexistente 404). Nunca devolver filas `ARCHIVED`.
- [ ] T017 [US3] En `backend/src/api/v1/students.py` agregar `GET` y `POST /students/me/health-questionnaire` (POST responde 201) y `GET /students/{student_id}/health-questionnaire` (`student_id` = `StudentProfile.id`), usando `handle_error` como los endpoints existentes. Declarar `/me/health-questionnaire` antes de `/{student_id}/...` para que `me` no se interprete como id.
- [ ] T018 [US3] Agregar `health_questionnaire_completed: bool` a `StudentProfileResponse` (`backend/src/schemas/student.py`) y poblarlo en `profile_response` de `backend/src/api/v1/students.py` con `is_questionnaire_completed` (derivado, no es columna). Ajustar los tests existentes de `backend/tests/test_student_api.py` que comparan la respuesta del perfil si hace falta.
- [ ] T019 [P] [US3] Frontend: crear `frontend/src/services/studentHealthService.ts` (`getOwnHealthQuestionnaire`, `saveHealthQuestionnaire` con `api.ts`) y tipos `HealthQuestionnaire`/`HealthQuestionnaireInput` en `frontend/src/types/student.ts`; agregar `health_questionnaire_completed: boolean` a `StudentProfile`.
- [ ] T020 [US3] Frontend: crear `frontend/src/pages/HealthQuestionnairePage.tsx` con las 5 preguntas como grupos Sí/No **sin opción preseleccionada** (radios con `<fieldset>`/`<legend>`), campo opcional "Otras condiciones médicas", envío deshabilitado hasta responder las 5 y mensaje "Respondé todas las preguntas" resaltado en rojo; precargar la versión vigente si existe; tras guardar, mostrar confirmación. Sin sección de objetivos. Registrar la ruta `studentHealth: '/alumno/salud'` en `frontend/src/constants/routes.ts` y en `frontend/src/App.tsx` (rol alumno) y enlazarla desde `HomePage.tsx` para el alumno con `health_questionnaire_completed === false`.
- [ ] T021 [US3] Validar que `cd frontend && npm run build` pasa y que el Escenario 1 paso 2 de `quickstart.md` queda cubierto por los tests de T015.
- [ ] T022 [US3] Correr `ruff check backend` y `python -m pytest backend/tests --cov=backend/src --cov-fail-under=90` (Principio VI) y corregir lo que falle.

**Checkpoint**: US-41 completa; el acceso de entrenadores sigue pendiente de la spec 004 (`trainer_has_access` stub) y la aplicación de `require_health_questionnaire` en enviar solicitud (spec 004) y acceder a rutina (spec 006).

---

## Dependencies & Execution Order

- T001 → T003 → (T004, T005) y (T007, T008); T002 antes de T003.
- US1 y US2 comparten `student_service.py` y `test_student_api.py`: ejecutar T004/T005 antes de T007/T008. Frontend T006 y T011 tocan la misma página: T006 primero.
- T009 → T010. T012 al final.
- US-41: T013 → T016 → T017; T014 antes de T016; T015 (tests) antes de T016/T017; T018 después de T016; T019 → T020; T021 y T022 al final. T016, T017 y T018 tocan `student_service.py`/`students.py`: secuenciales.

## Parallel Opportunities

- T014 y T019 (archivos nuevos, sin dependencias) junto a T013; T015 en paralelo con T019/T020.
- T002 junto a T001. T006 (frontend) junto a T004/T005. T007, T009 y T011 son paralelizables entre sí tras T003.

## Implementation Strategy

1. MVP: Foundational + US1 (T001–T006), luego US2 (T007–T012).
2. US-41 (T013–T022) en rama `feature/us41`: modelo y schemas, tests, servicio y endpoints, indicador en el perfil y luego frontend.
3. Pendiente fuera de alcance: reemplazar el stub de `trainer_has_access` y aplicar `require_health_questionnaire` al enviar solicitud (spec 004) y acceder a rutina (spec 006); US-42 y US-43 en otro `/speckit-tasks`.
