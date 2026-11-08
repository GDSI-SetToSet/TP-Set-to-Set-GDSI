# Implementation Plan: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Branch**: `005-exercise-library-and-templates` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-exercise-library-and-templates/spec.md` (US-08, US-09, US-12, US-52)

## Summary

La biblioteca personal de ejercicios (US-08), las rutinas genéricas (US-09) y los videos demostrativos (US-12) están implementados. US-52 completa la ficha del ejercicio con notas técnicas y claves de respiración opcionales, administradas por el entrenador y visibles para el alumno dentro de la rutina asignada.

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0
- Frontend: React 18, React Router v6, CSS propio (`frontend/src/styles/`), Lucide React

**Storage**: PostgreSQL 16 / SQLite (tests unitarios y CI). Tablas creadas con `Base.metadata.create_all`, sin migraciones.

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$)

**Target Platform**: Linux Server / Web responsive

**Project Type**: Servicio web y módulo de interfaz

**Performance Goals**:
- Búsqueda y filtrado de ejercicios por grupo muscular < 80ms

**Constraints**:
- 5 campos obligatorios para dar de alta un ejercicio: nombre, descripción, categoría, músculo a trabajar y equipamiento/materiales (US-08).
- Baja lógica de ejercicios para preservar las rutinas que los incluyen.
- Errores RFC 7807 con `errors[]` por campo.
- Prohibición absoluta de carga o transcodificación de archivos de video binarios en el servidor (Principio V).

**Scale/Scope**: Biblioteca de cientos de ejercicios y rutinas por entrenador. Rutinas de hasta 7 días, 10 bloques por día y 30 ejercicios por bloque.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Accesibilidad | PASSED | Controles de 44 × 44 px, contraste de la paleta existente y mensajes de error por campo. |
| II. IA Asistiva | N/A | Los ejercicios servirán como catálogo fuente para la spec 006. |
| III. Privacidad y Datos de Salud | PASSED | No hay datos de salud. El vínculo activo se valida en el backend en cada petición del alumno. |
| IV. Pagos Informales | N/A | No procesa pagos. |
| V. Gestión Liviana de Medios Técnicos | PASSED | US-12 acepta enlaces externos de video y no carga ni transcodifica archivos binarios en el servidor. |
| VI. Calidad y Verificación Continua | PASSED | Pruebas de integración por story, cobertura $\ge 90\%$, Ruff y build. |
| VII. Entrega Incremental | PASSED | Un PR por story. US-09 parte de `develop` con US-08 ya mergeada. |

## Project Structure

### Documentation (this feature)

```text
specs/005-exercise-library-and-templates/
├── plan.md              # Este plan de implementación
├── research.md          # Decisiones técnicas (Phase 0)
├── data-model.md        # Definición de entidades y restricciones (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
├── tasks.md             # Tareas de US-08 y US-09
├── checklists/
│   └── requirements.md  # Control de calidad de la spec
└── contracts/
    └── exercise-library-api.yaml # Especificación OpenAPI 3.0
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/v1/
│   │   ├── exercises.py          # US-08: /exercises
│   │   └── routine_templates.py  # US-09: /routine-templates y /students/me/routine-templates
│   ├── models/
│   │   ├── exercise.py
│   │   └── routine_template.py
│   ├── schemas/
│   │   ├── exercise.py
│   │   └── routine_template.py
│   └── services/
│       ├── exercise_service.py
│       └── routine_template_service.py
└── tests/
    ├── test_exercise_api.py
    └── test_routine_template_api.py

frontend/
└── src/
    ├── components/
    │   ├── ExerciseCard.tsx
    │   ├── RoutineTemplateCard.tsx
    │   └── RoutineTemplateDetail.tsx
    ├── pages/
    │   ├── ExerciseLibraryPage.tsx
    │   ├── RoutineTemplatesPage.tsx
    │   └── StudentRoutinesPage.tsx
    ├── services/
    │   ├── exerciseService.ts
    │   └── routineTemplateService.ts
    ├── styles/
    │   ├── exercise-library.css
    │   └── routine-templates.css
    └── types/
        ├── exercise.ts
        └── routineTemplate.ts
```

**Structure Decision**: Módulos `exercises` y `routine_templates` con la misma separación API, servicio, schema y modelo del resto del backend. Las pruebas siguen la convención plana de `backend/tests/`.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
