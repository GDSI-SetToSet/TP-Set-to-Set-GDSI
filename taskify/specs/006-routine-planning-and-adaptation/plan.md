# Implementation Plan: Generación de Rutina Particular con IA (US-13)

**Branch**: `feature/006-us13-ai-routine-generation` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-routine-planning-and-adaptation/spec.md` (US-13)

## Summary

La User Story US-13 permite al entrenador crear una rutina personalizada para un alumno con vínculo activo, adaptando una rutina genérica de su biblioteca mediante IA en función de los objetivos y limitaciones (físicas o médicas) del alumno. La IA genera una propuesta (`PENDING_REVIEW`) que sustituye o elimina ejercicios incompatibles y ajusta volumen/intensidad; el entrenador revisa y aprueba explícitamente la propuesta (`APPROVED`) antes de que quede activada al alumno, conservando intacta la rutina genérica original.

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0, `httpx` (para adaptadores HTTP)
- Frontend: React 18, React Router v6, CSS propio (`frontend/src/styles/`), Lucide React

**Storage**: SQLite (entorno local, testing y CI) / PostgreSQL 16. Tablas creadas con `Base.metadata.create_all`.

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$)

**Target Platform**: Linux Server / Web responsive

**Scale/Scope**: Generación de rutinas particulares para alumnos activos de cada entrenador. Rutinas estructuradas en días, bloques y ejercicios.

## Constitution Check

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Accesibilidad | PASSED | Controles de 44 × 44 px, contraste conforme a WCAG 2.1 AA, flujo de revisión y aprobación claro. |
| II. IA Asistiva con Supervisión Humana Obligatoria | PASSED | Human-in-the-Loop obligatorio: la IA genera propuesta en `PENDING_REVIEW`; solo el entrenador la aprueba a `APPROVED`. Adaptador desacoplado `AIRoutineAdapter`. |
| III. Privacidad y Protección de Datos de Salud | PASSED | Validación server-side: solo el entrenador con `TrainingRelationship.status == 'ACTIVE'` puede generar la rutina y acceder a salud/objetivos. |
| IV. Pagos Informales | N/A | No procesa pagos. |
| V. Gestión Liviana de Medios Técnicos | PASSED | Reutiliza los ejercicios existentes de la biblioteca con enlaces externos sin subir archivos de video binarios. |
| VI. Calidad y Verificación Continua | PASSED | Pruebas de integración automatizadas para todos los criterios de aceptación, Ruff y build limpio de frontend. Cobertura $\ge 90\%$. |
| VII. Entrega Incremental | PASSED | Una sola user story (US-13) implementada en rama dedicada `feature/006-us13-ai-routine-generation` basada en `develop`. |

## Project Structure

### Documentation (this feature)

```text
taskify/specs/006-routine-planning-and-adaptation/
├── spec.md                   # Especificación funcional con clarificaciones y escenarios
├── plan.md                   # Este plan de implementación
├── research.md               # Decisiones de diseño y arquitectura del adaptador de IA
├── data-model.md             # Definición de AssignedRoutine y entidades relacionadas
├── quickstart.md             # Guía de verificación rápida
├── checklists/
│   └── requirements.md       # Control de calidad DoR de la spec
└── contracts/
    ├── routine-adaptation-api.yaml   # Contrato OpenAPI 3.0 para US-13
    └── student-routine-edit-api.yaml # Contrato OpenAPI 3.0 para US-14
```

### Source Code (US-13)

```text
backend/
├── src/
│   ├── api/v1/
│   │   ├── assigned_routines.py  # Endpoints de generación con IA, consulta y aprobación
│   │   └── trainers.py           # Endpoint de alumnos activos del entrenador
│   ├── models/
│   │   └── assigned_routine.py   # Modelos AssignedRoutine, Day, Block, Exercise
│   ├── schemas/
│   │   └── assigned_routine.py   # Schemas de request/response y validación
│   └── services/
│       ├── ai_routine_adapter.py # Interfaz desacoplada y adaptador de adaptación
│       └── assigned_routine_service.py # Lógica de negocio y persistencia
└── tests/
    └── test_ai_routine_api.py    # Suite de pruebas automatizadas de US-13

frontend/
└── src/
    ├── pages/
    │   └── GenerateAIRoutinePage.tsx # Selector de alumno/plantilla, vista previa y aprobación
    ├── services/
    │   └── assignedRoutineService.ts # Métodos de cliente HTTP
    ├── types/
    │   └── assignedRoutine.ts        # Definiciones TypeScript
    └── constants/
        └── routes.ts                 # Ruta /entrenador/rutinas/generar-ia
```

---

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

### Source Code (US-14)

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
