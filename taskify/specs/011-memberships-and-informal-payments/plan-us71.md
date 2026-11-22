# Plan de implementación: US-71 — Ver vencimiento de la suscripción e informar pago

**Branch**: `feature/us-71-student-subscription` (desde `sprint6`; PR hacia `sprint6`) | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md) (Sesión 2026-11-17 — US-71)

**Alcance**: escenarios 1–6 de US-71 (el 6 viene de US-34) y el bloqueo de FR-006. Depende de US-34, ya mergeada en `sprint6`. No depende de US-35.

## Resumen

Se reutiliza todo lo de US-34. El vencimiento sigue siendo `inicio + (1 + meses CONFIRMADO)`, así que un pago informado (`PENDIENTE_CONFIRMACION`) o rechazado no lo mueve, y confirmarlo lo extiende sin lógica nueva.

| Pieza | Cambio |
|---|---|
| `informal_payments` | Columnas nuevas (migración aditiva): `source` (`TRAINER`/`STUDENT`, por defecto `TRAINER`), `confirmed_by_user_id`, `confirmed_at`, `rejected_by_user_id`, `rejected_at`, `rejection_reason`, `receipt_path`, `receipt_filename`, `receipt_mime_type`, `receipt_size`. |
| `subscription_service` | `current_date()` (el "hoy" del servidor, simulable en las pruebas) y `relationship_status(db, relationship, today)` para reutilizar el cálculo. |
| `core/storage.py` | `save_upload` y `open_upload` reciben la carpeta base; los comprobantes van a `backend/uploads/payment_receipts/<relationship_id>/`. |
| Servicio nuevo `student_subscription_service` | Suscripciones del alumno, historial, informar pago con comprobante, descarga del comprobante (alumno o entrenador del vínculo). |
| `informal_payment_service` | `confirm_payment` y `reject_payment`; `void_payment` solo anula confirmados; `pending_payment_count` en `SubscriptionSummary`; la vista del pago incluye origen, confirmación, rechazo y comprobante. |
| `routine_template_service.start_student_workout_session` | 409 si la suscripción del vínculo está vencida (FR-006). |
| Notificaciones | `PAYMENT_REPORTED` (al entrenador), `PAYMENT_CONFIRMED` y `PAYMENT_REJECTED` (al alumno). |

## API

Alumno:
- `GET /api/v1/students/me/subscriptions?date=`: suscripciones de sus vínculos activos (con nombre del entrenador y pagos pendientes).
- `GET /api/v1/students/me/subscriptions/{relationship_id}/payments?date=`: suscripción e historial.
- `POST /api/v1/students/me/subscriptions/{relationship_id}/payments?date=` (multipart: `paid_on`, `amount`, `method`, `months_covered`, `note`, `receipt` opcional) → 201, pago `PENDIENTE_CONFIRMACION`.

Ambas partes del vínculo:
- `GET /api/v1/payments/{payment_id}/receipt`: descarga autenticada del comprobante (404 para terceros).

Entrenador:
- `POST /api/v1/trainers/me/payments/{payment_id}/confirm?date=` → 200 (409 si no está pendiente).
- `POST /api/v1/trainers/me/payments/{payment_id}/reject?date=` con `{reason}` → 200 (409 si no está pendiente; 422 sin motivo).

Contrato: [contracts/student-payments-api.yaml](./contracts/student-payments-api.yaml).

## Frontend

- **Alumno**: la tarjeta de "Mis entrenadores" suma el bloque de la suscripción (vencimiento, estado, "Informar pago", "Ver pagos"). El inicio muestra un aviso si alguna suscripción está "Por vencer" o "Vencida". "Rutina del día" muestra un bloqueo con "Informar pago" si la suscripción está vencida. Se agregan el diálogo "Informar pago", con comprobante, y el historial de pagos del alumno.
- **Entrenador**: en "Suscripciones", cada fila cuenta los pagos informados y en el historial hay "Confirmar" y "Rechazar" (con motivo), más la descarga del comprobante. El inicio muestra un aviso con las suscripciones vencidas y los pagos por confirmar.
- **Notificaciones**: `PAYMENT_REPORTED` lleva a "Suscripciones" del alumno; `PAYMENT_CONFIRMED` y `PAYMENT_REJECTED`, a "Mis entrenadores".

## Verificación de la Constitución

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Avisos con texto (no solo color), diálogos accesibles, controles ≥ 44 px. |
| III. Privacidad | PASS | El comprobante vive en almacenamiento privado y se descarga solo con autorización del vínculo, igual que el apto médico. |
| IV. Pagos | PASS | Sin pasarela. Los pagos informados no se borran: se confirman, se rechazan con motivo o, si están confirmados, se anulan. La auditoría registra quién confirmó o rechazó, y cuándo. |
| VI. Verificación | PASS | Pruebas de API de los 6 escenarios, del bloqueo y de autorización. Corrida de la suite completa con una fecha futura simulada para detectar pruebas que dependan del calendario. |
| VII. Entrega incremental | PASS | Una story, un PR hacia `sprint6`, con su precedente (US-34) mergeado. |
