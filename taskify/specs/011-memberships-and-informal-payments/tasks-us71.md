---
description: "Lista de tareas de US-71 de la feature 011"
---

# Tasks: US-71 — Ver vencimiento de la suscripción e informar pago

**Entrada**: `spec.md` (Sesión 2026-11-17 — US-71), `plan-us71.md`, `contracts/student-payments-api.yaml`
**Alcance**: solo US-71 (escenarios 1–6 y FR-006). PR hacia `sprint6`. **Pruebas**: obligatorias (Principio VI).

## Fase 1: Backend

- [X] T001 [US71] Columnas nuevas de `informal_payments` en `backend/src/models/informal_payment.py` y sus `ColumnMigration` en `backend/src/core/migrations.py`; prueba de migración sobre una tabla de US-34 existente en `backend/tests/test_database_migrations.py`.
- [X] T002 [US71] `backend/src/core/storage.py`: carpeta base configurable en `save_upload` y `open_upload` (sin cambiar el comportamiento del apto médico).
- [X] T003 [US71] `backend/src/services/subscription_service.py`: `current_date()` y `relationship_status()`.
- [X] T004 [US71] `backend/src/services/informal_payment_service.py`: `confirm_payment`, `reject_payment`, `void_payment` solo para confirmados, `pending_payment_count` en el resumen, campos nuevos en `PaymentView`; esquemas en `backend/src/schemas/informal_payment.py`.
- [X] T005 [US71] `backend/src/services/student_subscription_service.py`: suscripciones del alumno, historial, informar pago con comprobante y descarga del comprobante; notificaciones `PAYMENT_REPORTED`, `PAYMENT_CONFIRMED` y `PAYMENT_REJECTED`.
- [X] T006 [US71] Rutas en `backend/src/api/v1/students.py` (alumno), `backend/src/api/v1/trainers.py` (confirmar y rechazar) y la descarga del comprobante.
- [X] T007 [US71] Bloqueo de FR-006 en `start_student_workout_session` (409 con suscripción vencida).
- [X] T008 [US71] `backend/tests/test_us71_student_subscription_api.py`: escenarios 1–6, bloqueo y desbloqueo al confirmar, el pago pendiente no desbloquea, comprobante (tipos, tamaño, descarga y autorización), terceros, roles y validación.
- [X] T009 [US71] Buscar pruebas que dependan del calendario: las que crean vínculos con fecha de inicio fija e inician sesiones. Solo había una (`test_us26_session_adjustment_api.py`, inicio fijo el 01/11/2026) y pasó a `date.today()`. Una corrida con `current_date()` un año adelante no sirve como diagnóstico, porque vence cualquier vínculo.

## Fase 2: Frontend

- [X] T010 [P] [US71] Tipos y servicios (`frontend/src/types/payment.ts`, `frontend/src/services/paymentService.ts`).
- [X] T011 [US71] `StudentPaymentDialog` (informar pago con comprobante) y `StudentPaymentHistory`.
- [X] T012 [US71] Bloque de suscripción en `ActivePlanCard` / `StudentActivePlansPage`; aviso en el inicio del alumno; bloqueo en `StudentRoutinesPage`.
- [X] T013 [US71] Entrenador: pagos pendientes en `TrainerSubscriptionsPage` y `PaymentHistory` (confirmar, rechazar, comprobante); aviso en el inicio; ruteo de las notificaciones nuevas.

## Fase 3: Verificación

- [X] T014 `ruff check backend`, `pytest --cov=backend/src` (≥ 90 %), `npm run build`.
- [X] T015 Recorrido en el navegador con la demo: alumno y entrenador, todos los escenarios y el bloqueo.
- [X] T016 Commit y PR hacia `sprint6`.
