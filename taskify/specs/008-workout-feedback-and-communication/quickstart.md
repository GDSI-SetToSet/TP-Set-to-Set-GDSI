# Quickstart: US-63 y US-64

## US-63 — Resumen de sesión
1. Como alumno con rutina asignada, iniciá el entrenamiento de un día y registrá algunas series con peso.
2. Finalizá la sesión (con o sin RPE). Se abre el diálogo "¡Felicitaciones!" con tonelaje, duración, series `completadas / programadas` y, si corresponde, los PRs destacados.
3. Repetí el mismo día con más peso: el resumen muestra la diferencia porcentual contra el promedio anterior. En la primera sesión del día indica "Primera sesión registrada de este día".
4. API: `GET /api/v1/students/me/routine-templates/assigned/workout-sessions/{id}/summary` (422 si la sesión no terminó, 404 si es de otro alumno).

## US-64 — Devolución sobre el esfuerzo
1. Como entrenador, abrí el panel del alumno y en una sesión con RPE elegí una categoría y (opcional) un comentario; guardá. El alumno recibe una notificación.
2. Como alumno, iniciá tu próxima sesión: se muestra la devolución y queda marcada como vista.
3. En "Devoluciones de tu entrenador" se ve el historial; sin devoluciones aparece "Todavía no recibiste devoluciones de tu entrenador".

## Verificación
```bash
ruff check backend
pytest backend/tests --cov=backend/src --cov-fail-under=90
cd frontend && npm run build
```
