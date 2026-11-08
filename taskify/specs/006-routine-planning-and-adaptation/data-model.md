# Data Model: Generación de Rutina Particular con IA (US-13)

**Feature**: `006-routine-planning-and-adaptation` (US-13)
**Date**: 2026-10-31

## Entidades y Atributos

### 1. `AssignedRoutine`
Rutina particular adaptada para un alumno individual, originada a partir de una plantilla genérica mediante asistencia de IA.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | No | - | Clave foránea a `TrainerProfile.id` (entrenador autor). |
| `student_id` | UUID / String(36) | No | - | Clave foránea a `StudentProfile.id` (alumno destinatario). |
| `template_id` | UUID / String(36) | Sí | `None` | Clave foránea a `RoutineTemplate.id` (plantilla base utilizada). |
| `name` | String(150) | No | - | Nombre de la rutina particular adaptada. |
| `duration_weeks` | Integer | No | - | Duración en semanas (1 a 52). |
| `intensity` | Enum(`BAJA`, `MEDIA`, `ALTA`, `EXIGENTE`) | No | - | Nivel de intensidad adaptado. |
| `status` | Enum(`PENDING_REVIEW`, `APPROVED`) | No | `PENDING_REVIEW` | Estado de revisión y aprobación humana. |
| `adaptation_summary` | Text | Sí | `None` | Explicación detallada de las adaptaciones efectuadas por IA. |
| `approved_at` | DateTime (UTC) | Sí | `None` | Momento exacto de la aprobación manual del entrenador. |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de generación de la propuesta. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de última actualización. |

### 2. `AssignedRoutineDay`
Día organizado dentro de la rutina particular.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `routine_id` | UUID / String(36) | No | - | Clave foránea a `AssignedRoutine.id` con `CASCADE`. |
| `order_index` | Integer | No | - | Posición secuencial del día dentro de la rutina. |
| `name` | String(100) | No | - | Nombre del día (ej. "Día 1 - Tren superior adaptado"). |

### 3. `AssignedRoutineBlock`
Bloque de trabajo dentro de un día de la rutina particular.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `day_id` | UUID / String(36) | No | - | Clave foránea a `AssignedRoutineDay.id` con `CASCADE`. |
| `order_index` | Integer | No | - | Posición secuencial del bloque dentro del día. |
| `name` | String(100) | No | - | Nombre del bloque (ej. "Bloque Principal"). |

### 4. `AssignedRoutineExercise`
Ejercicio adaptado dentro de un bloque de la rutina particular.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `block_id` | UUID / String(36) | No | - | Clave foránea a `AssignedRoutineBlock.id` con `CASCADE`. |
| `exercise_id` | UUID / String(36) | No | - | Clave foránea a `Exercise.id` (biblioteca del entrenador). |
| `order_index` | Integer | No | - | Posición de ejecución dentro del bloque. |
| `sets` | Integer | No | - | Cantidad de series adaptadas (1 a 20). |
| `reps` | String(50) | No | - | Repeticiones adaptadas (ej. "8-10", "15"). |
| `rest_seconds` | Integer | No | - | Descanso adaptado en segundos (0 a 600). |
| `adaptation_notes` | String(255) | Sí | `None` | Nota específica de la IA para este ejercicio (ej. "Sustituido por seguridad lumbar"). |

## Reglas de Integridad y Ciclo de Vida

1. **Estado `PENDING_REVIEW`**:
   - Creado por el generador de IA.
   - Visible para el entrenador para revisión y decisión.
   - NO visible para el alumno como rutina activa.
2. **Estado `APPROVED`**:
   - Transición iniciada exclusivamente por el entrenador mediante acción explícita.
   - Establece `approved_at = utc_now()`.
   - Asocia `TrainingRelationship.initial_routine_id = assigned_routine.id` si la relación activa no poseía rutina vinculada.
3. **Inmutabilidad de la plantilla base**:
   - `RoutineTemplate` referenciada por `template_id` no se modifica. Si la plantilla base se elimina o modifica más tarde, la rutina asignada conserva su copia íntegra con `ondelete="SET NULL"`.

---

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

# Data Model: US-53

## ExerciseSafeVariant
- `id`, `exercise_id` (FK `exercises`, ejercicio de riesgo), `variant_exercise_id` (FK `exercises`, ejercicio variante), `covered_zones` (lista de textos normalizados, no vacía), `created_at`, `updated_at` (UTC)
- Ambos ejercicios pertenecen al mismo entrenador y no están dados de baja; `exercise_id` ≠ `variant_exercise_id`; `covered_zones` ⊆ `contraindicated_zones` del ejercicio de riesgo; la variante no puede tener contraindicada ninguna zona de `covered_zones`.
- Único por (`exercise_id`, `variant_exercise_id`). Dar de baja un ejercicio que es variante la deja inactiva: no se resuelve más y se reabren los casos que cubría.

## SafeVariantCase
- `id`, `student_id` (FK `student_profiles`), `exercise_id` (FK `exercises`), `status` (`PENDING` | `RESOLVED`), `created_at`, `resolved_at` (nullable)
- Único por (`student_id`, `exercise_id`). Sirve para emitir una sola `Notification` al entrenador por caso pendiente.

## Resolución (no persistida)
`conflicto = {zonas del ejercicio} ∩ {zonas protegidas del alumno}`
- vacío → `SAFE`: se muestra el ejercicio original.
- existe variante activa con `covered_zones ⊇ conflicto` → `VARIANT` (la más antigua).
- en otro caso → `BLOCKED` (`can_skip: true`) y se abre/mantiene el caso `PENDING`.

## Transiciones del caso
`(nuevo)` → `PENDING` → (el entrenador crea/edita una variante que cubre el conflicto) → `RESOLVED` → (nueva consulta sin cobertura, p. ej. cambian las restricciones) → `PENDING` + nueva notificación.

# Data Model: US-54

## ExerciseReplacementLog
- `id`, `student_id` (FK `student_profiles`), `routine_id`, `day_name`, `session_date` (fecha UTC), `original_exercise_id` (FK `exercises`), `replacement_exercise_id` (FK `exercises`, nullable: nulo = el alumno salteó), `updated_at` (UTC)
- Único por (`student_id`, `routine_id`, `day_name`, `session_date`, `original_exercise_id`): cada nueva elección o salto sobrescribe la anterior.
- La alternativa debe estar en la lista calculada vigente; no modifica `StudentRoutine`.

## Alternativas (no persistidas)
`alternativas = ejercicios del mismo entrenador, no dados de baja, ≠ original, mismo target_muscle_group, sin zonas de riesgo en común con las zonas protegidas del alumno`. Vacío → el alumno puede saltear.
