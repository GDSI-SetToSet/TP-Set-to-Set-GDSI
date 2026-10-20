# Tasks: Perfil del Alumno, Cuestionario de Salud y Apto Médico (alcance: US-39 ajuste + US-40)

**Input**: `specs/003-student-profile-and-health/` (plan.md, spec.md, data-model.md, research.md §4, contracts/student-health-api.yaml, quickstart.md)

**Alcance de este tasks.md**: ajuste de US-39 (nombre/apellido) y US-40 completa, según las clarificaciones del 2026-10-20. US-41, US-42 y US-43 no se incluyen; se generan en una corrida posterior.

**Estado previo**: ya existen `StudentProfile` (con `full_name`), `GET/PUT /students/me/profile`, `StudentProfileEditPage.tsx` y `backend/tests/test_student_api.py`. El esquema se crea con `Base.metadata.create_all` (no hay Alembic): ver T001.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivos distintos, sin dependencias pendientes)
- **[US1]** = US-39 (ajuste de nombre/teléfono), **[US2]** = US-40 (objetivos y onboarding)

---

## Phase 1: Foundational (bloquea ambas historias)

- [ ] T001 Reemplazar `full_name` por `first_name` (String(100), obligatorio para publicar) y `last_name` (String(100), obligatorio para publicar) en `backend/src/models/student_profile.py`; agregar `fitness_goals` (JSON, no nulo, default `[]`) y `personal_motivation` (Text, nulo). Como no hay Alembic, documentar en el PR que las bases locales existentes deben recrearse (`create_all` no altera tablas).
- [ ] T002 [P] Agregar el catálogo cerrado en `backend/src/core/constants.py`: `FITNESS_GOALS = frozenset({"fuerza", "hipertrofia", "resistencia", "perdida_de_peso", "salud_general", "movilidad_rehabilitacion"})`.
- [ ] T003 Actualizar `backend/src/schemas/student.py`: `StudentProfileUpdate` y `StudentProfileResponse` con `first_name`, `last_name`, `fitness_goals: list[str]` (sin repetidos; cada valor debe pertenecer a `FITNESS_GOALS`, si no 422) y `personal_motivation: str | None`; mantener `PHONE_PATTERN = ^\+?[0-9]{10,15}$` y corregir el mensaje a "El teléfono debe tener entre 10 y 15 dígitos, con '+' opcional al inicio".

**Checkpoint**: modelo y schemas listos.

---

## Phase 2: User Story 1 — Nombre y apellido separados (US-39, P1)

**Goal**: el perfil usa nombre y apellido obligatorios y teléfono con formato `+` opcional + 10-15 dígitos.
**Independent Test**: `PUT /students/me/profile` con `first_name`/`last_name` válidos devuelve 200; sin apellido no publica; teléfono con espacios devuelve 422.

- [ ] T004 [US1] Actualizar `backend/tests/test_student_api.py` a `first_name`/`last_name` (reemplaza `full_name` en los 3 tests existentes) y agregar casos: falta `last_name` → perfil queda `DRAFT`; teléfono `+54 9 11 4444-5555` → 422; teléfono de 16 dígitos → 422.
- [ ] T005 [US1] Actualizar `backend/src/services/student_service.py` (`update_profile`): usar `first_name` y `last_name` en `proposed` y en los campos requeridos del mensaje de error 422 ("must keep first name, last name, birth date and contact phone").
- [ ] T006 [P] [US1] Actualizar `frontend/src/types/student.ts` y `frontend/src/pages/StudentProfileEditPage.tsx`: reemplazar `full_name` por dos inputs (`first_name`, `last_name`, `maxLength={100}`, "Este campo es obligatorio" en rojo) y mostrar el mensaje de teléfono nuevo.

**Checkpoint**: US-39 funciona con el modelo de nombre aclarado.

---

## Phase 3: User Story 2 — Objetivos y onboarding (US-40, P1)

**Goal**: el alumno elige ≥1 objetivo del catálogo cerrado y una motivación opcional; el perfil solo pasa a `PUBLISHED` con datos personales + ≥1 objetivo; los entrenadores autorizados pueden leerlos.
**Independent Test**: `quickstart.md` Escenario 1 (200 `PUBLISHED`; `[]` → 422; objetivo fuera de catálogo → 422; edición refleja cambios de inmediato).

- [ ] T007 [P] [US2] Tests en `backend/tests/test_student_api.py`: (a) con datos personales + `["fuerza","salud_general"]` → 200 y `status == "PUBLISHED"`; (b) `fitness_goals=[]` → perfil `DRAFT`, no publicado; (c) objetivo `"yoga"` → 422; (d) duplicados `["fuerza","fuerza"]` → 422; (e) PUT posterior con otros objetivos → GET inmediato devuelve los nuevos; (f) `personal_motivation` ausente no impide publicar; (g) un perfil `PUBLISHED` no puede quedar con `fitness_goals=[]` (422).
- [ ] T008 [US2] En `backend/src/services/student_service.py`: agregar `fitness_goals` a la regla de completitud (`complete` = nombre, apellido, fecha de nacimiento, teléfono y `len(fitness_goals) >= 1`); un perfil `PUBLISHED` que quede incompleto devuelve 422 con `{"field": "fitness_goals", ...}`.
- [ ] T009 [P] [US2] Tests de visibilidad en `backend/tests/test_student_api.py` para `GET /api/v1/students/{student_id}/goals`: el propio alumno → 200; entrenador sin relación → 403; alumno inexistente → 404.
- [ ] T010 [US2] Implementar `GET /students/{student_id}/goals` en `backend/src/api/v1/students.py` y `get_goals_for_viewer(db, viewer, student_id)` en `backend/src/services/student_service.py`: permitir al propio alumno; para un entrenador, consultar una función `trainer_has_access(db, trainer_id, student_id)` que **hoy devuelve `False`** (`# ponytail: stub hasta que exista TrainingRequest/TrainingRelationship en la spec 004; reemplazar por la consulta real de solicitud pendiente o relación ACTIVE`). Respuesta: `{fitness_goals, personal_motivation}`; 403 si no hay acceso.
- [ ] T011 [P] [US2] Frontend: en `frontend/src/types/student.ts` agregar `FitnessGoal` (los 6 valores) y `fitness_goals`/`personal_motivation`; en `frontend/src/pages/StudentProfileEditPage.tsx` agregar selector múltiple de los 6 objetivos con etiquetas en español (Fuerza, Hipertrofia, Resistencia, Pérdida de peso, Salud general, Movilidad/rehabilitación), textarea opcional de motivación, y bloquear "Guardar/Finalizar" con mensaje "Elegí al menos un objetivo" si no hay ninguno.
- [ ] T012 [US2] Validar el Escenario 1 de `specs/003-student-profile-and-health/quickstart.md` contra la API local y correr `pytest --cov` verificando cobertura ≥ 90 % (Principio VI).

**Checkpoint**: US-40 completa salvo la lectura real por entrenadores (depende de la spec 004).

---

## Dependencies & Execution Order

- T001 → T003 → (T004, T005) y (T007, T008); T002 antes de T003.
- US1 y US2 comparten `student_service.py` y `test_student_api.py`: ejecutar T004/T005 antes de T007/T008. Frontend T006 y T011 tocan la misma página: T006 primero.
- T009 → T010. T012 al final.

## Parallel Opportunities

- T002 junto a T001. T006 (frontend) junto a T004/T005. T007, T009 y T011 son paralelizables entre sí tras T003.

## Implementation Strategy

1. MVP: Foundational + US1 (T001–T006), luego US2 (T007–T012).
2. Pendiente fuera de alcance: reemplazar el stub de `trainer_has_access` cuando exista la spec 004; US-41–43 en otro `/speckit-tasks`.
