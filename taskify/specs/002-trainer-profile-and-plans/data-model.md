# Data Model: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Feature**: `002-trainer-profile-and-plans`
**Date**: 2026-10-15

## Entidades y Atributos

### 1. `TrainerProfile`
Datos profesionales del entrenador asociados a su cuenta de usuario.

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `user_id` | UUID / String(36) | No | - | Clave foránea 1:1 referenciando a `User.id`. Índice único. |
| `full_name` | String(150) | Sí | `None` | Nombre y apellido profesional; obligatorio para publicar (US-02). |
| `contact_phone` | String(50) | Sí | `None` | Teléfono / WhatsApp de contacto; obligatorio para publicar (US-02). Formato según Constitución: `+` opcional y 8 a 15 dígitos. |
| `specialty` | String(100) | Sí | `None` | Especialidad principal; obligatoria para publicar (ej. Hipertrofia, Rehabilitación) (US-02). |
| `status` | Enum(`DRAFT`, `PUBLISHED`) | No | `DRAFT` | `PUBLISHED` solo si `contact_phone` y `specialty` están cargados; `DRAFT` no es visible en búsquedas ni perfil público. |
| `bio` | Text | Sí | `None` | Biografía y metodología de trabajo. |
| `certifications` | Text | Sí | `None` | Títulos y certificaciones académicas/deportivas. |
| `max_students` | Integer | No | `0` | Límite máximo de alumnos activos (0 a 100) (US-04). |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de creación. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de última actualización. |

### 2. `TrainingPlan`
Paquetes o planes de entrenamiento mensuales ofrecidos por el entrenador (US-03).

| Campo | Tipo | Nulo | Por Defecto | Descripción |
|---|---|---|---|---|
| `id` | UUID / String(36) | No | `uuid4()` | Identificador primario. |
| `trainer_id` | UUID / String(36) | No | - | Clave foránea referenciando a `TrainerProfile.id`. |
| `title` | String(100) | No | - | Título del paquete (ej. "Plan Personalizado Full"). |
| `description` | Text | Sí | `None` | Detalle de los servicios incluidos. |
| `monthly_price` | Numeric(10, 2) | No | - | Tarifa mensual (0 a 1.000.000) (US-03). |
| `currency` | String(3) | No | `'ARS'` | Moneda (por defecto ARS) (US-03). |
| `is_active` | Boolean | No | `True` | Estado de publicación del paquete. |
| `created_at` | DateTime (UTC) | No | `utcnow()` | Fecha de alta. |
| `updated_at` | DateTime (UTC) | No | `utcnow()` | Fecha de edición. |

## Reglas de Validación

- **Cupos**: `0 <= max_students <= 100`. Si no se especifica, por defecto es 0.
- **Tarifa**: `0 <= monthly_price <= 1000000.00`.
- **Guardado parcial**: `full_name`, `contact_phone`, `specialty`, `bio` y `certifications` pueden actualizarse de forma parcial mientras el perfil permanece en `DRAFT`; los valores enviados no pueden ser cadenas vacías.
- **Teléfono**: regex `^\+?[0-9]{8,15}$` (sin espacios ni guiones).
- **Estado del perfil**: `status = PUBLISHED` si y solo si `full_name`, `contact_phone` y `specialty` no son nulos; se recalcula en cada guardado. Un perfil ya `PUBLISHED` rechaza actualizaciones que eliminen cualquiera de esos campos.
- **No retroactividad**: editar `monthly_price` o archivar un `TrainingPlan` (`is_active = False`) no modifica el arancel acordado de vínculos activos; el vínculo conserva el precio vigente al momento de aceptarse.
