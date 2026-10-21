# Implementation Plan: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Branch**: `005-exercise-library-and-templates` | **Date**: 2026-10-15 | **Spec**: [specs/005-exercise-library-and-templates/spec.md](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/taskify/specs/005-exercise-library-and-templates/spec.md)

**Input**: Feature specification from `/specs/005-exercise-library-and-templates/spec.md` (US-08, US-09, US-12, US-52)

## Summary

Implementar la gestión de la biblioteca de ejercicios (ejercicios del sistema y personalizados del entrenador), notas técnicas y pautas de respiración (US-52), vinculación estricta de videos demostrativos mediante URLs de plataformas externas soportadas (YouTube, Vimeo, Google Drive; Principio V, US-12), y diseño de plantillas de rutinas genéricas (US-09).

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0
- Frontend: React 18, React Router v6, Tailwind CSS, Lucide React

**Storage**: PostgreSQL 16 / SQLite (tests unitarios y CI)

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$) incluyendo validadores regex de URLs de video

**Target Platform**: Linux Server / Web responsive

**Project Type**: Servicio web y módulo de interfaz

**Performance Goals**:
- Búsqueda y filtrado de ejercicios por grupo muscular < 80ms
- Validación y persistencia de enlaces de video < 100ms

**Constraints**:
- Prohibición absoluta de carga o transcodificación de archivos de video binarios en el servidor (Principio V).
- Validación de URLs mediante expresiones regulares estrictas (solo dominios soportados: YouTube, Vimeo, Google Drive).
- 4 campos obligatorios para dar de alta un ejercicio: nombre, descripción, músculo a trabajar y equipamiento/materiales (US-08).

**Scale/Scope**: Biblioteca de cientos de ejercicios y plantillas disponibles para todos los entrenadores.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Accesibilidad | PASSED | Visualización clara de notas técnicas y pautas de postura en tipografía legible. |
| II. IA Asistiva | N/A | Los ejercicios servirán como catálogo fuente para el generador de rutinas. |
| III. Privacidad y Datos de Salud | PASSED | La biblioteca es técnica y pública para alumnos asignados, sin datos sensibles. |
| IV. Pagos Informales | N/A | No procesa pagos. |
| V. Gestión Liviana de Medios Técnicos | PASSED | Cumplimiento total: solo enlaces externos a plataformas soportadas (US-12). |
| VI. Calidad y Verificación Continua | PASSED | Cobertura $\ge 90\%$ con pruebas unitarias sobre analizadores de URL de video. |

## Project Structure

### Documentation (this feature)

```text
specs/005-exercise-library-and-templates/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de validación de URLs y reproductores embebidos (Phase 0)
├── data-model.md        # Definición de entidades, restricciones y estados (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
└── contracts/
    └── exercise-library-api.yaml # Especificación OpenAPI 3.0 para ejercicios y plantillas
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── exercises.py     # Endpoints: /exercises (CRUD, filtros)
│   │       └── templates.py     # Endpoints: /routine-templates (CRUD plantillas)
│   ├── core/
│   │   └── media_validator.py# Validador regex de URLs de YouTube, Vimeo y Google Drive
│   ├── models/
│   │   ├── exercise.py
│   │   └── routine_template.py
│   ├── schemas/
│   │   ├── exercise.py
│   │   └── routine_template.py
│   └── services/
│       ├── exercise_service.py
│       └── template_service.py
└── tests/
    ├── unit/
    │   └── test_media_validator.py
    └── integration/
        └── test_exercise_api.py

frontend/
├── src/
│   ├── pages/
│   │   ├── ExerciseLibraryPage.tsx
│   │   └── RoutineTemplatesPage.tsx
│   ├── components/
│   │   ├── ExerciseCard.tsx
│   │   └── VideoEmbedModal.tsx
│   └── services/
│       └── exerciseService.ts
```

**Structure Decision**: Módulos `exercises` y `templates` integrados al dominio central de entrenamiento.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
