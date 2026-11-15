# Modelo de datos: US-18 — Resumen del alumno para el entrenador

US-18 no agrega tablas de base de datos. El modelo de lectura de la API compone entidades existentes.

## Entidades existentes

### TrainingRelationship

- Identifica el vínculo entre el entrenador y el alumno.
- Alcance requerido: `trainer_id` coincide con el perfil del entrenador autenticado y `status` es `ACTIVE`.
- Proporciona `plan_id`, `agreed_monthly_price`, `agreed_currency`, `start_date` e `initial_routine_id`.

### StudentProfile

- Proporciona nombre, apellido, fecha de nacimiento, imagen de perfil, biografía, objetivos físicos y estado del perfil.
- `protected_zones` se cargan únicamente después de verificar la autorización del vínculo activo.

### TrainingPlan

- Resuelve el paquete contratado originalmente mediante el vínculo.
- El precio y la moneda mostrados provienen del acuerdo del vínculo, no del precio actual del catálogo.

### Asignación de rutina

- Los datos existentes de `RoutineTemplate`, `AssignedRoutine` y `StudentRoutine` proporcionan la rutina asignada vigente.
- La respuesta de detalle no debe exponer una rutina en borrador como rutina actual del alumno.

### Datos de actividad

- Los registros existentes de `WorkoutSession` proporcionan las sesiones completadas y la marca de tiempo/RPE de la última sesión.
- Los registros existentes de `WorkoutSetLog` proporcionan la cantidad de series registradas y los datos para calcular el tonelaje de la última sesión.
- Los reportes existentes de esfuerzo y del mapa corporal siguen disponibles mediante sus servicios y endpoints actuales; US-18 no cambia su ciclo de vida.

## Modelos de lectura de la API

### TrainerStudentListItem

- `relationship_id`
- `student_id`
- `full_name`
- `profile_status`
- `package_title`
- `routine_name` anulable
- `has_activity`
- `unreviewed_alert_count` anulable/reservado para la integración de US-29; debe permanecer en `0` u omitirse hasta que exista esa historia

### TrainerStudentDetail

- `relationship`: ID del vínculo, estado, fecha de inicio, precio y moneda acordados del paquete
- `profile`: campos existentes del perfil del alumno apropiados para un entrenador autorizado
- `goals`: objetivos físicos y motivación
- `limitations`: nombres normalizados de zonas protegidas e indicadores de seguridad existentes
- `routine`: resumen de la rutina vigente y referencia al detalle existente de la rutina
- `metrics`: `finished_sessions`, `last_session_at`, `logged_sets`, `last_rpe`, `last_tonnage_kg`
- `available_existing_views`: referencias/identificadores necesarios para los componentes actuales de rutina, reportes y progreso

## Invariantes

1. Un elemento del listado o detalle solo puede devolverse para un vínculo activo perteneciente al entrenador autenticado.
2. Los vínculos terminados y vencidos quedan excluidos.
3. El precio del paquete mostrado para un alumno activo es el precio acordado en el vínculo.
4. El perfil, la rutina, la actividad, los objetivos o las zonas protegidas faltantes se representan como datos vacíos/nulos, no mediante valores predeterminados inventados.
5. US-18 no introduce ninguna operación de escritura.

# Modelo de datos: US-30 — Progreso del alumno

US-30 no agrega tablas ni migraciones; es un modelo de lectura sobre `WorkoutSession` (solo con `finished_at`), `WorkoutSetLog`, `Exercise.target_muscle_group`, `PersonalRecord` (US-59), `EffortFeedback` (US-64), `ExerciseReplacementLog` (US-54) y la rutina vigente del alumno, dentro de un vínculo ACTIVO del entrenador.

## Respuesta `TrainingEvolution`

- `period`: `{ key: 4w | 12w | all, start, end }` (fechas ISO; `start` es el lunes inicial); `group_by`: `session` | `week`; `muscle_group`: filtro opcional; `muscle_groups`: grupos de todo el historial; `has_sessions`
- `summary`:
  - `progress`: `{ improving, with_data, status }`
  - `adherence`: `{ completed_sessions, scheduled_sessions, pct, sets_completion_pct, status }`
  - `effort`: `{ avg_rpe_last_4, trend: rising | stable | falling, message_key, status }`
  - `to_review`: `{ count, status }`
- `exercises[]`: `{ exercise_id, name, muscle_group, metric: max_weight | max_reps | none, start, current, change_pct, last_improvement: { date, is_pr }, status, points[] }`; `status`: `progressing` | `stalled` | `declined` | `unchanged` | `few_data` | `no_metric`; punto: `{ key, period_start, period_end, weight, reps, target_weight, rpe, is_pr, is_partial }`
- `adherence[]`: `{ period_start, period_end, scheduled, completed, is_partial }` por semana
- `most_skipped[]`: `{ exercise_id, name, completion_pct, skip_count, main_reason: replacement_requested | null }`
- `rpe[]`: `{ key, period_start, period_end, rpe, has_report, trainer_feedback, is_partial }`
- `sets_by_muscle_group[]`: `{ muscle_group, avg_completed_per_week, avg_scheduled_per_week }`
- `to_review[]`: `{ type, exercise_id, label }`

## Reglas de cálculo

1. Solo sesiones finalizadas del vínculo ACTIVO; ajeno o inactivo devuelve 404. El período se alinea a semanas calendario (lunes a domingo, UTC); 4 o 12 semanas incluyen la semana en curso.
2. La semana en curso (`is_partial`) se grafica pero no entra en estados, porcentajes ni tendencias.
3. Métrica por sesión y ejercicio: la mejor serie con repeticiones numéricas (más peso y, a igual peso, más repeticiones); sin carga, más repeticiones; sin repeticiones numéricas: `no_metric`.
4. Estado (semanas completas, en este orden): menos de 2 sesiones → `few_data`; valor actual ≤ 90 % del máximo de las 3 semanas anteriores → `declined`; mejora en las últimas 3 semanas completas → `progressing`; sin mejora y con al menos 3 sesiones en esas semanas → `stalled`; si no, `unchanged`. Mejora: supera el mejor valor anterior.
5. Con `few_data` el inicio y el actual se calculan con todas las sesiones del período; el cambio porcentual es nulo.
6. `is_pr` solo marca la sesión del récord vigente: `PersonalRecord` guarda un único récord por alumno y ejercicio, no un historial.
7. Sesiones programadas por semana = días de la rutina vigente (criterio de US-32), desde la asignación; una semana completa suma `min(completadas, programadas)`. Cumplimiento de series = series registradas (sin superar lo programado por ejercicio, contando el reemplazo elegido) sobre las programadas de la versión vigente de la rutina.
8. Ejercicios más salteados: los 3 con cumplimiento menor al 70 %.
9. Esfuerzo: promedio de RPE de las últimas 4 sesiones con reporte (semanas completas), tendencia contra las 4 anteriores (±0,5 es estable). Mensaje por precedencia: esfuerzo excesivo (algún RPE ≥ 9) → fatiga (carga no sube y RPE sube) → exigir más (promedio < 6) → progreso con esfuerzo en aumento → progreso con margen. La carga "sube" si `progress.status` es verde.
10. Semáforos: progreso verde ≥ 50 %, amarillo 25–49 %; adherencia verde ≥ 80 %, amarillo 60–79 %; esfuerzo verde con promedio 6–8, rojo con promedio ≥ 9 o fatiga; para revisar verde 0, amarillo 1–2, rojo ≥ 3. Los umbrales son constantes del servicio.
11. `to_review` en orden: ejercicios que bajaron, estancados, fatiga o esfuerzo excesivo, ejercicios salteados y semanas sin entrenar (últimas 2 completas). `to_review.count` es la cantidad de puntos de la lista.
12. Series semanales por grupo: promedio de series registradas por semana completa; programadas = series de todos los días de la rutina vigente (cada día una vez por semana).
13. Operación de solo lectura.
