# Plan de implementación: US-34 — Registrar pagos y controlar el estado de las suscripciones

**Branch**: `feature/us-34-informal-payments` (desde `sprint6`; PR hacia `sprint6`) | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Alcance**: solo US-34 (escenarios 1, 2, 3, 5 y 6). Fuera de este plan (Principio VII: una story por PR):

- US-35 (baja del alumno y estado `CANCELADA`).
- US-71: vista del alumno, alertas de vencimiento, pago informado por el alumno con comprobante y su confirmación o rechazo (ex escenario 4 de US-34), y bloqueo de la "Rutina del día" con la suscripción vencida (FR-006).

## Resumen

El entrenador tiene una sección **"Suscripciones"** con sus alumnos activos, el paquete, el vencimiento y el estado ("Al día", "Por vencer" o "Vencida"). Desde ahí registra pagos recibidos por fuera de la app, consulta el historial de cada alumno y anula un pago mal cargado indicando el motivo, con la opción de registrar el pago corregido referenciando al anulado.

Decisión central (ver [research.md](./research.md)): **la suscripción no se guarda, se calcula**. El vínculo activo (`TrainingRelationship`) es la suscripción, y el vencimiento se deriva de su fecha de inicio y de los meses de los pagos confirmados no anulados:

```text
vencimiento = sumar_meses(start_date, 1 + Σ months_covered de pagos CONFIRMADO)
```

Esto cumple las tres decisiones de la spec (sesión 2026-11-16): el primer mes se considera abonado, los pagos extienden desde el vencimiento anterior aunque se paguen tarde, y una anulación recalcula el vencimiento sin lógica extra. Tampoco hace falta migrar datos: los vínculos activos existentes obtienen su vencimiento de su `start_date`.

Se crea una sola tabla nueva, `informal_payments`. Es un libro de pagos inmutable: sin endpoint de borrado y con un guard del ORM que impide el borrado físico. La anulación y la reemisión se registran en la misma tabla (`void_*` y `replaces_payment_id`).

## Reutilización (no duplicar)

- `trainer_student_service._trainer_profile` y `_active_relationship` para resolver el entrenador autenticado y validar el vínculo activo (autorización en el servidor, 404 si no hay vínculo).
- `trainer_student_service.list_trainer_students` define qué es un "alumno activo"; el listado de suscripciones usa el mismo criterio (`status == "ACTIVE"`).
- `TrainingRelationship.agreed_monthly_price` y `agreed_currency` para precargar el monto y fijar la moneda (ARS por defecto, según la Constitución).
- `api/errors.py`: errores RFC 7807 con `errors[]` por campo; `TrainerStudentError` + `handle_student_error` en `api/v1/trainers.py`.
- El parámetro `date` con la fecha local del cliente, como en `GET /me/daily-routines` (US-22), para calcular "hoy" sin depender de la zona del servidor.
- Frontend: el cliente `services/api.ts`, `ProtectedRoute`, el patrón de tarjetas de la home del entrenador (`HomePage.tsx`) y los diálogos existentes (`RequestActionModal.tsx`) como referencia de modal accesible.

## Contexto técnico

**Lenguaje/Versión**: Python 3.12; TypeScript/React 18; Node.js 20

**Dependencias principales**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Pytest, React Router, Axios (todas existentes; sin dependencias nuevas, `sumar_meses` se implementa con la librería estándar)

**Almacenamiento**: tabla nueva `informal_payments`, creada por `Base.metadata.create_all` en `core/migrations.py` (aditiva e idempotente; sin cambios en tablas existentes)

**Pruebas**: Pytest (integración de API + unitarias del cálculo de vencimiento), Ruff, `npm run build`, cobertura ≥ 90 % del pipeline

**Plataforma objetivo**: aplicación web responsiva en servidor Linux

**Tipo de proyecto**: aplicación web existente (FastAPI + React)

**Rendimiento**: el listado se resuelve con 2 consultas (vínculos activos del entrenador + suma de meses confirmados agrupada por vínculo) y el cálculo en memoria. Escala esperada: decenas de alumnos por entrenador.

**Restricciones**: solo el entrenador del vínculo activo ve o carga pagos; rol alumno → 403; sin token → 401. Fechas de pago como fecha calendario; marcas de auditoría en UTC ISO 8601. Moneda del vínculo. Errores RFC 7807.

**Escala/Alcance**: un entrenador, decenas de alumnos, decenas de pagos por alumno.

## Verificación de la Constitución

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Responsivo; contraste ≥ 4.5:1; controles ≥ 44×44 px; el estado se comunica con texto además del color ("Vencida", "Por vencer: faltan 3 días"); el formulario marca los campos faltantes con mensajes comprensibles (escenario 3). |
| II. IA con supervisión | N/A | Sin IA. |
| III. Privacidad de salud | PASS | No expone datos de salud. La autorización por vínculo activo se valida en el backend en cada petición. |
| IV. Pagos informales | PASS | Sin pasarela de pagos (FR-009). Sin borrado físico: no hay endpoint DELETE y un guard `before_delete` del ORM lo impide (FR-003). Anulación con motivo, fecha y usuario obligatorios, y reemisión que referencia al original (FR-004). |
| V. Medios externos | N/A | US-34 no adjunta comprobantes (son de US-71). |
| VI. Verificación continua | PASS | Pruebas de API y unitarias, Ruff y build del frontend en CI. |
| VII. Entrega incremental | PASS | Una story, un PR hacia `sprint6` (rama de integración del sprint; al cierre del sprint, `sprint6` se mergea a `develop`, por decisión del equipo del 2026-11-16). Depende de US-07/US-49 (vínculo activo con tarifa acordada), ya mergeadas. US-35 y US-71 parten de esta story mergeada. |

Re-evaluación post-diseño: PASS, con una excepción documentada en *Seguimiento de complejidad*.

## Estructura del proyecto

### Documentación

```text
taskify/specs/011-memberships-and-informal-payments/
├── spec.md                       (clarificaciones 2026-11-16)
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/informal-payments-api.yaml
├── checklists/requirements.md
└── tasks.md
```

### Código fuente

```text
backend/
├── src/
│   ├── models/informal_payment.py              (nuevo; guard before_delete)
│   ├── models/__init__.py                      (registrar el modelo)
│   ├── schemas/informal_payment.py             (nuevo)
│   ├── services/subscription_service.py        (nuevo; cálculo de vencimiento y estado)
│   ├── services/informal_payment_service.py    (nuevo; registrar, anular, historial)
│   └── api/v1/trainers.py                      (4 rutas nuevas)
├── scripts/seed_demo.py                        (purga de demo: borra pagos demo antes de los vínculos; escenarios de demo)
└── tests/
    ├── test_us34_subscription_service.py       (nuevo; unitarias)
    └── test_us34_informal_payments_api.py      (nuevo; integración)
frontend/
└── src/
    ├── constants/routes.ts                     (trainerSubscriptions: '/entrenador/suscripciones')
    ├── types/payment.ts                        (nuevo)
    ├── services/paymentService.ts              (nuevo)
    ├── pages/TrainerSubscriptionsPage.tsx      (nuevo)
    ├── components/PaymentFormDialog.tsx        (nuevo)
    ├── components/PaymentHistory.tsx           (nuevo; incluye anulación)
    ├── components/TrainerStudentDetail.tsx     (enlace "Pagos y vencimiento")
    ├── pages/HomePage.tsx                      (tarjeta "Suscripciones")
    ├── App.tsx                                 (ruta protegida rol entrenador)
    └── styles.css                              (estilos de la sección)
```

**Decisión de estructura**: `subscription_service` (cálculo puro, sin I/O, reutilizable por US-35 y US-71) separado de `informal_payment_service` (persistencia y reglas de anulación). Las rutas van en `trainers.py` bajo `/me/...`, igual que el resto de las vistas del entrenador.

## Seguimiento de complejidad

| Excepción | Por qué | Alternativa descartada |
|---|---|---|
| La purga de usuarios demo (`seed_demo.py`, solo `@demo.settoset.com`) borra físicamente sus pagos con un `DELETE` SQL masivo antes de borrar los vínculos. | La purga ya elimina todo el grafo de datos demo (vínculos, solicitudes, paquetes); sin esto la FK de `informal_payments` impide resetear la demo. No es un flujo de la aplicación ni afecta datos reales. | Anular los pagos demo en vez de borrarlos: los vínculos no podrían borrarse y la demo dejaría de ser idempotente. |
