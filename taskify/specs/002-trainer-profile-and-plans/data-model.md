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
| `full_name` | String(150) | No | - | Nombre y apellido profesional. |
| `contact_phone` | String(50) | No | - | Teléfono / WhatsApp de contacto obligatorio (US-02). |
| `specialty` | String(100) | No | - | Especialidad principal obligatoria (ej. Hipertrofia, Rehabilitación) (US-02). |
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
- **Campos Mandatorios**: `contact_phone` y `specialty` no pueden ser nulos ni cadenas vacías.
