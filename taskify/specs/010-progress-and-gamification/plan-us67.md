# Plan de implementación: US-67 — Desbloqueo de logros y medallas

**Branch**: `feature/us-67-achievements` (desde `feature/us-68-training-streak`; PR hacia `sprint6`) | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md) (Session 2026-11-17 — US-67)

**Alcance**: escenarios 1–4 de US-67. Depende de US-68 (PR #73) por "Racha de 4 semanas"; la rama parte de la de US-68 (excepción al Principio VII aceptada por el equipo).

## Resumen

Catálogo fijo de cinco logros, medidos sobre datos existentes:

| Código | Hito | Fecha real |
|---|---|---|
| `FIRST_SESSION` / `TEN_SESSIONS` | 1 / 10 sesiones finalizadas (todos los vínculos) | fin de la sesión N |
| `FIRST_PR` / `FIVE_PRS` | 1 / 5 récords (peso que supera estrictamente el máximo previo del ejercicio, US-65) | serie del récord N |
| `STREAK_4_WEEKS` | racha de US-68 de 4 semanas | lunes que sigue a la 4.ª semana cumplida (`streak_reached_on`) |

Los logros **se guardan** al desbloquearse (`student_achievements`, único por alumno y código), con su fecha real y sin perderse nunca. Se evalúan al finalizar una sesión (gancho en `finish_student_workout_session`, que nunca impide finalizar) y al consultar los logros (la racha se completa al terminar la semana).

**Nuevo o retroactivo**: es nuevo el hito alcanzado por la sesión que acaba de finalizar, o la racha completada esta semana. Celebra (queda pendiente hasta que el alumno cierra el resumen) y notifica (`ACHIEVEMENT_UNLOCKED` al alumno y a sus entrenadores activos). Lo cumplido antes se otorga en silencio, marcado como retroactivo.

**Felicitación** (`achievement_congratulations`, una por logro, hasta 300 caracteres): el entrenador la envía desde el detalle del alumno, el alumno recibe una notificación `CONGRATULATION` y la ve una sola vez como aviso al abrir su próxima sesión.

## API

Alumno: `GET /students/me/achievements` (desbloqueados con fecha + bloqueados con avance), `POST /students/me/achievements/{id}/celebrated`, `POST /students/me/achievements/{id}/congratulation/seen`.
Entrenador: `GET /trainers/me/students/{student_id}/achievements`, `POST /trainers/me/achievements/{id}/congratulation` (201; 409 si ya felicitó; 404 si no es su alumno activo).

## Frontend

Celebración dentro del resumen de la sesión finalizada (se reconoce al cerrar); sección "Mis logros" en "Mi evolución"; aviso de felicitación al abrir la sesión; logros y "Felicitar" en el detalle del alumno del entrenador; ruteo de `ACHIEVEMENT_UNLOCKED` y `CONGRATULATION`.

## Verificación de la Constitución

I (texto además de íconos; controles ≥ 44 px) PASS · III (el entrenador solo ve logros de alumnos activos) PASS · VI (pruebas de cada hito, retroactivos, celebración, felicitación y autorización) PASS · VII EXCEPCIÓN (rama sobre US-68 sin mergear).
