---
description: "Lista de tareas de US-65 de la feature 010"
---

# Tasks: US-65 — Evolución de cargas, constancia y récords personales (PRs)

**Entrada**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/student-progress-api.yaml`, `quickstart.md`

**Alcance**: solo US-65 (única story de este plan). US-67 y US-68 no se implementan. Sin tablas ni migraciones nuevas.

**Pruebas**: obligatorias por Principio VI (backend con Pytest, cobertura ≥ 90 %; frontend con `npm run build`).

**Formato**: `- [ ] T### [P?] [US1] Descripción con ruta`. `[P]` = archivos distintos y sin dependencias pendientes.

## Fase 1: Preparación

- [X] T001 Agregar `studentProgress: '/alumno/evolucion'` a `frontend/src/constants/routes.ts` y verificar en `backend/src/services/routine_template_service.py` (`create_student_workout_log`) y `backend/tests/conftest.py` cómo se crean alumno, vínculo, ejercicio y series para reutilizarlo en las pruebas.

## Fase 2: Fundacional (bloquea la story)

- [X] T002 [P] [US1] Definir los esquemas Pydantic de solo lectura `StudentProgress`, `ExerciseLoad`, `LoadPoint`, `WeeklyVolume`, `WeekComparison`, `PersonalRecordEntry` en `backend/src/schemas/student_progress.py`, con los campos de `data-model.md` y `contracts/student-progress-api.yaml` (`delta_vs_previous_pct` y `previous_weight_kg` nulos; `reps` texto registrado; `week_start`/`week_end`/`date` como fecha; `achieved_at` como fecha-hora UTC).
- [X] T003 [P] [US1] Definir los tipos TypeScript equivalentes en `frontend/src/types/studentProgress.ts`.

## Fase 3: US-65 (P2) — Mi evolución

**Objetivo**: el alumno ve la carga por ejercicio, el volumen semanal con comparación y el historial cronológico de PRs, con filtros por ejercicio, grupo muscular y fechas.

**Prueba independiente**: ejecutar `pytest backend/tests/test_us65_student_progress_api.py` y recorrer los 7 pasos manuales de `quickstart.md`.

### Backend

- [X] T004 [US1] Implementar en `backend/src/services/student_progress_service.py` el cálculo puro de series válidas: para PR y carga basta `weight_kg > 0`; para volumen además `reps_completed` numérico, usando `_number` de `session_comparison_service` (FR-001a/FR-001b).
- [X] T005 [US1] Implementar en el mismo servicio el historial de PRs (FR-001a): por ejercicio, en orden `recorded_at` y desempate `set_number`, una serie es PR solo si su peso supera **estrictamente** el máximo previo; la primera serie válida es PR inicial (`is_initial = true`, `previous_weight_kg` nulo). Calcular sobre todo el historial del alumno y filtrar después por rango, ejercicio y grupo; devolver en orden cronológico ascendente.
- [X] T006 [US1] Implementar en el mismo servicio el volumen semanal (FR-001b): Σ(`weight_kg` × reps) por semana lunes–domingo UTC, una entrada por semana del rango con 0 en semanas sin series, `is_partial = true` en la semana actual; más `WeekComparison` (semana actual vs. semana anterior y promedio de semanas completas previas; `delta_vs_previous_pct` nulo si la anterior es 0).
- [X] T007 [US1] Implementar en el mismo servicio la serie de carga por ejercicio: un punto por (ejercicio, día) con la mayor carga del día (más peso; a igual peso, más repeticiones), `is_pr` por punto, `has_trend = false` con menos de 2 puntos, `muscle_groups` con las opciones del filtro desde `Exercise.target_muscle_group`.
- [X] T008 [US1] Implementar `get_student_progress(db, user, exercise_id, muscle_group, from_, to)` en el mismo servicio: resolver el alumno con `get_or_create_profile` (solo datos propios), rango por defecto = últimas 12 semanas incl. la actual con `range.is_default = true` (FR-001c), filtros combinados con AND, `from > to` → error 422 RFC 7807. Agregar `# ponytail:` indicando que se leen todos los logs del alumno y que se agregará en SQL si el historial crece (SC-001, < 500 ms).
- [X] T009 [US1] Exponer `GET /api/v1/students/me/progress` (parámetros `exercise_id`, `muscle_group`, `from`, `to`) en `backend/src/api/v1/students.py` con `response_model=StudentProgress`, rol alumno (403 para entrenador, 401 sin token) y errores RFC 7807.
- [X] T010 [US1] Escribir `backend/tests/test_us65_student_progress_api.py` cubriendo: escenario 1 (carga por ejercicio), 2 (volumen semanal y comparación), 3 (semana en 0 sin afectar las demás), 4 (filtros por ejercicio, grupo y fechas, y combinados), 5 (PRs cronológicos con fecha; peso igual al máximo previo no es PR; PR inicial), series sin peso o con reps no numéricas ("45 seg") excluidas, rango por defecto de 12 semanas, `from > to` → 422 `application/problem+json`, `has_trend` falso con menos de 2 puntos, `has_data` falso sin series, aislamiento entre alumnos, 403 entrenador y 401 sin token.

### Frontend

- [X] T011 [P] [US1] Crear `frontend/src/services/studentProgressService.ts` con `getStudentProgress(filters)` tipado contra `frontend/src/types/studentProgress.ts`, usando el cliente de `frontend/src/services/api.ts`.
- [X] T012 [P] [US1] Crear `frontend/src/components/StudentProgressCharts.tsx` con tres bloques SVG propios (carga del ejercicio seleccionado, barras de volumen semanal con la semana parcial diferenciada y resumen de comparación, lista cronológica de PRs), reutilizando `niceTicks`, `formatDay`, `formatNumber`, `formatRange` de `frontend/src/utils/trainingEvolution.mjs`; `role="img"` + `aria-label` en cada gráfico y lista textual equivalente; contraste ≥ 4.5:1.
- [X] T013 [US1] Crear `frontend/src/pages/StudentProgressPage.tsx`: filtros (ejercicio, grupo muscular, desde/hasta; controles ≥ 44×44 px), estados de carga, error con mensaje comprensible y vacío; con `has_trend = false` mostrar el estado informativo "se requieren más sesiones para trazar la tendencia"; ejercicio por defecto = el de más puntos.
- [X] T014 [US1] Registrar la ruta protegida (rol alumno) en `frontend/src/App.tsx` y agregar el acceso "Mi evolución" en la home del alumno en `frontend/src/pages/HomePage.tsx`.
- [X] T015 [P] [US1] Agregar los estilos responsivos de la pantalla en `frontend/src/styles.css`, siguiendo las clases existentes de `training-evolution`.

## Fase 4: Verificación y cierre

- [ ] T016 Ejecutar `ruff check backend` y `pytest --cov=backend/src` y confirmar cobertura ≥ 90 % sin romper pruebas previas (Principio VI).
- [ ] T017 Ejecutar `npm run build` en `frontend/` sin errores.
- [X] T018 Recorrer manualmente `specs/010-progress-and-gamification/quickstart.md` (7 pasos) contra los escenarios de aceptación de la spec.
- [ ] T019 Ejecutar `/speckit-analyze` y `/speckit-converge` sobre US-65 y confirmar que no hay requisitos faltantes ni referencias a US-67/US-68.

## Fase 5: Rediseño "Mi evolución" (T020–T029)

> Reemplaza el volumen semanal por constancia y el selector de ejercicio por una lista de frases (ver `us-65-redisign.md`). Numeración propia de la feature 010. Las tareas T004–T015 de la Fase 3 describen la versión anterior.

- [X] T020 [US1] Reescribir los criterios de aceptación y los FR de US-65 en `spec.md` (PO a validar).
- [X] T021 [US1] Backend: progreso por ejercicio con `message_key`, reutilizando `classify` de `training_evolution_service` (sin duplicar lógica).
- [X] T022 [US1] Backend: constancia por semana y racha; el bucle de adherencia pasa a `adherence_weeks`, compartido con la vista del entrenador (US-30).
- [X] T023 [US1] Backend: récords reales (sin la primera carga, con la marca previa), ejercicios nuevos y próxima sesión (rutina vigente, ajustes de US-26 y devolución de US-64).
- [X] T024 [US1] Actualizar `contracts/student-progress-api.yaml` y `data-model.md`: parámetros `period` y `muscle_group`; se eliminan `exercise_id`, `from`, `to`, el volumen semanal y el 422 por fechas.
- [X] T025 [US1] Frontend: tipos, servicio y utilidades de frases (`utils/studentProgress.mjs`) con su test (sin "estancado", "bajó" ni porcentajes).
- [X] T026 [US1] Frontend: encabezado, selector de período y sección "¿Estoy mejorando?" (lista, chips, gráfico con objetivo punteado y explicación).
- [X] T027 [US1] Frontend: secciones "¿Estoy siendo constante?", "¿Qué logré?" y "¿Qué me toca ahora?".
- [X] T028 [US1] Frontend: eliminar volumen semanal, texto comparativo, filtros de fecha y selectores duplicados; estados especiales.
- [X] T029 [US1] Pruebas de backend (`test_us65_student_progress_api.py`) y frontend (`studentProgress.test.mjs`).

## Dependencias y orden

- T001 → Fase 2 → Fase 3 → Fase 4.
- T002 y T003 en paralelo. T004 → T005, T006, T007 (mismo archivo: secuenciales) → T008 → T009 → T010.
- Frontend: T011 y T012 en paralelo tras T003; T013 tras T011 y T012; T014 tras T013; T015 en paralelo con T013.
- Backend (T004–T010) y frontend (T011–T015) pueden avanzar en paralelo una vez cerrados T002 y T003.

## Estrategia

MVP = toda la story (es una sola). Orden sugerido: contrato/esquemas → servicio con pruebas → pantalla. Un único PR hacia `develop` (Principio VII).
