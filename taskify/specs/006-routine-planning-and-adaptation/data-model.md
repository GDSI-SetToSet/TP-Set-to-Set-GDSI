# Data Model: US-14

## StudentRoutine
- `id`, `relationship_id` (FK `training_relationships`, único por alumno–entrenador activo), `source_template_id` (nullable), `source_kind` (`GENERIC`; el valor `AI` se agrega con US-13)
- `name`, `duration_weeks`, `intensity`, `has_no_materials_alternative`, `desired_weekly_volume` (nullable, entre 1 y 7); `intensity` con los mismos valores válidos que `RoutineTemplate.intensity`
- Contenido vigente (`days`, JSON): días → bloques → ejercicios (misma forma que la entrada de `RoutineTemplate`: `exercise_id`, `sets` > 0, `reps`, `rest_seconds` ≥ 0, `target_weight_kg` ≥ 0 opcional)
- `draft_*`: contenido en borrador con la misma forma; `draft_version` (entero, +1 por guardado), `draft_updated_at`
- `status`: `ACTIVE` | `DRAFT_PENDING` | `UNASSIGNED` (el entrenador quitó la rutina; la copia y su log se conservan) (hay borrador sin confirmar)
- `created_at`, `updated_at` (UTC)

Reglas: solo el entrenador del vínculo ACTIVE edita; el alumno solo lee el contenido vigente. Si el vínculo termina, el acceso se revoca (Principio III).

## Exercise (cambio)
- `contraindicated_zones`: lista de textos normalizados (opcional, vacía por defecto).

## RoutineChangeLog (inmutable)
- `id`, `student_routine_id`, `trainer_id`, `confirmed_at` (UTC), `changes` (resumen por ejercicio/parámetro: antes → después). Sin delete.

## Transiciones
`ACTIVE` → (guardar borrador) → `DRAFT_PENDING` → (confirmar) → `ACTIVE` con contenido nuevo + log. Descartar borrador → `ACTIVE`.

## Validaciones
- Guardar borrador: valores numéricos válidos, ejercicio propio del entrenador y no dado de baja, **ningún ejercicio contraindicado** por zonas protegidas del alumno (bloqueo absoluto), `draft_version` coincidente.
- Confirmar: todo lo anterior + alternativa "Sin materiales" en cada ejercicio agregado o reemplazado respecto de la versión vigente si la rutina es "Sin materiales"; rutina con al menos un ejercicio.
