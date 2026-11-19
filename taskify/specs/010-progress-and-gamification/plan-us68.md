# Plan de implementación: US-68 — Racha de constancia de entrenamiento

**Branch**: `feature/us-68-training-streak` (desde `sprint6`; PR hacia `sprint6`) | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md) (Session 2026-11-17 — US-68)

**Alcance**: escenarios 1–4 de US-68. Fuera de alcance: US-67 (logros) y el escenario 3 de US-63 (racha en el resumen de sesión), que sigue diferido.

## Resumen

La racha **se calcula, no se guarda**: sale de las sesiones finalizadas del vínculo con rutina asignada y del objetivo semanal, que son los días de la rutina vigente (`abandonment_risk_service._weekly_trainings`, el criterio de US-30 y US-32). Semanas de lunes a domingo en UTC, contadas desde la asignación de la rutina.

- **Semana cumplida**: sesiones finalizadas ≥ objetivo semanal.
- **Racha actual**: semanas cumplidas consecutivas que terminan en la última semana terminada.
- **Racha máxima**: la serie más larga del historial.
- **Semana en curso**: avance `n de objetivo`; nunca suma ni corta hasta terminar.
- **Mensaje de aliento** (escenario 2): al pedir la racha, si la última semana terminada no se cumplió y la anterior sí, se crea una notificación `STREAK_RESET`. No se repite gracias a `related_entity_id` = lunes de la semana que cortó la racha.

## API

- `GET /api/v1/students/me/streak` → `{has_routine, weekly_target, current_weeks, max_weeks, this_week_sessions, week_start}` (genera el mensaje de aliento si corresponde).
- `GET /api/v1/trainers/me/students/{student_id}/streak` → lo mismo para el alumno con vínculo activo (404 si no lo es).

## Frontend

- Inicio del alumno: el acceso "Rutina del día" muestra "Racha: N semanas · n de M esta semana" (escenario 4).
- "Mi evolución": tarjeta con la racha actual, la máxima y el avance de la semana (escenario 3).
- Entrenador: en el detalle del alumno, un bloque con la racha actual y la máxima (escenario 3).
- `STREAK_RESET` lleva a "Rutina del día".

## Verificación de la Constitución

I (texto además de íconos; contraste) PASS · III (el entrenador solo ve a sus alumnos activos) PASS · VI (pruebas de semanas cumplidas, no cumplidas, en curso, sin rutina, notificación única) PASS · VII (una story, un PR hacia `sprint6`) PASS.
