# Research: US-34 — Pagos informales y estado de suscripciones

**Fecha**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

## R1. ¿Guardar la suscripción o calcularla?

**Decisión**: calcularla. No hay tabla `MembershipSubscription`: la suscripción es el `TrainingRelationship` activo y su vencimiento se deriva:

```text
vencimiento = sumar_meses(start_date, 1 + Σ months_covered de pagos con status CONFIRMADO)
```

**Motivos**:
- Cumple las tres clarificaciones sin casos especiales: primer mes abonado (`1 +`), extensión desde el vencimiento anterior aunque el pago sea tardío (la suma no depende de la fecha de pago) y anulación que recalcula sola (el pago anulado deja de sumar).
- No hay estado duplicado que se desincronice ni migración de datos para los vínculos activos existentes.
- Pocas filas por entrenador; el costo de calcular es despreciable.

**Alternativas descartadas**: (a) tabla de suscripción con `due_date` persistido y actualizado en cada pago o anulación: duplica la verdad y obliga a "deshacer" extensiones al anular; (b) `due_date` en `training_relationships`: el mismo problema, más una columna migrada.

**Impacto en la spec**: la entidad `MembershipSubscription` de la spec se materializa como un DTO calculado (`SubscriptionSummary`), no como una tabla. El estado `CANCELADA` lo aportará US-35 a partir del vínculo terminado.

## R2. Sumar meses sin desplazamiento de días

**Decisión**: `sumar_meses(fecha, n)` calcula siempre **desde `start_date`** con el total de meses y ajusta el día al último día del mes destino si no existe (31/01 + 1 → 28/02 o 29/02; 31/01 + 2 → 31/03). Se implementa con `calendar.monthrange` (librería estándar).

**Motivo**: encadenar extensiones mes a mes arrastra el recorte (31 → 28 → 28...). Calcular desde el inicio con el total conserva el día de facturación.

**Alternativa descartada**: `python-dateutil.relativedelta`. Da el mismo resultado, pero agrega una dependencia para una función de 6 líneas.

## R3. Estados y "hoy"

**Decisión**:
- `dias_restantes = vencimiento − hoy`.
- `VENCIDA` si `dias_restantes < 0`; `POR_VENCER` si `0 ≤ dias_restantes ≤ 5`; `AL_DIA` si `dias_restantes > 5`.
- "Hoy" es la fecha local del entrenador, enviada por el cliente en el parámetro `date` (mismo patrón que US-22). Sin el parámetro se usa `date.today()` del servidor.

**Motivo**: con UTC puro, un entrenador en Argentina (UTC−3) vería el cambio de estado a las 21:00. El cálculo de "hoy" se hace en el cliente porque no hay zona horaria guardada por usuario.

## R4. Inmutabilidad y anulación con reemisión

**Decisión**: una sola tabla, `informal_payments`.
- **Anular** completa `status = ANULADO`, `voided_at`, `voided_by_user_id` y `void_reason` (obligatorio, de 5 a 500 caracteres). Un `CHECK` garantiza que un pago `ANULADO` tenga esos tres campos y que un pago no anulado no los tenga.
- **Reemitir** es registrar un pago nuevo con `replaces_payment_id` apuntando al anulado, que debe ser del mismo vínculo y estar `ANULADO`. Un `UNIQUE` sobre `replaces_payment_id` impide reemplazarlo dos veces.
- **Sin borrado**: no hay endpoint DELETE y un listener `before_delete` del ORM lanza una excepción. La FK `relationship_id` no tiene `ON DELETE CASCADE`, así que borrar un vínculo con pagos falla en la base.

**Motivo**: los campos de la entidad `PaymentCorrectionAudit` de la spec (motivo, usuario, fecha y el vínculo entre el pago anulado y el nuevo) quedan completos en las dos filas involucradas, sin una tabla puente.

**Alternativa descartada**: una tabla `payment_correction_audits` aparte. Agrega una tercera escritura transaccional sin aportar datos nuevos.

**Flujo de interfaz**: "Anular" pide el motivo y, al confirmar, ofrece "Registrar pago corregido", que abre el formulario precargado con los datos del pago anulado y `replaces_payment_id`. Son dos llamadas; si la segunda no se hace, queda un pago anulado sin reemplazo, que es un estado válido.

## R5. Validación del formulario (escenario 3)

**Decisión**: validación en el backend con Pydantic (fuente de verdad) y la misma validación en el cliente para dar feedback inmediato.

| Campo | Regla | Mensaje |
|---|---|---|
| `paid_on` | obligatorio; no posterior a "hoy" | "Ingresá la fecha del pago." / "La fecha del pago no puede ser futura." |
| `amount` | obligatorio; > 0; ≤ 9.999.999,99; 2 decimales | "Ingresá el monto del pago." / "El monto debe ser mayor a cero." |
| `method` | `EFECTIVO`, `TRANSFERENCIA` u `OTRO` | "Elegí el medio de pago." |
| `months_covered` | entero de 1 a 12 | "El período debe ser de 1 a 12 meses." |
| `note` | opcional; ≤ 500 caracteres | — |

Los errores salen como RFC 7807 con `errors[]` por campo (handler existente en `api/errors.py`). Se marcan todos los campos faltantes a la vez.

## R6. Moneda y monto sugerido

**Decisión**: `currency` se copia de `relationship.agreed_currency` y no se edita. El cliente precarga `amount = agreed_monthly_price × months_covered` y el entrenador puede cambiarlo (descuentos, pagos parciales acordados). El backend no exige que el monto coincida con la tarifa.

## R7. Estados reservados para US-71

**Decisión**: el `CHECK` de `status` admite `PENDIENTE_CONFIRMACION`, `CONFIRMADO`, `RECHAZADO` y `ANULADO` desde ahora, pero US-34 solo crea `CONFIRMADO` y solo anula. Solo `CONFIRMADO` suma meses. US-71 agrega `reported_by`, `confirmed_by` y `receipt` sin tocar el `CHECK`.

**Motivo**: evita una migración de constraint en una tabla recién creada. El historial de US-34 ya muestra "Cargado por" y US-71 sumará "Confirmado por".
