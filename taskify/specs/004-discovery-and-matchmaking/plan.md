# Implementation Plan: Búsqueda de Entrenadores, Perfiles Públicos y Solicitudes de Alta

**Branch**: `004-discovery-and-matchmaking` | **Date**: 2026-10-15 | **Spec**: [specs/004-discovery-and-matchmaking/spec.md](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/taskify/specs/004-discovery-and-matchmaking/spec.md)

**Input**: Feature specification from `/specs/004-discovery-and-matchmaking/spec.md` (US-44, US-46, US-47, US-48, US-06, US-07, US-49)

## Summary

Implementar el buscador y catálogo público de entrenadores con filtros multifactor (especialidad, precio, disponibilidad de cupos), la selección de paquete de entrenamiento, el ciclo de vida transaccional de solicitudes de alta (`PENDING`, `ACCEPTED`, `REJECTED`, `CANCELLED`), la vinculación alumno-entrenador (`TrainingRelationship`), y la política de cupos agotados (Alternativa A: solicitudes previas permanecen en bandeja con acción 'Aceptar' inhabilitada hasta liberar cupo).

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0
- Frontend: React 18, React Router v6, Tailwind CSS, Lucide React

**Storage**: PostgreSQL 16 / SQLite (tests y CI)

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$) con escenarios de concurrencia y límites de cupo

**Target Platform**: Linux Server / Web responsive

**Project Type**: Servicio web y aplicación cliente

**Performance Goals**:
- Búsqueda de entrenadores con filtros < 100ms
- Transición de solicitud y creación de relación < 150ms bajo bloqueo transaccional

**Constraints**:
- Al alcanzar `active_students >= max_students`, se bloquean nuevas solicitudes y la acción de aceptación sobre pendientes (US-04, US-07 Alternativa A).
- Visualización de datos de salud permitida al entrenador durante la evaluación de solicitud PENDING; revocada inmediatamente si es rechazada o cancelada (Principio III).
- Creación de vínculo activo `TrainingRelationship` al aceptar la solicitud.

**Scale/Scope**: Módulo central de interacción comercial y vinculación para el MVP.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Accesibilidad | PASSED | Tarjetas de entrenadores con badges claros de disponibilidad y botones de acción accesibles. |
| II. IA Asistiva | N/A | No involucra IA en matchmaking. |
| III. Privacidad y Datos de Salud | PASSED | Acceso a salud restringido a solicitud PENDING o relación ACTIVE; revocación inmediata ante rechazo o cancelación. |
| IV. Pagos Informales | PASSED | Asociación del paquete de entrenamiento sin cobro automático por pasarela. |
| V. Gestión de Medios | N/A | No almacena videos. |
| VI. Calidad y Verificación Continua | PASSED | Pruebas de integración sobre transiciones de estado de solicitudes y cupos en CI. |

## Project Structure

### Documentation (this feature)

```text
specs/004-discovery-and-matchmaking/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de patrones transaccionales y búsqueda (Phase 0)
├── data-model.md        # Definición de entidades, restricciones y estados (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
└── contracts/
    └── matchmaking-api.yaml # Especificación OpenAPI 3.0 para búsqueda y solicitudes
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── discovery.py     # Endpoints: /trainers (búsqueda y perfil público)
│   │       └── requests.py      # Endpoints: /matchmaking/requests (solicitudes, aceptar, rechazar, cancelar)
│   ├── models/
│   │   ├── training_request.py
│   │   └── training_relationship.py
│   ├── schemas/
│   │   └── matchmaking.py
│   └── services/
│       └── matchmaking_service.py # Lógica de asignación, bloqueo de cupos y notificaciones
└── tests/
    ├── unit/
    │   └── test_matchmaking_service.py
    └── integration/
        └── test_matchmaking_api.py

frontend/
├── src/
│   ├── pages/
│   │   ├── TrainerSearchPage.tsx
│   │   ├── TrainerPublicDetailPage.tsx
│   │   └── TrainerRequestsInboxPage.tsx
│   ├── components/
│   │   └── RequestActionModal.tsx
│   └── services/
│       └── matchmakingService.ts
```

**Structure Decision**: Submódulo `matchmaking` desacoplado que coordina entre `trainers` y `students`.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
