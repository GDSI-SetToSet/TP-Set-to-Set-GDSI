# Implementation Plan: Edición de Rutina según Objetivos y Limitaciones del Alumno (US-14)

**Branch**: `feature/us14` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)

**Input**: Spec 006, alcance de este plan: **solo US-14** (US-13, 53, 54 y 55 tienen sus propios planes/PR; Principio VII).

## Summary

El entrenador edita la rutina de un alumno en un **borrador por alumno**; el alumno sigue viendo la versión vigente hasta que el entrenador confirma. Hoy "asignar" solo guarda `initial_routine_id` apuntando a la plantilla compartida, por lo que se necesita una **copia por alumno** (`StudentRoutine`) creada al asignar o al primer edit. El borrador se valida al guardar (limitaciones físicas, bloqueo absoluto) y al confirmar ("Sin materiales"); cada confirmación genera un registro de cambios.

## Technical Context

**Language/Version**: Python 3.12 (backend) / TypeScript, Node.js 20 (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0; React 18, React Router v6

**Storage**: PostgreSQL 16 / SQLite (tests). Tablas con `Base.metadata.create_all`, sin migraciones.

**Testing**: Pytest + `pytest-cov` (≥ 90 %), Ruff, `npm run build`

**Target Platform**: Linux server / web responsive

**Project Type**: Servicio web + módulo de interfaz

**Performance Goals**: Guardar o confirmar una edición < 1 s para rutinas de hasta 7 días × 10 bloques × 30 ejercicios.

**Constraints**: Errores RFC 7807 con `errors[]`; autorización del vínculo activo validada en backend; fechas UTC ISO 8601.

**Scale/Scope**: Cientos de rutinas por entrenador; una versión vigente + un borrador por alumno.

## Constitution Check

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASSED | Controles ≥ 44×44 px, errores por campo y alertas legibles. |
| II. IA asistiva / Human-in-the-Loop | PASSED | Borradores IA (US-13) también pasan por confirmación manual; editar no activa nada solo. |
| III. Privacidad de salud | PASSED | Las zonas protegidas se leen en backend solo con vínculo ACTIVE entre entrenador y alumno; el alumno no ve el borrador. |
| IV. Pagos | N/A | — |
| V. Medios técnicos | N/A | — |
| VI. Calidad en CI | PASSED | Tests de servicio y API por escenario, cobertura ≥ 90 %. |
| VII. Entrega incremental | PASSED con dependencia | Un PR solo para US-14. Depende de US-09 (rutinas genéricas), ya mergeada. US-53 no está: ver research D4. |

Re-evaluación post-diseño: sin violaciones.

## Project Structure

### Documentation

```text
specs/006-routine-planning-and-adaptation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/student-routine-edit-api.yaml
```

### Source Code

```text
backend/src/
├── models/student_routine.py         # StudentRoutine (+ días/bloques/ejercicios), RoutineChangeLog
├── schemas/student_routine.py
├── services/student_routine_service.py   # borrador, validaciones, confirmación, auditoría
├── api/v1/student_routines.py        # /trainers/me/students/{id}/routine...
backend/tests/                        # unit + integration por escenario
frontend/src/                         # pantalla de edición de rutina del alumno
```

**Structure Decision**: Se reutiliza la estructura por capas existente (model / schema / service / router). Sin abstracciones nuevas.

## Complexity Tracking

Sin violaciones constitucionales a justificar.
