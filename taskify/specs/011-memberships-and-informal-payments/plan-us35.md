# Plan de implementación: US-35 — Dar de baja a un alumno

**Branch**: `feature/us-35-student-termination` (desde `sprint6`; PR hacia `sprint6`) | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md) (Sesión 2026-11-17)

**Alcance**: escenarios 1–3 de US-35. Depende de US-34 (suscripción calculada sobre el vínculo activo), ya mergeada en `sprint6`. Fuera de alcance: reactivar una baja y una vista de "ex alumnos".

## Resumen

El entrenador da de baja al alumno desde el detalle del alumno ("Mis alumnos"), eligiendo una categoría y, si corresponde, un detalle. El vínculo pasa a `TERMINATED` y el resto de la app ya reacciona sola, porque todas las vistas y autorizaciones filtran por vínculo `ACTIVE`:

| Efecto | Dónde ocurre | Cambio necesario |
|---|---|---|
| Libera el cupo | `trainer_service.count_active_students` | ninguno |
| Sale de "Mis alumnos" y de "Suscripciones" (sin vencimientos) | `list_trainer_students`, `informal_payment_service.list_subscriptions` | ninguno |
| Revoca el acceso a datos de salud | `student_service.trainer_has_access` | ninguno |
| La rutina deja de estar disponible para el alumno | `student_routine_service.student_assigned_view` | ninguno |
| Chat en modo lectura | `conversation_service.require_active` (US-21) | ninguno |
| Notificación al alumno con el motivo | nuevo, tipo `SUBSCRIPTION_TERMINATED` | nuevo |

Las pruebas verifican cada efecto de la tabla.

## Datos

En `training_relationships` ya existen `status`, `end_date`, `terminated_at` y `termination_reason`. Se agrega `termination_category` (`VARCHAR(24)`, nullable) con una migración aditiva en `core/migrations.py` (`TARGET_COLUMNS`). Al dar de baja: `status = TERMINATED`, `end_date` = fecha de la baja, `terminated_at` = ahora (UTC), `termination_category` y `termination_reason` = detalle (o `NULL`).

Categorías: `FALTA_DE_PAGO`, `RAZONES_PERSONALES`, `OTRO` (con `OTRO`, el detalle es obligatorio).

## API

`POST /api/v1/trainers/me/students/{student_id}/termination`, cuerpo `{ "category": "...", "detail": "..." }`:

- `200` → `{ relationship_id, student_id, status: "TERMINATED", end_date, terminated_at, category, detail, available_slots }`.
- `422` sin categoría, con categoría inválida, con "Otro motivo" sin detalle o con un detalle de más de 500 caracteres (escenario 3), con `errors[]` por campo.
- `404` sin vínculo activo con ese alumno (incluye una baja repetida); `403` con rol alumno; `401` sin token.

Contrato: [contracts/student-termination-api.yaml](./contracts/student-termination-api.yaml).

## Frontend

- `TrainerStudentDetail`: botón "Dar de baja" que abre un diálogo con la categoría (radios), el detalle (con contador), las consecuencias de la baja y el aviso "El alumno verá este motivo". Si confirma, se cierra el detalle y "Mis alumnos" se recarga con un mensaje de éxito.
- `studentNotificationPath`: `SUBSCRIPTION_TERMINATED` → "Mis entrenadores".

## Verificación de la Constitución

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Diálogo con foco atrapado, Escape, radios con etiqueta, controles ≥ 44 px, consecuencias en texto. |
| III. Privacidad | PASS | La revocación es inmediata porque todo el acceso exige vínculo `ACTIVE`; hay una prueba del acceso al cuestionario de salud después de la baja. |
| IV. Pagos | PASS | Los pagos no se tocan: quedan en la base sin borrarse. |
| VI. Verificación | PASS | Pruebas de API de cada escenario y de cada efecto. |
| VII. Entrega incremental | PASS | Una story, un PR hacia `sprint6`, con su precedente (US-34) ya mergeado. |

## Estructura

```text
backend/src/core/migrations.py                       (columna termination_category)
backend/src/models/training_relationship.py          (termination_category)
backend/src/schemas/trainer_student.py               (StudentTerminationRequest/Result)
backend/src/services/student_termination_service.py (nuevo)
backend/src/api/v1/trainers.py                       (ruta POST)
backend/tests/test_us35_student_termination_api.py   (nuevo)
frontend/src/types/trainerStudent.ts, services/trainerStudentService.ts
frontend/src/components/StudentTerminationDialog.tsx (nuevo)
frontend/src/components/TrainerStudentDetail.tsx, pages/TrainerStudentsPage.tsx
frontend/src/constants/routes.ts                     (SUBSCRIPTION_TERMINATED)
```
