# Modelo de datos: US-65

Sin tablas ni migraciones nuevas. Entradas existentes: `WorkoutSetLog` (peso, repeticiones, `recorded_at`, `exercise_id`, `student_id`), `Exercise` (`name`, `target_muscle_group`), `PersonalRecord` (solo máximo vigente; no se usa para el historial).

## Reglas de validación
- Serie válida para cálculo: `weight_kg > 0` y `reps_completed` numérico (> 0).
- PR: peso estrictamente mayor al máximo previo del mismo ejercicio; la primera serie válida es PR inicial.
- `from <= to`; ambas fechas ISO 8601 (UTC). Sin parámetros: últimas 12 semanas.

## Respuesta `StudentProgress` (esquemas Pydantic de solo lectura)

| Entidad | Campos |
|---|---|
| `StudentProgress` | `range{from,to,is_default}`, `muscle_groups[]` (opciones del filtro), `has_data`, `exercises[]`, `weekly_volume[]`, `week_comparison`, `personal_records[]` |
| `ExerciseLoad` | `exercise_id`, `name`, `muscle_group`, `has_trend` (≥ 2 puntos), `points[]` |
| `LoadPoint` | `date`, `weight_kg`, `reps`, `is_pr` |
| `WeeklyVolume` | `week_start`, `week_end`, `volume_kg`, `is_partial` (una por semana, 0 si sin series) |
| `WeekComparison` | `current_volume_kg`, `previous_volume_kg`, `delta_vs_previous_pct` (null si previa = 0), `previous_avg_kg` (semanas completas previas del rango) |
| `PersonalRecordEntry` | `exercise_id`, `exercise_name`, `weight_kg`, `reps`, `achieved_at`, `previous_weight_kg` (null si inicial), `is_initial` |

`ProgressChartData` de la spec se materializa como `exercises[]` + `weekly_volume[]` + `personal_records[]` (cálculo en lectura, sin persistencia).

## Transiciones de estado
Ninguna: solo lectura.
