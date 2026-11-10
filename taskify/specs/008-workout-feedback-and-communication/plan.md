# Implementation Plan: Resumen de Sesión (US-63) y Devolución sobre el Esfuerzo (US-64)

**Branch**: `feature/063-us63-session-summary` (US-63) y `feature/064-us64-effort-feedback` (US-64) | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `taskify/specs/008-workout-feedback-and-communication/spec.md`

**Alcance de este plan**: US-63 y US-64. US-60 ya está mergeada (PR #48); US-61 y US-62 quedan fuera y tendrán su propio plan.

## Summary

- **US-63**: endpoint de solo lectura que calcula el resumen de una sesión finalizada del alumno (tonelaje, duración, series completadas vs programadas, PRs logrados en la sesión y comparación contra el promedio histórico del mismo día de rutina) y un diálogo en el frontend que lo muestra al finalizar el entrenamiento. No requiere cambios de esquema.
- **US-64**: nueva entidad `EffortFeedback` (una por sesión con RPE), endpoint de alta/edición para el entrenador con notificación al alumno, endpoints de historial y "marcar vista" para el alumno, formulario en el panel del entrenador y aviso + historial en la vista del alumno.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript + React 18 + Vite (frontend, Node 20)
**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic v2; axios, react-router, lucide-react
**Storage**: PostgreSQL (prod) / SQLite (tests y local) vía SQLAlchemy `create_all` + `backend/src/core/migrations.py`
**Testing**: pytest con `TestClient` (`client` fixture), cobertura ≥ 90 %; `npm run build`
**Target Platform**: web responsiva (mobile-first durante el entrenamiento)
**Project Type**: web application (backend + frontend)
**Performance Goals**: resumen calculado en una sola request (< 300 ms con historial típico de < 200 sesiones)
**Constraints**: errores RFC 7807; fechas UTC ISO 8601; autorización en servidor por relación activa
**Scale/Scope**: 1 endpoint + 1 componente (US-63); 1 tabla + 3 endpoints + 2 componentes (US-64)

## Constitution Check

| Principio | Cumplimiento |
|-----------|--------------|
| I. Accesibilidad | Diálogo con `role="dialog"`, `aria-modal`, foco en botón principal, botones ≥ 44 px, textos con contraste AA. Resumen visible sin pasos extra. |
| II. IA | No aplica. |
| III. Privacidad | El resumen solo lo consulta el alumno dueño de la sesión. La devolución solo la crea el entrenador con vínculo `ACTIVE` y solo la lee el alumno de la sesión. Validación siempre en backend. |
| IV. Pagos | No aplica. |
| V. Medios | No aplica. |
| VI. Calidad | Tests de API por story (`test_us63_session_summary_api.py`, `test_us64_effort_feedback_api.py`), Ruff, build. |
| VII. Incremental | Una story por PR. US-63 y US-64 son independientes entre sí; ambas dependen solo de US-60 (mergeada). El escenario 3 de US-63 se difiere hasta US-67/68. |
| Reglas transversales | Errores vía `RoutineTemplateError` → RFC 7807; timestamps `utc_now()`. |

**Resultado**: PASS, sin violaciones.

## Project Structure

### Documentation (this feature)

```text
taskify/specs/008-workout-feedback-and-communication/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── session-summary-api.yaml      # US-63
│   └── effort-feedback-api.yaml      # US-64
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/src/
├── services/session_summary_service.py      # US-63 (nuevo)
├── services/effort_feedback_service.py      # US-64 (nuevo)
├── models/effort_feedback.py                # US-64 (nuevo)
├── schemas/routine_template.py              # US-63/64: schemas de respuesta
└── api/v1/routine_templates.py              # US-63/64: endpoints
backend/tests/
├── test_us63_session_summary_api.py
└── test_us64_effort_feedback_api.py
frontend/src/
├── components/SessionSummaryDialog.tsx      # US-63
├── components/EffortFeedbackForm.tsx        # US-64 (entrenador)
├── components/EffortFeedbackList.tsx        # US-64 (alumno)
├── pages/StudentRoutinesPage.tsx
├── components/RoutineAssignmentPanel.tsx
├── services/routineTemplateService.ts
└── types/routineTemplate.ts
```

**Structure Decision**: se reutiliza el módulo `routine_templates` (routers `router` y `student_router`), que ya expone sesiones y logs (US-59/60). La lógica nueva va en servicios propios para no seguir creciendo `routine_template_service.py`.

## Complexity Tracking

Sin violaciones que justificar.
