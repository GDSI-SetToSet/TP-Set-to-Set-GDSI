# Lista de verificación de calidad de la especificación: US-34 — Pagos y estado de suscripciones

**Propósito**: validar que US-34 está lista para implementarse (Definition of Ready).
**Feature**: [spec.md](../spec.md)

- [x] El alcance de US-34 está aislado de US-35 y US-71 (Clarificaciones 2026-11-16).
- [x] El escenario 4 (confirmar o rechazar un pago informado) se trasladó a US-71 y quedó registrado en ambas historias.
- [x] El primer vencimiento, la unidad del período y la regla del pago tardío están definidos sin ambigüedad.
- [x] Los umbrales de estado están definidos: "Por vencer" entre 0 y 5 días, "Vencida" desde el día siguiente al vencimiento, y "hoy" en fecha local.
- [x] Los escenarios 1, 2, 3, 5 y 6 son explícitos y comprobables con estructura Dado/Cuando/Entonces.
- [x] La inmutabilidad (sin borrado) y la anulación con motivo, fecha, usuario y reemisión referenciada cumplen el Principio IV.
- [x] La autorización del lado del servidor exige un vínculo activo entre entrenador y alumno.
- [x] Se usan la tarifa y la moneda acordadas del vínculo, no el precio actual del catálogo.
- [x] Están definidos los casos de estado vacío, campos faltantes, fecha futura, doble anulación, doble reemplazo, rol alumno y entrenador ajeno.
- [x] Están presentes el contrato de API, el modelo de datos, el research, el quickstart y las tareas de implementación.
- [x] Cada tarea de implementación está etiquetada con `[US34]` y tiene una ruta explícita.

## Notas

Esta lista de verificación está limitada a US-34. US-35 y US-71 tendrán su propia verificación cuando se planifiquen.
