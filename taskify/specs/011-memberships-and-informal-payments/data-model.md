# Data Model: US-34 — Pagos informales y estado de suscripciones

**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## Tabla nueva: `informal_payments` (modelo `InformalPayment`)

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | `String(36)` PK | no | `new_id()` |
| `relationship_id` | `String(36)` FK `training_relationships.id` | no | indexada; **sin** `ON DELETE CASCADE` (R4) |
| `trainer_id` | `String(36)` FK `trainer_profiles.id` | no | indexada; desnormalizada para autorizar sin join |
| `student_id` | `String(36)` FK `student_profiles.id` | no | indexada |
| `paid_on` | `Date` | no | fecha en que el alumno pagó; ≤ "hoy" |
| `amount` | `Numeric(10, 2)` | no | `CHECK amount > 0` |
| `currency` | `String(3)` | no | copia de `agreed_currency` del vínculo |
| `method` | `String(16)` | no | `CHECK method IN ('EFECTIVO','TRANSFERENCIA','OTRO')` |
| `months_covered` | `Integer` | no | `CHECK months_covered BETWEEN 1 AND 12` |
| `status` | `String(24)` | no | `CHECK status IN ('PENDIENTE_CONFIRMACION','CONFIRMADO','RECHAZADO','ANULADO')`; US-34 crea `CONFIRMADO` |
| `note` | `Text` | sí | ≤ 500 caracteres (validado en el esquema) |
| `registered_by_user_id` | `String(36)` FK `users.id` | no | usuario que cargó el pago |
| `created_at` | `DateTime(tz)` | no | UTC |
| `voided_at` | `DateTime(tz)` | sí | UTC |
| `voided_by_user_id` | `String(36)` FK `users.id` | sí | |
| `void_reason` | `Text` | sí | 5–500 caracteres |
| `replaces_payment_id` | `String(36)` FK `informal_payments.id` | sí | `UNIQUE`; debe apuntar a un pago `ANULADO` del mismo vínculo |

**Constraints adicionales**

- `ck_informal_payments_void_fields`: `(status = 'ANULADO') = (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)`. Se escribe como `(status = 'ANULADO' AND voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL) OR (status <> 'ANULADO' AND voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)` para ser portable entre SQLite y PostgreSQL.
- `uq_informal_payments_replaces`: `UNIQUE (replaces_payment_id)`.
- Índice `ix_informal_payments_relationship_status`: `(relationship_id, status)` para la suma de meses confirmados.

**Inmutabilidad**: listener `event.listens_for(InformalPayment, "before_delete")` que lanza `RuntimeError("Los pagos no se eliminan; se anulan.")`. Fuera de las columnas `status`/`void_*` no hay actualizaciones: el servicio solo escribe esas columnas al anular.

**Transiciones de estado (US-34)**

```text
(nuevo) ──registrar──▶ CONFIRMADO ──anular(motivo)──▶ ANULADO   (terminal)
```

`PENDIENTE_CONFIRMACION → CONFIRMADO | RECHAZADO` queda reservado para US-71.

## Sin cambios en tablas existentes

`TrainingRelationship` aporta `start_date`, `status`, `plan_id`, `agreed_monthly_price` y `agreed_currency`. No se agregan columnas.

## DTOs calculados (no persistidos)

### `SubscriptionSummary`

| Campo | Tipo | Origen |
|---|---|---|
| `relationship_id` | str | vínculo |
| `student_id` | str | vínculo |
| `student_name` | str | `StudentProfile.first_name + last_name` (o el email si no hay nombre) |
| `plan_id`, `plan_title` | str | `TrainingPlan` |
| `agreed_monthly_price` | Decimal | vínculo |
| `currency` | str | vínculo |
| `start_date` | date | vínculo |
| `months_paid` | int | Σ `months_covered` de pagos `CONFIRMADO` |
| `due_date` | date | `sumar_meses(start_date, 1 + months_paid)` |
| `days_until_due` | int | `due_date − hoy` (negativo si está vencida) |
| `status` | `AL_DIA` \| `POR_VENCER` \| `VENCIDA` | R3 |
| `last_payment_on` | date \| null | `max(paid_on)` de pagos `CONFIRMADO` |

Orden del listado: `VENCIDA`, luego `POR_VENCER` y luego `AL_DIA`; dentro de cada grupo, por `due_date` ascendente y después por nombre.

### `PaymentView`

Todos los campos de la tabla más `registered_by_name`, `voided_by_name` (nombre del perfil del usuario) y `replaced_by_payment_id` (el pago que lo reemplazó, si existe). El historial se ordena por `paid_on` descendente y luego por `created_at` descendente, e incluye los anulados.

## Ejemplos del cálculo

| start_date | pagos confirmados (meses) | due_date | hoy | estado |
|---|---|---|---|---|
| 2026-10-01 | — | 2026-11-01 | 2026-10-20 | AL_DIA (12 días) |
| 2026-10-01 | — | 2026-11-01 | 2026-10-28 | POR_VENCER (4) |
| 2026-10-01 | — | 2026-11-01 | 2026-11-01 | POR_VENCER (0) |
| 2026-10-01 | — | 2026-11-01 | 2026-11-02 | VENCIDA (−1) |
| 2026-10-01 | 1 (pagado tarde el 10/11) | 2026-12-01 | 2026-11-10 | AL_DIA (21) |
| 2026-10-01 | 1 + 3 | 2027-03-01 | 2026-11-10 | AL_DIA |
| 2026-01-31 | 1 | 2026-03-31 | — | (sin desplazamiento) |
| 2026-01-31 | — | 2026-02-28 | — | (recorte a fin de mes) |
