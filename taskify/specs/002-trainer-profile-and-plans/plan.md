# Implementation Plan: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Branch**: `002-trainer-profile-and-plans` | **Date**: 2026-10-15 | **Spec**: [specs/002-trainer-profile-and-plans/spec.md](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/taskify/specs/002-trainer-profile-and-plans/spec.md)

**Input**: Feature specification from `/specs/002-trainer-profile-and-plans/spec.md` (US-02, US-03, US-04)

## Summary

Implementar el módulo de configuración de perfil profesional de entrenadores, publicación y edición de planes de entrenamiento con tarifas mensuales, y administración de cupos máximos de alumnos (0 a 100). Incluye la regla de negocio acordada para cupos agotados (Alternativa A: solicitudes pendientes permanecen en bandeja con acción 'Aceptar' inhabilitada hasta liberar cupo).

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0
- Frontend: React 18, React Router v6, Tailwind CSS, Lucide React

**Storage**: PostgreSQL 16 (producción/referencia) / SQLite (tests unitarios y CI)

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$) en backend; Jest / React Testing Library en frontend

**Target Platform**: Linux Server / Web responsive

**Project Type**: Servicio web y frontend web application

**Performance Goals**:
- Consulta pública de perfil de entrenador < 100ms
- Actualización de cupo y disponibilidad de paquetes < 150ms

**Constraints**:
- Rango de cupos permitidos: 0 a 100 (US-04). Valor por defecto: 0.
- Rango de tarifas por paquete: 0 a 1.000.000 ARS (US-03). Moneda por defecto: ARS.
- Campos obligatorios de perfil: contacto y especialidad (US-02); sin ellos el perfil queda en DRAFT (no visible). Teléfono: `+` opcional y 8 a 15 dígitos.
- No retroactividad de tarifas: editar o archivar un paquete aplica solo a solicitudes futuras.
- Errores de la API en formato RFC 7807 (Constitución v1.1.0).
- Bloqueo de aceptación de solicitudes al tener cupos agotados (Decisión Alternativa A).

**Scale/Scope**: Entrenadores registrados configurando su oferta comercial y capacidad operativa en el MVP.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Enfoque en el Usuario y Accesibilidad | PASSED | Formularios de edición con validaciones claras, badges de estado de cupos con alto contraste. |
| II. IA Asistiva | N/A | No interactúa con IA. |
| III. Privacidad y Datos de Salud | PASSED | Los datos del perfil del entrenador son de acceso público, no contienen datos médicos de alumnos. |
| IV. Pagos Informales | PASSED | Define precios de referencia mensuales sin pasarela integrada. |
| V. Gestión de Medios | N/A | No gestiona videos. |
| VI. Calidad y Verificación Continua | PASSED | Pruebas de límites en cupos (0-100) y tarifas, cobertura $\ge 90\%$. |

## Project Structure

### Documentation (this feature)

```text
specs/002-trainer-profile-and-plans/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de alternativas técnicas (Phase 0)
├── data-model.md        # Definición de entidades, restricciones y estados (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
└── contracts/
    └── trainer-api.yaml # Especificación OpenAPI 3.0 para perfil, planes y cupos
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── trainers.py      # Endpoints: /trainers/me/profile, /trainers/me/plans, /trainers/me/quota
│   ├── models/
│   │   ├── trainer_profile.py   # Entidad TrainerProfile
│   │   └── training_plan.py     # Entidad TrainingPlan
│   ├── schemas/
│   │   └── trainer.py           # Schemas Pydantic (ProfileUpdate, PlanCreate, QuotaUpdate)
│   └── services/
│       └── trainer_service.py   # Lógica de cálculo de cupos, validaciones y planes
└── tests/
    ├── unit/
    │   └── test_trainer_service.py
    └── integration/
        └── test_trainer_api.py

frontend/
├── src/
│   ├── pages/
│   │   ├── TrainerProfileEditPage.tsx
│   │   └── TrainerPlansManagementPage.tsx
│   ├── components/
│   │   ├── QuotaBadge.tsx
│   │   └── PlanCard.tsx
│   └── services/
│       └── trainerService.ts
```

**Structure Decision**: Módulo de dominio `trainers` integrado con la arquitectura modular estándar.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
