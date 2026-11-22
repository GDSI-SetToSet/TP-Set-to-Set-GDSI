---
description: "Lista de tareas de US-34 de la feature 011"
---

# Tasks: US-34 — Registrar pagos y controlar el estado de las suscripciones

**Entrada**: `spec.md` (Clarificaciones 2026-11-16), `plan.md`, `research.md`, `data-model.md`, `contracts/informal-payments-api.yaml`, `quickstart.md`

**Alcance**: solo US-34 (escenarios 1, 2, 3, 5 y 6). US-35 y US-71 no se implementan; el ex escenario 4 (confirmar o rechazar un pago informado) pertenece a US-71.

**Pruebas**: obligatorias por Principio VI (backend con Pytest, cobertura ≥ 90 %; frontend con `npm run build`).

**Formato**: `- [ ] T### [P?] [US34] Descripción con ruta`. `[P]` = archivos distintos y sin dependencias pendientes.

## Fase 1: Preparación

- [X] T001 Crear la rama `feature/us-34-informal-payments` desde `sprint6` actualizado (`git fetch`). Por decisión del equipo (2026-11-16), las stories del Sprint 6 se integran en `sprint6` y al cierre del sprint `sprint6` se mergea a `develop`. Agregar `trainerSubscriptions: '/entrenador/suscripciones'` a `frontend/src/constants/routes.ts`. Revisar en `backend/tests/conftest.py` y `backend/tests/test_trainer_student_api.py` cómo se crean el entrenador, el alumno, el paquete y el vínculo activo, para reutilizarlo en las pruebas.

## Fase 2: Fundacional (bloquea la story)

- [X] T002 [US34] Crear `backend/src/models/informal_payment.py` con `InformalPayment` según `data-model.md`: columnas, `CHECK` de `amount`, `method`, `months_covered`, `status` y `ck_informal_payments_void_fields`, `UNIQUE (replaces_payment_id)`, índice `(relationship_id, status)`, FK a `training_relationships` **sin** `ondelete="CASCADE"`, y el listener `before_delete` que lanza `RuntimeError("Los pagos no se eliminan; se anulan.")`. Registrarlo en `backend/src/models/__init__.py`.
- [X] T003 [US34] Agregar en `backend/tests/test_database_migrations.py` una prueba de que la migración crea `informal_payments` con sus constraints sobre una base existente y de que es idempotente (doble ejecución). Si `create_all` no alcanza para bases ya creadas, agregar la creación en `backend/src/core/migrations.py`.
- [X] T004 [P] [US34] Definir en `backend/src/schemas/informal_payment.py` los esquemas Pydantic `SubscriptionStatus`, `PaymentMethod`, `PaymentStatus`, `SubscriptionSummary`, `PaymentCreate`, `PaymentVoidRequest`, `PaymentView`, `PaymentHistory` y `PaymentMutationResult`, según `contracts/informal-payments-api.yaml`, con las reglas y mensajes de `research.md` R5 (fecha y monto obligatorios con mensaje propio, `amount` > 0 y ≤ 9.999.999,99 con 2 decimales, `months_covered` de 1 a 12, `note` ≤ 500, `reason` de 5 a 500, sin espacios sobrantes).
- [X] T005 [P] [US34] Definir los tipos TypeScript equivalentes en `frontend/src/types/payment.ts`.

## Fase 3: US-34 (P1) — Pagos y estado de suscripciones

**Objetivo**: el entrenador ve el estado de la suscripción de cada alumno activo, registra pagos que extienden el vencimiento, consulta el historial y anula o corrige un pago sin borrarlo.

**Prueba independiente**: ejecutar `pytest backend/tests/test_us34_*.py` y recorrer los 9 pasos manuales de `quickstart.md`.

### Backend

- [X] T006 [US34] Implementar en `backend/src/services/subscription_service.py` funciones puras sin I/O: `add_months(start, n)` desde la fecha de inicio con recorte a fin de mes (R2); `compute_due_date(start_date, months_paid)` = `add_months(start_date, 1 + months_paid)`; y `subscription_status(due_date, today)` → (`status`, `days_until_due`) con `VENCIDA` < 0, `POR_VENCER` de 0 a 5 y `AL_DIA` > 5 (R3).
- [X] T007 [US34] Escribir `backend/tests/test_us34_subscription_service.py` con todos los ejemplos de la tabla de `data-model.md`: bordes de 5, 0 y −1 días, pago tardío que extiende desde el vencimiento anterior, varios pagos acumulados, 31/01 + 1 → 28/02, 31/01 + 2 → 31/03 y año bisiesto.
- [X] T008 [US34] Implementar en `backend/src/services/informal_payment_service.py` `list_subscriptions(db, user, today, status=None)`: vínculos `ACTIVE` del entrenador (resueltos con `_trainer_profile` de `trainer_student_service`) y una sola consulta agregada `SUM(months_covered)` y `MAX(paid_on)` de pagos `CONFIRMADO` agrupada por `relationship_id`. Construye `SubscriptionSummary` con el nombre del alumno (o su email si no tiene nombre) y el título del paquete, y ordena VENCIDA → POR_VENCER → AL_DIA, luego por `due_date` y luego por nombre.
- [X] T009 [US34] Implementar en el mismo servicio `get_payment_history(db, user, student_id, today)`: valida el vínculo activo con `_active_relationship` (404 si no hay) y devuelve `PaymentHistory` con todos los pagos, incluidos los anulados, ordenados por `paid_on` y `created_at` descendentes. Resuelve `registered_by_name`, `voided_by_name` (`TrainerProfile.full_name`, o el email si no hay nombre) y `replaced_by_payment_id`.
- [X] T010 [US34] Implementar en el mismo servicio `register_payment(db, user, student_id, data, today)`. Valida que `paid_on` ≤ `today` (422 con `errors[]` en `paid_on`) y el vínculo activo. Si viene `replaces_payment_id`, exige que sea un pago del mismo vínculo en estado `ANULADO` (si no, 422) y que no esté ya reemplazado (409, también al capturar el `IntegrityError` del `UNIQUE`). Crea el pago `CONFIRMADO` con `currency` del vínculo, `registered_by_user_id` y `created_at` en UTC, y devuelve `PaymentMutationResult` con la suscripción recalculada (FR-001, FR-002).
- [X] T011 [US34] Implementar en el mismo servicio `void_payment(db, user, payment_id, reason, today)`: 404 si el pago no pertenece a un vínculo del entrenador, sin revelar si existe; 409 si ya está `ANULADO`. Completa solo `status`, `voided_at`, `voided_by_user_id` y `void_reason`, y devuelve la suscripción recalculada (FR-003, FR-004).
- [X] T012 [US34] Exponer en `backend/src/api/v1/trainers.py` `GET /me/subscriptions`, `GET /me/students/{student_id}/payments`, `POST /me/students/{student_id}/payments` (201) y `POST /me/payments/{payment_id}/void`, con el parámetro `date` (fecha local, por defecto `date.today()`) y `status` opcional en el listado. Usar `response_model` y mapear los errores del servicio a RFC 7807 con `errors[]` como `handle_error`. Rol alumno → 403 y sin token → 401, igual que las rutas vecinas. Declarar `GET /me/subscriptions` antes de las rutas con parámetros de path que puedan capturarla.
- [X] T013 [US34] Escribir `backend/tests/test_us34_informal_payments_api.py` cubriendo:
  - escenario 1: listado con los tres estados, orden y filtro `status`; lista vacía sin alumnos; alumno recién aceptado "Al día" con vencimiento a 1 mes; alumnos de otro entrenador o con vínculo terminado excluidos.
  - escenario 2: un pago extiende desde el vencimiento anterior aunque esté vencida; `currency` del vínculo.
  - escenario 3: sin `paid_on` ni `amount` → 422 `application/problem+json` con ambos en `errors[]`; fecha futura, monto ≤ 0, meses 0 y 13, y medio inválido → 422.
  - escenario 5: historial con anulados, nombres y orden; anular sin motivo → 422; doble anulación → 409; la anulación recalcula el vencimiento; borrar con `db.delete` → `RuntimeError`; no existe ruta DELETE (405).
  - escenario 6: reemisión con `replaces_payment_id` válido; reemplazar un pago no anulado o de otro vínculo → 422; reemplazar dos veces → 409.
  - autorización: 403 con rol alumno, 401 sin token y 404 con un entrenador ajeno, tanto en el historial como en la anulación.
- [X] T014 [US34] Actualizar la purga de demo en `backend/scripts/seed_demo.py`: antes de borrar los vínculos demo, borrar sus pagos con `delete(InformalPayment).where(...)` masivo, limitado a usuarios `@demo.settoset.com` (excepción documentada en `plan.md`). Sembrar en el vínculo Tomás–Gonzalo un pago anulado y su corrección. Los tres estados a la vez (Al día, Por vencer y Vencida) requieren varios alumnos del mismo entrenador, y la demo tiene uno por entrenador: quedan para el script de demo del Sprint 6 (como `prepare_sprint5_demo.py`). Verificar `backend/tests/test_seed_demo.py` (idempotencia y purga).

### Frontend

- [X] T015 [P] [US34] Crear `frontend/src/services/paymentService.ts` con `listSubscriptions(status?)`, `getPaymentHistory(studentId)`, `registerPayment(studentId, data)` y `voidPayment(paymentId, reason)`, tipados contra `frontend/src/types/payment.ts`. Usar el cliente de `frontend/src/services/api.ts` y enviar siempre `date` con la fecha local (`YYYY-MM-DD`).
- [X] T016 [P] [US34] Crear `frontend/src/components/PaymentFormDialog.tsx`: modal accesible (foco inicial y atrapado, Escape, `aria-modal`) con fecha (hoy por defecto, sin fechas futuras), meses (1–12, por defecto 1), monto precargado con tarifa × meses mientras el entrenador no lo edite, medio (Efectivo, Transferencia u Otro) y nota opcional. Validar en el cliente con los mensajes de R5, marcando todos los campos faltantes a la vez; mostrar los `errors[]` del servidor en su campo. En modo corrección (`replaces_payment_id`), precargar los datos del pago anulado y mostrar "Corrige al pago del dd/mm/aaaa". Controles ≥ 44×44 px.
- [X] T017 [P] [US34] Crear `frontend/src/components/PaymentHistory.tsx`: resumen de la suscripción (paquete, vencimiento, estado con texto y color, días restantes) y lista de pagos con fecha, monto en la moneda del vínculo, medio, meses, "Cargado por" y nota. Los anulados se muestran tachados con "Anulado: motivo, fecha y usuario" y los enlaces "Corrige a…" / "Reemplazado por…". El botón "Anular" pide un motivo obligatorio (5–500 caracteres) y al confirmar ofrece "Registrar pago corregido". No hay ninguna acción de eliminar.
- [X] T018 [US34] Crear `frontend/src/pages/TrainerSubscriptionsPage.tsx`: listado con filtro por estado (Todas, Vencidas, Por vencer, Al día), insignia de estado legible sin depender del color ("Vencida hace 3 días", "Vence en 2 días", "Al día"), vencimiento, paquete y último pago; acciones "Registrar pago" y "Ver historial". El historial se abre en la misma página con `?studentId=` para poder enlazarlo. Incluir estados de carga, error comprensible y vacío ("Todavía no tenés alumnos activos"), y refrescar el listado después de registrar o anular.
- [X] T019 [US34] Registrar la ruta protegida (rol entrenador) en `frontend/src/App.tsx`; agregar la tarjeta "Suscripciones" en la home del entrenador en `frontend/src/pages/HomePage.tsx`; agregar el enlace "Pagos y vencimiento" (`/entrenador/suscripciones?studentId=…`) en `frontend/src/components/TrainerStudentDetail.tsx`.
- [X] T020 [P] [US34] Agregar los estilos responsivos de la sección (listado, insignias con contraste ≥ 4.5:1, pago anulado, modal) en `frontend/src/styles.css`, siguiendo las clases existentes.

## Fase 4: Verificación y cierre

- [X] T021 Ejecutar `ruff check backend` y `pytest --cov=backend/src`, y confirmar cobertura ≥ 90 % sin romper pruebas previas (Principio VI).
- [X] T022 Ejecutar `npm run build` en `frontend/` sin errores.
- [X] T023 Recorrer manualmente `specs/011-memberships-and-informal-payments/quickstart.md` (9 pasos) contra los escenarios de aceptación de la spec.
- [ ] T024 Ejecutar `/speckit-analyze` y `/speckit-converge` sobre US-34, confirmar que no hay requisitos faltantes ni código de US-35 o US-71, y abrir el PR hacia `sprint6` (DoD).

## Dependencias y orden

- T001 → Fase 2 → Fase 3 → Fase 4.
- T002 → T003. T004 y T005 en paralelo con T002.
- Backend: T006 → T007; T008 → T009 → T010 → T011 (mismo archivo: secuenciales; dependen de T002, T004 y T006) → T012 → T013. T014 después de T002.
- Frontend: T015, T016 y T017 en paralelo tras T005; T018 tras T015–T017; T019 tras T018; T020 en paralelo con T018.
- Backend (T006–T014) y frontend (T015–T020) avanzan en paralelo una vez cerrados T004 y T005; la prueba manual (T023) requiere ambos.

## Estrategia

MVP = toda la story. Orden sugerido: modelo y esquemas → cálculo puro con pruebas → servicio y API con pruebas → pantalla. Un único PR hacia `sprint6`, que al cierre del sprint se integra a `develop`. US-35 y US-71 empiezan recién con este PR mergeado.
