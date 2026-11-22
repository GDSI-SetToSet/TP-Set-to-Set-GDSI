---
description: "Lista de tareas de US-67 de la feature 010"
---

# Tasks: US-67 — Desbloqueo de logros y medallas

**Entrada**: `spec.md` (Session 2026-11-17 — US-67), `plan-us67.md`. **Alcance**: solo US-67. PR hacia `sprint6` (sobre US-68).

- [X] T001 [US67] Modelos `StudentAchievement` y `AchievementCongratulation` (`backend/src/models/achievement.py`); prueba de creación idempotente de las tablas en `test_database_migrations.py`.
- [X] T002 [US67] `streak_service`: `relationship_week_data` (refactor sin cambio de comportamiento) y `streak_reached_on`.
- [X] T003 [US67] `backend/src/services/achievement_service.py`: catálogo, fechas reales, evaluación (nuevos vs retroactivos), notificaciones, celebración y felicitación; gancho en `finish_student_workout_session`.
- [X] T004 [US67] Esquemas (`backend/src/schemas/achievement.py`) y rutas (`backend/src/api/v1/achievements.py`).
- [X] T005 [US67] `backend/tests/test_us67_achievements_api.py`: cada hito, retroactivos con fecha real, celebración, racha de 4 semanas, felicitación única, validación, autorización y vínculo terminado.
- [X] T006 [US67] Frontend: `AchievementCelebration` en `SessionSummaryDialog`, `AchievementsSection` en "Mi evolución", `CongratulationBanner` en la sesión, `TrainerAchievements` en el detalle del alumno, ruteo de notificaciones.
- [X] T007 `ruff check backend`, `pytest --cov=backend/src`, `npm run build`; recorrido en el navegador de los 4 escenarios; commit y PR hacia `sprint6`.
