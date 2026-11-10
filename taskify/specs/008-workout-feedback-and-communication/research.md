# Research: US-63 y US-64

## R1. Cálculo del tonelaje (US-63)
- **Decision**: tonelaje = Σ `weight_kg × reps` de las `WorkoutSetLog` de la sesión. `reps_completed` es texto: se toma el número inicial (`"10"` → 10, `"8-10"` → 8, `"12,5"` → 12.5); si no se puede interpretar o `weight_kg` es nulo, la serie aporta 0 kg pero cuenta como completada.
- **Rationale**: coincide con el edge case de la spec ("peso × repeticiones de todas las series completadas") y es tolerante con datos históricos.
- **Alternatives**: rechazar series no numéricas (rompe sesiones existentes).

## R2. Series programadas (US-63)
- **Decision**: Σ `sets` de los ejercicios del día `day_name` de la rutina activa del alumno, solo si su id coincide con `session.routine_id`. Si la rutina cambió o el día ya no existe, `programmed_sets = null` y el front muestra solo las completadas.
- **Rationale**: las sesiones no guardan un snapshot de la rutina; inventar un valor sería engañoso.

## R3. PRs de la sesión (US-63)
- **Decision**: por cada ejercicio de la sesión, comparar el peso máximo registrado en la sesión contra el máximo de los logs anteriores del alumno para ese ejercicio (`recorded_at` menor al primer log del ejercicio en la sesión y fuera de la sesión). Es PR si no había logs previos con peso > 0 y el de la sesión es > 0, o si lo supera. Se informa el peso previo (o `null` si es el primero).
- **Rationale**: misma regla que US-59 pero recalculable a posteriori; no depende de que `PersonalRecord` siga apuntando al log de esta sesión (puede haberse superado después).
- **Alternatives**: usar `PersonalRecord.workout_set_log_id` (pierde PRs superados en sesiones posteriores).

## R4. Comparación histórica (US-63, Clarification 2026-11-10)
- **Decision**: promedio de tonelaje de las sesiones finalizadas anteriores (`started_at` menor) del mismo alumno, misma `routine_id` y mismo `day_name`, que tengan al menos una serie registrada. `delta_percent = (actual − promedio) / promedio × 100`, redondeado a 1 decimal; `null` si no hay sesiones previas o el promedio es 0.

## R5. Momento de mostrar el resumen (US-63)
- **Decision**: al finalizar (manual o automático) el front navega a `/student/routines?session=<id>&completed=1`; el diálogo de celebración existente pasa a mostrar el resumen obtenido de `GET .../workout-sessions/{id}/summary`. Si la request falla, se muestra la felicitación sin métricas y un mensaje de error comprensible.

## R6. Devolución (US-64, Clarification 2026-11-10)
- **Decision**: tabla `workout_effort_feedback` con `session_id` único (upsert desde un `PUT`). Categorías `MORE_EFFORT`, `ADEQUATE`, `LESS_INTENSITY`. Al editar se actualiza `updated_at`, se limpia `seen_at` y se envía nueva notificación `EFFORT_FEEDBACK` al alumno.
- **Rationale**: "una por sesión, editable" se modela naturalmente como upsert idempotente.
- **Migración**: tabla nueva ⇒ `create_all` la crea; no hace falta alterar tablas existentes.

## R7. Visualización para el alumno (US-64)
- **Decision**: `GET .../assigned/effort-feedback` devuelve el historial (más reciente primero) con `seen_at`. Al abrir una sesión (`sessionMode`) se muestran las no vistas en un aviso y se marcan con `POST .../effort-feedback/{id}/seen`. En la vista general hay una sección "Devoluciones de tu entrenador" con estado vacío explícito.
