# Modelo de datos: US-65

Sin tablas ni migraciones nuevas. Entradas existentes: `WorkoutSetLog` (peso, repeticiones, `recorded_at`, `exercise_id`, `student_id`), `Exercise` (`name`, `target_muscle_group`), `PersonalRecord` (solo máximo vigente; no se usa para el historial).

## Reglas de validación
- Mejor serie del día por ejercicio: más peso y, a igual peso, más repeticiones; sin carga, más repeticiones. Los días sin repeticiones numéricas ("45 seg", "al fallo") se descartan. Se reutiliza `training_evolution_service`.
- Récord: la mejor serie de un día supera (tupla peso, repeticiones) a la mejor anterior del ejercicio; el primer día no cuenta. Se calcula sobre todo el historial y después se filtra por período.
- `period` ∈ {`4w`, `12w` (defecto), `all`}; `muscle_group` opcional. El resumen no depende del grupo.

## Respuesta `StudentProgress` (esquemas Pydantic de solo lectura)

| Entidad | Campos |
|---|---|
| `StudentProgress` | `period{key,start,end}`, `muscle_group`, `muscle_groups[]` (chips, sin filtrar), `has_sessions`, `summary`, `exercises[]`, `consistency[]`, `records[]`, `new_exercises[]`, `next_session` |
| `summary` | `improving_exercises_last_4w`, `streak{current_weeks,best_weeks}`, `records_in_period` |
| `ExerciseEvolution` | `exercise_id`, `name`, `muscle_group`, `metric` (`max_weight`/`max_reps`), `start`, `current`, `best` (`{weight,reps}`), `message_key`, `weeks_without_change`, `last_improvement_is_pr`, `points[]` |
| `ExercisePoint` | `date`, `weight`, `reps`, `target_weight`, `is_pr` |
| `consistency[]` | `period_start`, `period_end`, `scheduled`, `completed`, `is_partial` |
| `RecordEntry` | `date`, `exercise_id`, `name`, `weight`, `reps`, `previous{weight,reps}` |
| `NextSession` | `day_name`, `trainer_feedback`, `exercises[]` (`last`, `target_weight`, `reps`, `sets`, `adjusted_by_trainer`, `trainer_note`) |

Se eliminan el volumen semanal, la comparación con la semana anterior y los parámetros `exercise_id`, `from` y `to`.

## Transiciones de estado
Ninguna: solo lectura.
