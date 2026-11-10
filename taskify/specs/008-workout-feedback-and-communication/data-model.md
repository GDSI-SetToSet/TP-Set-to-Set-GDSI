# Data Model: US-63 y US-64

## US-63 — sin cambios de esquema

`SessionSummary` es un valor calculado (no persistido) a partir de `WorkoutSession`, `WorkoutSetLog` y la rutina activa:

| Campo | Tipo | Regla |
|-------|------|-------|
| session_id | str | sesión finalizada del alumno |
| day_name | str | |
| started_at / finished_at | datetime (UTC) | |
| duration_seconds | int | `finished_at − started_at`, ≥ 0 |
| rpe | int \| null | de US-60 |
| total_tonnage_kg | float | R1, redondeo a 2 decimales |
| completed_sets | int | cantidad de logs de la sesión |
| programmed_sets | int \| null | R2 |
| personal_records | list[SessionPersonalRecord] | R3 |
| history.previous_sessions_count | int | R4 |
| history.average_tonnage_kg | float \| null | R4 |
| history.tonnage_delta_percent | float \| null | R4 |

`SessionPersonalRecord`: `exercise_id`, `exercise_name`, `weight_kg`, `reps_completed`, `previous_weight_kg | null`.

## US-64 — `EffortFeedback` (tabla `workout_effort_feedback`)

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| id | String(36) | PK |
| session_id | String(36) | FK `workout_sessions.id` ON DELETE CASCADE, **UNIQUE** |
| relationship_id | String(36) | FK `training_relationships.id` ON DELETE CASCADE, index |
| trainer_id | String(36) | FK `trainer_profiles.id`, index |
| student_id | String(36) | FK `student_profiles.id` ON DELETE CASCADE, index |
| category | String(20) | CHECK IN (`MORE_EFFORT`, `ADEQUATE`, `LESS_INTENSITY`) |
| comment | String(500) | nullable; se guarda `trim()`; vacío ⇒ null |
| created_at / updated_at | DateTime(tz) | UTC |
| seen_at | DateTime(tz) | nullable; se limpia al editar |

**Reglas**: solo para sesiones finalizadas con `rpe` no nulo; solo el entrenador del vínculo `ACTIVE` de la sesión crea/edita; solo el alumno de la sesión lee y marca vista.
**Transiciones**: (no existe) → creada (`seen_at=null`) → vista (`seen_at=now`) → editada (`seen_at=null`) → vista…
