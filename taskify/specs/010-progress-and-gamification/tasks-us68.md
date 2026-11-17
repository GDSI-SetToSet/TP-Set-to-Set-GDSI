---
description: "Lista de tareas de US-68 de la feature 010"
---

# Tasks: US-68 — Racha de constancia de entrenamiento

**Entrada**: `spec.md` (Session 2026-11-17 — US-68), `plan-us68.md`. **Alcance**: solo US-68. PR hacia `sprint6`.

- [X] T001 [US68] `backend/src/services/streak_service.py`: cálculo puro (`compute_streak(weekly_target, first_week, done_by_week, current_monday)`) y armado para un vínculo (sesiones finalizadas, objetivo semanal de `_weekly_trainings`).
- [X] T002 [US68] Esquema `TrainingStreak` en `backend/src/schemas/student_progress.py`; rutas `GET /api/v1/students/me/streak` (con la notificación `STREAK_RESET` única) y `GET /api/v1/trainers/me/students/{student_id}/streak`.
- [X] T003 [US68] `backend/tests/test_us68_training_streak.py`: unitarias del cálculo (semanas cumplidas, corte, máxima, semana en curso, semanas sin sesiones, antes de la asignación) e integración (sin rutina, notificación única, entrenador, autorización).
- [X] T004 [P] [US68] Tipos y servicio en el frontend (`types/studentProgress.ts`, `services/studentProgressService.ts`, `services/trainerStudentService.ts`).
- [X] T005 [US68] Componente `StreakBadge`/`StreakCard`; inicio del alumno (acceso "Rutina del día"), "Mi evolución" y `TrainerStudentDetail`; `STREAK_RESET` en `studentNotificationPath`.
- [X] T006 `ruff check backend`, `pytest --cov=backend/src`, `npm run build`; recorrido en el navegador; commit y PR hacia `sprint6`.
