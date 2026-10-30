# Data Model: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15 (actualizado 2026-10-30 tras `/speckit-clarify`)

## Entidades y Atributos

### 1. `Exercise` (US-08, US-12, US-52)
Ejercicio de la biblioteca personal de un entrenador.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | No | - | Clave foránea a `TrainerProfile.id`, propietario del ejercicio. |
| `name` | String(150) | No | - | Nombre del ejercicio (ej. "Sentadilla búlgara"). |
| `description` | Text | No | - | Descripción y metodología de ejecución. |
| `category` | Enum(`FUERZA`, `CARDIO`, `MOVILIDAD`, `FLEXIBILIDAD`, `EQUILIBRIO`) | No | - | Tipo de ejercicio. |
| `target_muscle_group` | String(100) | No | - | Músculo principal trabajado (ej. "Cuádriceps", "Pectoral"). |
| `equipment_needed` | String(150) | No | - | Materiales requeridos (ej. "Mancuernas", "Sin materiales / Peso corporal"). |
| `has_no_materials_alternative` | Boolean | No | `False` | Indica que el ejercicio tiene alternativa "Sin materiales" (US-09). |
| `deleted_at` | DateTime (UTC) | Sí | `None` | Baja lógica: si tiene valor, el ejercicio no se lista ni se puede seleccionar. |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de creación. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de modificación. |

**Pendiente de US-12 y US-52** (no se implementa en US-08): `video_url` String(500), `video_platform` Enum(`YOUTUBE`, `VIMEO`, `GOOGLE_DRIVE`, `NONE`) y `technical_cues` Text.

### 2. `RoutineTemplate` (Plantillas Genéricas, US-09)
Plantillas predeterminadas configuradas por el entrenador para reutilizar con alumnos.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | No | - | Clave foránea a `TrainerProfile.id`, entrenador creador. |
| `name` | String(150) | No | - | Título de la rutina (ej. "Full Body Hipertrofia 3 Días"). |
| `duration_weeks` | Integer | No | - | Duración prevista en semanas, entre 1 y 52. |
| `intensity` | Enum(`BAJA`, `MEDIA`, `ALTA`, `EXIGENTE`) | No | - | Nivel de intensidad. |
| `has_no_materials_alternative` | Boolean | No | `False` | Si es apta "Sin materiales" (US-09). |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de creación. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de modificación. |

### 3. `RoutineTemplateDay`
Día ordenado de una rutina. Toda rutina tiene entre 1 y 7 días.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `template_id` | UUID / String(36) | No | - | Clave foránea a `RoutineTemplate.id`. |
| `order_index` | Integer | No | - | Posición del día dentro de la rutina. |
| `name` | String(100) | No | - | Nombre del día (ej. "Día 1 - Empuje"). |

### 4. `RoutineTemplateBlock`
Bloque ordenado de un día. Todo día tiene entre 1 y 10 bloques.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `day_id` | UUID / String(36) | No | - | Clave foránea a `RoutineTemplateDay.id`. |
| `order_index` | Integer | No | - | Posición del bloque dentro del día. |
| `name` | String(100) | No | - | Nombre del bloque (ej. "Entrada en calor"). |

### 5. `RoutineTemplateExercise`
Asociación ordenada de ejercicios dentro de un bloque. Todo bloque tiene entre 1 y 30 ejercicios.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `block_id` | UUID / String(36) | No | - | Clave foránea a `RoutineTemplateBlock.id`. |
| `exercise_id` | UUID / String(36) | No | - | Clave foránea a `Exercise.id`. |
| `order_index` | Integer | No | - | Orden de ejecución en el bloque. |
| `sets` | Integer | No | - | Cantidad de series, entre 1 y 20. |
| `reps` | String(50) | No | - | Repeticiones o rango (ej. "10-12"). |
| `rest_seconds` | Integer | No | - | Descanso en segundos, entre 0 y 600. |

## Reglas de Integridad

- Días, bloques y ejercicios se reemplazan como conjunto al editar una rutina; `order_index` se deriva de la posición recibida.
- Un `Exercise` con `deleted_at` no puede agregarse a una rutina, pero se conserva en las rutinas que ya lo incluyen.
- Si `RoutineTemplate.has_no_materials_alternative` es verdadero, todos sus ejercicios deben tener `has_no_materials_alternative` verdadero.
- Un `Exercise` incluido en una rutina apta "Sin materiales" no puede perder su marca.
