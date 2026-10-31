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
