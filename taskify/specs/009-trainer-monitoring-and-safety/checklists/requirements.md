# Lista de verificación de calidad de la especificación: US-18 — Visualización de alumnos activos

**Propósito**: validar el alcance exclusivo de US-18 antes de la implementación.
**Feature**: [spec.md](../spec.md)

- [x] El alcance de US-18 está aislado de las demás historias de la feature 009.
- [x] Los escenarios de aceptación 1–3 son explícitos y comprobables.
- [x] El escenario de ordenamiento de alertas está identificado como dependencia de US-29.
- [x] Se reutiliza el comportamiento existente de listado, rutinas, progreso, reportes y zonas protegidas.
- [x] La autorización del lado del servidor requiere un vínculo activo entre entrenador y alumno.
- [x] Los datos del paquete utilizan el precio acordado del vínculo en lugar del precio actual del catálogo.
- [x] Las métricas están limitadas a un resumen compacto de actividad y no absorben US-24 ni US-30.
- [x] Están definidos los casos de estado vacío, ausencia de rutina, ausencia de actividad, acceso prohibido y vínculo terminado.
- [x] Están presentes el contrato de API, el modelo de datos, el inicio rápido y las tareas de implementación.
- [x] Cada tarea de implementación está etiquetada con `[US18]` y tiene una ruta explícita.

## Notas

Esta lista de verificación está limitada al incremento actual de US-18. No certifica las demás historias agrupadas en la feature 009.
