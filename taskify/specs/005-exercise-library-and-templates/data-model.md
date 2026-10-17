# Data Model: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15

## Entidades y Atributos

### 1. `Exercise` (US-08, US-12, US-52)
Catálogo de ejercicios disponibles para diseño de entrenamientos.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | Sí | `None` | Si es nulo, es un ejercicio provisto por el sistema (`is_system = True`). |
| `name` | String(150) | No | - | Nombre del ejercicio (ej. "Sentadilla búlgara"). |
| `description` | Text | No | - | Descripción y metodología de ejecución. |
| `target_muscle_group` | String(100) | No | - | Músculo principal trabajado (ej. "Cuádriceps", "Pectoral"). |
| `equipment_needed` | String(150) | No | - | Materiales requeridos (ej. "Mancuernas", "Sin materiales / Peso corporal"). |
| `video_url` | String(500) | Sí | `None` | URL externa válida a YouTube, Vimeo o Google Drive (US-12). |
| `video_platform` | Enum(`YOUTUBE`, `VIMEO`, `GOOGLE_DRIVE`, `NONE`) | No | `'NONE'` | Plataforma detectada a partir de la URL. |
| `technical_cues` | Text | Sí | `None` | Notas técnicas y claves de respiración (US-52). |
| `is_system` | Boolean | No | `False` | Indica si pertenece a la biblioteca global de Set to Set. |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de creación. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de modificación. |

### 2. `RoutineTemplate` (Plantillas Genéricas, US-09)
Plantillas predeterminadas configuradas por el entrenador para reutilizar con alumnos.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | No | - | Clave foránea al entrenador creador. |
| `name` | String(150) | No | - | Título de la rutina (ej. "Full Body Hipertrofia 3 Días"). |
| `duration_weeks` | Integer | No | `4` | Duración prevista en semanas. |
| `intensity` | Enum(`BAJA`, `MEDIA`, `ALTA`, `EXIGENTE`) | No | `'MEDIA'` | Nivel de intensidad. |
| `has_no_materials_alternative` | Boolean | No | `False` | Si es apta para realizar sin equipamiento (US-09). |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de creación. |

### 3. `RoutineTemplateExercise`
Asociación ordenada de ejercicios dentro de una plantilla genérica.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `template_id` | UUID / String(36) | No | - | Clave foránea a `RoutineTemplate.id`. |
| `exercise_id` | UUID / String(36) | No | - | Clave foránea a `Exercise.id`. |
| `order_index` | Integer | No | `0` | Orden de ejecución en la sesión. |
| `default_sets` | Integer | No | `3` | Cantidad sugerida de series. |
| `default_reps` | String(50) | No | `'10-12'` | Rango sugerido de repeticiones. |
