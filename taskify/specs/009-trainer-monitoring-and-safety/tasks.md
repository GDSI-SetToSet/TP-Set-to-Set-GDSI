---
description: "Lista de tareas de US-18, US-19, US-20, US-22, US-24, US-26, US-28, US-30 y US-32 de la feature 009"
---

# Tasks: US-18, US-19, US-20, US-22, US-24, US-26, US-28, US-30 y US-32 — Monitoreo de alumnos activos

**Entrada**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/trainer-student-detail-api.yaml`, `quickstart.md`

**Alcance**: US-18, US-19, US-20, US-22, US-24, US-26, US-28, US-30 y US-32. No implementado US-21 ni US-29.

## Phase 1: Línea base del flujo existente

- [X] T001 [US1] [US18] Registrar el comportamiento actual de `/entrenador/alumnos` y la consulta existente de vínculos activos en `backend/tests/test_trainer_student_api.py` y `frontend/src/pages/TrainerStudentsPage.tsx` sin cambiar el flujo existente de asignación/progreso.
- [X] T002 [P] [US1] [US18] Agregar cobertura de regresión para el alcance exclusivo de activos, el estado vacío, el aislamiento entre entrenadores y la continuidad de la asignación de rutinas en `backend/tests/test_trainer_student_api.py` y los archivos de pruebas existentes relevantes.

## Phase 2: Modelo de lectura y API

- [X] T003 [P] [US1] [US18] Definir los modelos de respuesta Pydantic para listado/detalle, acuerdo del paquete, perfil, limitaciones, rutina vigente y métricas compactas en `backend/src/schemas/trainer_student.py`.
- [X] T004 [US1] [US18] Implementar la orquestación de lectura autorizada en `backend/src/services/trainer_student_service.py`, reutilizando `TrainingRelationship`, `StudentProfile`, `TrainingPlan`, `StudentRoutine`, los servicios existentes de rutinas, las consultas de sesiones/registros y los servicios de reportes/zonas; no duplicar las reglas de autorización.
- [X] T005 [US1] [US18] Exponer `GET /api/v1/trainers/me/students` y `GET /api/v1/trainers/me/students/{student_id}` en `backend/src/api/v1/trainers.py` o en el registro existente del router de entrenadores, devolviendo errores RFC 7807 y excluyendo los vínculos no activos.
- [X] T006 [US1] [US18] Agregar pruebas de API para el éxito del listado/detalle, la ausencia de alumnos activos, el acuerdo del paquete, la composición de perfil/objetivos/limitaciones/rutina/métricas, el acceso entre entrenadores, el acceso a vínculos terminados y la ausencia de divulgación de rutinas en borrador en `backend/tests/test_trainer_student_api.py`.

## Phase 3: Integración con la pantalla existente

- [X] T007 [P] [US1] [US18] Agregar métodos tipados del cliente y tipos de respuesta para el contrato de listado/detalle de US-18 en `frontend/src/services/trainerStudentService.ts` y `frontend/src/types/trainerStudent.ts`.
- [X] T008 [US1] [US18] Integrar la selección y la representación del detalle en `frontend/src/pages/TrainerStudentsPage.tsx` y en un componente enfocado `frontend/src/components/TrainerStudentDetail.tsx`, preservando `RoutineAssignmentPanel` como superficie existente de asignación/progreso.
- [X] T009 [US1] [US18] Preservar y verificar los estados de carga, vacío, error, detalle autorizado, ausencia de rutina y ausencia de actividad en `frontend/src/pages/TrainerStudentsPage.tsx` y `frontend/src/components/TrainerStudentDetail.tsx` sin agregar interfaz de búsqueda, filtros, gráficos, mensajería ni revisión de alertas.

## Phase 4: Verificación

- [X] T010 [P] [US1] [US18] Extender las pruebas enfocadas del backend para cubrir los escenarios de `quickstart.md` y el comportamiento de autorización RFC 7807 en `backend/tests/test_trainer_student_api.py`.
- [X] T011 [P] [US1] [US18] Ejecutar `ruff check backend` y el comando de pruebas enfocado/completo del backend con cobertura, utilizando el formato compatible con CI existente en el repositorio.
- [X] T012 [US1] [US18] Ejecutar `npm run build` en `frontend/` y ejecutar manualmente `taskify/specs/009-trainer-monitoring-and-safety/quickstart.md`.
- [X] T013 [US1] [US18] Ejecutar `/speckit-analyze` sobre los artefactos delimitados a US-18 y verificar que ninguna tarea haga referencia a la implementación de otra historia.

## Phase 5: US-19 — Buscar por alumno

- [X] T014 [US19] Agregar el filtrado local por nombre y apellido, con normalización de mayúsculas y acentos, en `frontend/src/components/RoutineAssignmentPanel.tsx` y `frontend/src/utils/studentSearch.mjs`.
- [X] T015 [US19] Mostrar todos los alumnos activos con el campo vacío y `No se encontraron alumnos` cuando no haya coincidencias, preservando las acciones existentes en `frontend/src/components/RoutineAssignmentPanel.tsx`.
- [X] T016 [P] [US19] Agregar pruebas de búsqueda por nombre, apellido, nombre completo, ausencia de coincidencias, campo vacío, mayúsculas/minúsculas, exclusión de no activos y preservación de datos de acciones en `frontend/src/utils/studentSearch.test.mjs`.
- [X] T017 [US19] Ejecutar las pruebas enfocadas de US-19 y `npm run build` en `frontend/`.

## Phase 6: US-20 — Filtrar alumnos por paquete contratado

- [X] T018 [US20] Exponer `plan_id` y `plan_title` del vínculo activo en `RoutineAssignmentStudentResponse` desde `list_routine_assignments` en `backend/src/services/routine_template_service.py` y `backend/src/schemas/routine_template.py`, sin cambiar la autorización existente.
- [X] T019 [P] [US20] Agregar la prueba de API que verifica el paquete contratado de cada alumno activo y la exclusión de vínculos terminados en `backend/tests/test_trainer_student_api.py`.
- [X] T020 [US20] Implementar `buildPlanFilterOptions`, `canFilterByPlan` y `filterStudentsByPlan` en `frontend/src/utils/studentPlanFilter.mjs` (paquetes vigentes + paquetes contratados por alumnos activos, con cupos ocupados).
- [X] T021 [US20] Integrar el selector de paquete en `frontend/src/components/RoutineAssignmentPanel.tsx`, visible solo con más de un paquete, combinado con la búsqueda de US-19 y con estado vacío para paquetes sin alumnos.
- [X] T022 [P] [US20] Agregar pruebas de un único paquete, varios paquetes, cupos ocupados, paquetes archivados, filtrado y combinación con la búsqueda en `frontend/src/utils/studentPlanFilter.test.mjs`, e incluirlas en `npm test`.
- [X] T023 [US20] Ejecutar las pruebas enfocadas y la suite completa del backend con cobertura, `npm test` y `npm run build` en `frontend/`.

## Phase 7: US-22 — Seguimiento de rutinas del día

- [X] T024 [US22] Definir `DailyRoutineItem`, `DailyRoutineSession`, `DailyRoutineExercise` y `DailyRoutineSet` en `backend/src/schemas/trainer_student.py`.
- [X] T025 [US22] Implementar `list_daily_routines` en `backend/src/services/daily_routine_tracking_service.py`: ventana del día local, prioridad de sesión en curso, agrupación de series por ejercicio y timestamps con zona UTC explícita.
- [X] T026 [US22] Exponer `GET /api/v1/trainers/me/daily-routines?date=&utc_offset_minutes=` en `backend/src/api/v1/trainers.py`.
- [X] T027 [P] [US22] Agregar pruebas de estados, detalle de series, día local, prioridad de sesión en curso, privacidad entre entrenadores y validación de parámetros en `backend/tests/test_us22_daily_routines_api.py`.
- [X] T028 [US22] Crear `frontend/src/pages/TrainerDailyRoutinesPage.tsx` (ruta `/entrenador/rutinas-del-dia`, acceso desde el inicio del entrenador) con selector de día, resumen por estado y detalle expandible por alumno.
- [X] T029 [P] [US22] Agregar utilidades y pruebas de formato/orden en `frontend/src/utils/dailyRoutineFormat.mjs` y `frontend/src/utils/dailyRoutineFormat.test.mjs`.
- [X] T030 [US22] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Phase 8: US-28 — Analizar reportes de molestia y dolor

- [X] T031 [US28] Agregar `exercise_muscle_group` a `BodyMapZoneHistoryItem` y a las consultas de historial por zona (alumno y entrenador) en `backend/src/schemas/body_map_report.py` y `backend/src/services/body_map_report_service.py`, y documentarlo en `taskify/specs/008-workout-feedback-and-communication/contracts/body-map-pain-reports-api.yaml`.
- [X] T032 [P] [US28] Agregar pruebas del historial con ejercicio, día de rutina y grupo muscular en `backend/tests/test_us28_pain_report_analysis_api.py`.
- [X] T033 [US28] Implementar `aggregatePain` y `groupByReport` en `frontend/src/utils/painReportAnalysis.mjs` con pruebas en `frontend/src/utils/painReportAnalysis.test.mjs`.
- [X] T034 [US28] Crear `frontend/src/components/PainReportAnalysis.tsx` (gráfico por zona, grupo muscular, ejercicio o día y listado de reportes) e integrarlo en `frontend/src/components/TrainerStudentDetail.tsx`.
- [X] T035 [US28] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Phase 9: US-32 — Alumnos con riesgo de abandono

- [X] T036 [US32] Implementar `evaluate_risk` y `list_abandonment_risk` en `backend/src/services/abandonment_risk_service.py` (frecuencia según la rutina, umbral de 5 entrenamientos o 14 días, alerta `ABANDONMENT_RISK` deduplicada por período).
- [X] T037 [US32] Exponer `GET /api/v1/trainers/me/abandonment-risk` en `backend/src/api/v1/trainers.py` y evaluar el riesgo al listar `GET /api/v1/trainers/me/notifications` sin bloquear la lectura si falla.
- [X] T038 [P] [US32] Agregar pruebas de umbrales, deduplicación, orden, alumnos sin rutina, privacidad y tolerancia a fallos en `backend/tests/test_us32_abandonment_risk_api.py`.
- [X] T039 [US32] Priorizar a los alumnos en riesgo y mostrar la etiqueta "Riesgo de abandono" en `frontend/src/components/RoutineAssignmentPanel.tsx`, con `frontend/src/utils/abandonmentRisk.mjs` y sus pruebas; enlazar la notificación al alumno en `frontend/src/constants/routes.ts`.
- [X] T040 [US32] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Phase 10: US-24 — Métricas esperadas vs obtenidas por sesión

- [X] T041 [US24] Definir `SessionComparison`, `ExerciseComparison`, `PlannedMetrics` y `PerformedMetrics` en `backend/src/schemas/trainer_student.py`.
- [X] T042 [US24] Implementar `compare_session` en `backend/src/services/session_comparison_service.py`: plan vigente del día (copia del alumno, plantilla o rutina asignada), sesión previa finalizada del mismo día de rutina, métricas por ejercicio y por sesión y mapeo de reemplazos (US-54).
- [X] T043 [US24] Exponer `GET /api/v1/trainers/me/sessions/{session_id}/comparison` en `backend/src/api/v1/trainers.py` (404 si la sesión no es de un alumno activo propio, 409 si sigue en curso) y documentarlo en `contracts/trainer-student-detail-api.yaml`.
- [X] T044 [P] [US24] Agregar pruebas de plan vs real, sesión previa del mismo día, sin sesión previa, reemplazos, sesión en curso y privacidad en `backend/tests/test_us24_session_comparison_api.py`.
- [X] T045 [P] [US24] Agregar utilidades de diferencias y formato en `frontend/src/utils/sessionComparison.mjs` con pruebas en `frontend/src/utils/sessionComparison.test.mjs`.
- [X] T046 [US24] Crear `frontend/src/components/SessionComparison.tsx` e integrarlo con la acción "Comparar métricas" en el detalle de sesiones finalizadas de `frontend/src/pages/TrainerDailyRoutinesPage.tsx`.
- [X] T047 [US24] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Phase 11: US-26 — Ajustar la próxima sesión a partir de los reportes

> Numeración a partir de T048: T041–T047 corresponden a US-24 (rama `feature/us24-planned-vs-actual-metrics`).

- [X] T048 [US26] Crear el modelo `SessionAdjustment` (`PENDING`/`APPLIED`/`SUPERSEDED`) en `backend/src/models/session_adjustment.py` y registrarlo en `backend/src/models/__init__.py` (tabla nueva, la crea `create_all`).
- [X] T049 [US26] Definir `AdjustmentInput`, `SessionAdjustmentContext`, `AdjustmentView` y `StudentAdjustmentNotice` en `backend/src/schemas/session_adjustment.py`.
- [X] T050 [US26] Implementar `get_adjustment_context`, `save_adjustment`, `apply_pending_adjustments` y `list_student_adjustments` en `backend/src/services/session_adjustment_service.py`, con la validación de US-14 (bloqueo de contraindicados y "Sin materiales"), el registro en `RoutineChangeLog`, el ajuste pendiente si hay una sesión en curso y la copia de la rutina creada recién al aplicar.
- [X] T051 [US26] Aplicar los ajustes pendientes al finalizar la sesión que esperaban y al iniciar una nueva en `backend/src/services/routine_template_service.py`.
- [X] T052 [US26] Exponer `GET`/`PUT /api/v1/trainers/me/sessions/{session_id}/adjustment` y `GET /api/v1/students/me/routine-adjustments` en `backend/src/api/v1/session_adjustments.py` y documentarlos en `contracts/trainer-student-detail-api.yaml`.
- [X] T053 [P] [US26] Agregar pruebas de contexto (cargas, RPE, molestias y reemplazos), ajuste aplicado y marca hasta entrenar el día, ajuste pendiente con sesión en curso, sesión abandonada, contraindicados, reemplazo de ejercicio, reglas de conflicto y privacidad en `backend/tests/test_us26_session_adjustment_api.py`.
- [X] T054 [P] [US26] Agregar utilidades y pruebas en `frontend/src/utils/sessionAdjustment.mjs` y `frontend/src/utils/sessionAdjustment.test.mjs`.
- [X] T055 [US26] Crear `frontend/src/components/SessionAdjustmentPanel.tsx` con la acción "Ajustar próxima sesión" en `frontend/src/pages/TrainerDailyRoutinesPage.tsx`, y mostrar "Ajustado por tu entrenador" con la nota en `frontend/src/pages/StudentRoutinesPage.tsx` (recargando la rutina al iniciar la sesión).
- [X] T056 [US26] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Phase 12: US-30 — Evolución de entrenamientos del alumno

> Numeración a partir de T057. Sin tablas ni migraciones: modelo de lectura sobre `WorkoutSession` finalizadas y `WorkoutSetLog` (ver `data-model.md`).
> **Objetivo**: en el detalle del alumno, un gráfico de carga, repeticiones totales y series, agrupable por entrenamiento, semana o grupo muscular.
> **Prueba independiente**: con un alumno de ≥3 sesiones finalizadas en semanas distintas, el escenario 7 de `quickstart.md` se cumple de punta a punta.

- [X] T057 [US30] Definir `TrainingEvolution`, `EvolutionSeries` y `EvolutionPoint` en `backend/src/schemas/trainer_student.py` (`group_by`: `session`|`week`|`muscle_group`; `period`: `4w`|`12w`|`all`; `weight_kind`: `max_weight`|`volume`; punto: `key`, `date`, `weight_kg`, `total_reps`, `sets`; `label` es null salvo en `muscle_group`).
- [X] T058 [US30] Hacer públicas `number` y `performed_metrics` (hoy `_number` y `_performed`) en `backend/src/services/session_comparison_service.py` y actualizar sus usos internos, para reutilizar la definición de volumen (repeticiones × carga) sin duplicarla.
- [X] T059 [US30] Implementar `get_training_evolution(db, user, student_id, group_by, period, exercise_id)` en `backend/src/services/training_evolution_service.py`: solo sesiones con `finished_at` de un vínculo `ACTIVE` del entrenador (404 si no, como en `session_comparison_service`); período por `finished_at` (4 o 12 semanas, `all` sin filtro); `session` = un punto por sesión, `week` = semana calendario lunes a domingo en UTC con clave el lunes ISO (carga máxima, repeticiones y series sumadas), `muscle_group` = una serie por `Exercise.target_muscle_group` con un punto por semana; con `exercise_id` la carga es la carga máxima de ese ejercicio y sin él el volumen; puntos en orden cronológico; sin sesiones `series` es `[]`. Marcar con `ponytail:` el límite de semana en UTC.
- [X] T060 [US30] Exponer `GET /api/v1/trainers/me/students/{student_id}/evolution` (la respuesta incluye `exercises` para el selector) en `backend/src/api/v1/trainers.py` con `group_by` (default `week`), `period` (default `12w`) y `exercise_id` opcional, validados por enum (422 RFC 7807), registrando la ruta antes de `/me/students/{student_id}` si hace falta para evitar conflictos; el contrato ya está en `contracts/trainer-student-detail-api.yaml`.
- [X] T061 [P] [US30] Agregar pruebas en `backend/tests/test_us30_training_evolution_api.py`: agrupación por sesión, por semana y por grupo muscular; período 4w/12w/all; con y sin `exercise_id` (carga máxima vs volumen); exclusión de sesiones en curso y abandonadas; sin sesiones; una sola sesión; `group_by`/`period` inválidos (422); alumno de otro entrenador o vínculo inactivo (404).
- [X] T062 [P] [US30] Agregar tipos y `getTrainingEvolution(studentId, { groupBy, period, exerciseId })` en `frontend/src/types/trainerStudent.ts` y `frontend/src/services/trainerStudentService.ts`.
- [X] T063 [P] [US30] Crear `frontend/src/utils/trainingEvolution.mjs` (+ `.d.mts`) con escalado de puntos del gráfico, formato de etiquetas de semana/fecha y la regla de estado (`empty` sin puntos, `single` con un punto, `ok` con 2 o más), con pruebas en `frontend/src/utils/trainingEvolution.test.mjs`.
- [X] T064 [US30] Crear `frontend/src/components/TrainingEvolution.tsx`: gráfico SVG de las tres métricas, selector de agrupación, selector de período (4 semanas, 12 semanas por defecto, todo el historial), selector opcional de ejercicio (la carga pasa de volumen a carga máxima), estados de carga/error, mensaje "Sin entrenamientos en este período" y nota de mínimo 2 sesiones con un solo punto; accesible (etiquetas, `aria-label`, lista alternativa de valores). Estilos en `frontend/src/styles/training-evolution.css`.
- [X] T065 [US30] Montar `TrainingEvolution` en `frontend/src/components/TrainerStudentDetail.tsx`, junto a `PainReportAnalysis`.
- [X] T066 [US30] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`, y validar el escenario 7 de `quickstart.md`.

## Phase 13: US-30 — Rediseño "Progreso del alumno" por preguntas

> Numeración a partir de T067. Reemplaza el enfoque de volumen (T057–T066) según la sesión 2026-11-16 de `spec.md`. T067–T073 de la versión anterior (volumen, indicadores de volumen y tabla de totales) quedan descartadas.

- [X] T067 [US30] Reescribir el criterio 1 de US-30 y registrar la sesión de clarificaciones 2026-11-16 en `spec.md`; actualizar `research.md`, `data-model.md`, `quickstart.md` y `contracts/trainer-student-detail-api.yaml`.
- [X] T068 [US30] Backend: definir los esquemas del nuevo `TrainingEvolution` (resumen, ejercicios, adherencia, RPE, series por grupo y `to_review`) en `backend/src/schemas/trainer_student.py` y devolver `number`/`performed` de `session_comparison_service.py` a privados.
- [X] T069 [US30] Backend: progresión por ejercicio y estados (`classify`: pocos datos → bajó → progresando → estancado → sin cambios; mejora con más peso o más repeticiones; peso corporal por repeticiones; "Sin métrica") en `backend/src/services/training_evolution_service.py`, excluyendo la semana en curso.
- [X] T070 [US30] Backend: adherencia (sesiones programadas con el criterio de US-32) y cumplimiento de series, con los ejercicios más salteados y el motivo "pedido de reemplazo".
- [X] T071 [US30] Backend: tendencia de RPE y mensaje de esfuerzo (`effort_message`, precedencia explícita) y semáforos con umbrales como constantes del módulo.
- [X] T072 [US30] Backend: series semanales por grupo muscular, lista `to_review` y filtro `muscle_group`; ruta `GET /api/v1/trainers/me/students/{student_id}/evolution?period=&group_by=&muscle_group=` en `backend/src/api/v1/trainers.py`.
- [X] T073 [P] [US30] Reescribir `backend/tests/test_us30_training_evolution_api.py`: estados, mejora con más repeticiones, peso corporal, semana parcial excluida, adherencia con semanas sin sesiones, las combinaciones del mensaje de esfuerzo, `to_review`, filtro por grupo muscular, privacidad y una prueba con el reloj real.
- [X] T074 [P] [US30] Frontend: actualizar tipos y servicio (`frontend/src/types/trainerStudent.ts`, `frontend/src/services/trainerStudentService.ts`).
- [X] T075 [P] [US30] Frontend: reescribir `frontend/src/utils/trainingEvolution.mjs` (+ `.d.mts`) con orden por estado, formato de rangos, escalas, etiquetas de semáforos, textos de mensajes y huecos de RPE, con pruebas en `trainingEvolution.test.mjs`.
- [X] T076 [US30] Frontend: encabezado con los 4 indicadores y los controles (Período, Agrupar, Grupo muscular) en `frontend/src/components/TrainingEvolution.tsx`.
- [X] T077 [US30] Frontend: sección "¿Está progresando?" (tabla por ejercicio y gráfico del ejercicio seleccionado).
- [X] T078 [US30] Frontend: sección "¿Está entrenando lo que le programé?" (barras de adherencia y ejercicios más salteados).
- [X] T079 [US30] Frontend: sección "¿Cómo le está costando?" (mensaje y gráfico de RPE con banda 6–8 y huecos).
- [X] T080 [US30] Frontend: sección "¿Qué tengo que ajustar?" (lista a revisar y series semanales por grupo muscular), sin botón de ajuste.
- [X] T081 [US30] Frontend: eliminar los gráficos, indicadores y tabla anteriores y el selector de ejercicio; estados especiales y accesibilidad; estilos en `frontend/src/styles/training-evolution.css`.
- [X] T082 [US30] Actualizar el seed demo para mostrar estados distintos (ejercicio estancado y una semana sin entrenar) en `backend/scripts/seed_demo.py`.
- [X] T083 [US30] Ejecutar `pytest` (US-30 y seed), `ruff`, `npm test` y `npm run build`, y repetir el cálculo contra la base real para Tomás y Valentina.

## Dependencias

T001 → T002/T003 (en paralelo) → T004 → T005 → T006 → T007/T008/T009 (T007 en paralelo con T006; T008 después de T007 y T005) → T010/T011/T012 → T013 → T014/T015/T016 (T016 en paralelo con T014/T015) → T017 → T018 → T019/T020 → T021/T022 → T023. US-22 (T024–T030), US-28 (T031–T035) y US-32 (T036–T040) son independientes entre sí y de US-20. US-24 (T041–T047) extiende la pantalla de US-22: T041 → T042 → T043 → T044; T045 en paralelo con el backend; T046 después de T043 y T045. US-26 (T048–T056) extiende la pantalla de US-22 y reutiliza la edición de US-14: T048 → T049 → T050 → T051/T052 → T053; T054 en paralelo con el backend; T055 después de T052 y T054. US-30 (T057–T066 con el enfoque anterior y T067–T083 con el rediseño por preguntas: T067 → T068 → T069 → T070/T071/T072 → T073; T074 y T075 en paralelo con el backend; T076 → T077–T080 → T081; T082 y T083 al final) es independiente de las demás y se monta en el detalle de US-18: T057 → T058 → T059 → T060 → T061; T062 y T063 en paralelo con el backend; T064 después de T062 y T063; T065 después de T064; T066 al final.

## Oportunidades de paralelización

- T002 y T003 pueden ejecutarse en paralelo.
- T007 puede ejecutarse en paralelo con la finalización de las pruebas del backend una vez estabilizado el contrato.
- T010, T011 y T012 pueden ejecutarse en paralelo después de completar la integración.
- T016 puede ejecutarse en paralelo con la implementación del filtro visual.
- US-30: T061, T062 y T063 pueden ejecutarse en paralelo una vez definido el esquema (T057).

## MVP

El incremento de US-18 comprende T003–T009 y el incremento de US-19 comprende T014–T017: búsqueda local sobre alumnos activos ya cargados, sin cambios de backend. El incremento de US-20 comprende T018–T023: filtro local por paquete con cupos ocupados, apoyado en `plan_id`/`plan_title` del listado de asignaciones. US-22 comprende T024–T030 (pantalla "Rutinas del día"), US-28 comprende T031–T035 (análisis de molestias en el detalle del alumno), US-32 comprende T036–T040 (riesgo de abandono con alerta y priorización), US-24 comprende T041–T047 (comparación de métricas planificadas, realizadas y previas de una sesión finalizada) y US-26 comprende T048–T056 (ajuste de la próxima sesión desde la sesión finalizada, con marca para el alumno). US-30 comprende T057–T066 (gráfico de evolución en el detalle del alumno). US-21 y US-29 permanecen fuera de alcance.
