# Quickstart de validación: US-34

## Prerrequisitos
- Backend: `pip install -r backend/requirements.txt`; frontend: `cd frontend && npm ci`.
- Datos: un entrenador con al menos tres alumnos activos (flujo de US-48 → US-07). `python backend/scripts/seed_demo.py --reset` deja a Tomás Castro (entrenador Gonzalo Morales) con un pago anulado y su corrección. Para ver los tres estados a la vez hace falta cambiar la fecha de inicio de los vínculos en una base de prueba, hasta que exista el script de demo del Sprint 6.

## Automatizado
```bash
pytest backend/tests/test_us34_subscription_service.py backend/tests/test_us34_informal_payments_api.py
ruff check backend && pytest --cov=backend/src           # cobertura ≥ 90 %
cd frontend && npm run build
```
Esperado: todo verde.

## Manual (escenarios de aceptación de la spec)
1. Iniciar sesión como entrenador → tarjeta "Suscripciones" (`/entrenador/suscripciones`). Se ven todos los alumnos activos con paquete, vencimiento y estado "Al día", "Por vencer" o "Vencida"; las vencidas primero (escenario 1).
2. Un alumno aceptado hoy figura "Al día" con vencimiento dentro de un mes (clarificación: primer mes abonado).
3. "Registrar pago" en un alumno vencido: fecha de hoy, 1 mes, monto precargado con la tarifa acordada, medio "Transferencia" → confirmar. El vencimiento avanza **un mes desde el vencimiento anterior** (no desde hoy) y el estado se actualiza (escenario 2).
4. Abrir el formulario, borrar la fecha y el monto → confirmar: no se registra y ambos campos muestran su mensaje (escenario 3). Repetir con una fecha futura: se rechaza.
5. Abrir el historial del alumno: se ven todos los pagos con fecha, monto, medio, meses y "Cargado por". No hay opción de eliminar (escenario 5).
6. "Anular" un pago sin motivo → no se permite. Con motivo → el pago queda tachado como "Anulado" con motivo, fecha y usuario, y el vencimiento retrocede (escenario 5).
7. Tras anular, "Registrar pago corregido": el formulario viene precargado; al confirmar, el pago nuevo muestra "Corrige al pago del dd/mm" y el anulado muestra "Reemplazado por…". Intentar reemplazar dos veces el mismo pago → error (escenario 6).
8. Desde el detalle de un alumno en "Mis alumnos", el enlace "Pagos y vencimiento" abre su historial.
9. Con un token de alumno, `GET /api/v1/trainers/me/subscriptions` → 403 `application/problem+json`. Con otro entrenador, el historial del alumno → 404.

Contrato: [contracts/informal-payments-api.yaml](./contracts/informal-payments-api.yaml). Modelo: [data-model.md](./data-model.md).
