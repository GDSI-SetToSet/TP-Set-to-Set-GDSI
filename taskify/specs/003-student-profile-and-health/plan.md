# Implementation Plan: Perfil del Alumno, Cuestionario de Salud y Apto Médico

**Branch**: `003-student-profile-and-health` | **Date**: 2026-10-15 | **Spec**: [specs/003-student-profile-and-health/spec.md](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/taskify/specs/003-student-profile-and-health/spec.md)

**Input**: Feature specification from `/specs/003-student-profile-and-health/spec.md` (US-39, US-40, US-41, US-42, US-43)

## Summary

Implementar el perfil integral del alumno, incluyendo datos personales (US-39), objetivos deportivos (US-40), cuestionario inicial de salud PAR-Q (US-41), antecedentes de lesiones o zonas corporales a proteger (US-42), y carga protegida de certificados de apto físico/médico (US-43). Garantiza la custodia de datos sensibles mediante autorización estricta del lado del servidor (Principio III) y la preservación del historial cronológico de certificados médicos (Alternativa A: último archivo marcado como `CURRENT` y anteriores como `ARCHIVED`).

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0, python-multipart, aiofiles
- Frontend: React 18, React Router v6, Tailwind CSS, Lucide React

**Storage**: PostgreSQL 16 / SQLite (pruebas), Almacenamiento local de archivos en volumen protegido fuera de la raíz web pública (`uploads/medical_clearances/`)

**Testing**: Pytest con `pytest-cov` ($\ge 90\%$) en backend con fixtures de RBAC y streaming de archivos

**Target Platform**: Linux Server / Web responsive

**Project Type**: Servicio web y aplicación cliente

**Performance Goals**:
- Descarga segura de certificado < 300ms para archivos de hasta 10 MB
- Consulta de ficha médica autorizada < 120ms

**Constraints**:
- Almacenamiento privado de aptos médicos sin acceso anónimo directo (Principio III).
- Autorización en cada acceso en el backend: solo el alumno y el entrenador con vínculo activo o solicitud pendiente pueden acceder.
- Revocación inmediata al finalizar la relación (US-35).
- Formatos de apto permitidos: PDF, JPEG, PNG (máx 10 MB).
- Historial acumulativo de certificados médicos sin sobreescritura (Alternativa A).

**Scale/Scope**: Ficha médica y perfil deportivo para la totalidad de alumnos del MVP.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Accesibilidad | PASSED | Cuestionarios accesibles y directos; carga de archivos con soporte drag-and-drop accesible y mensajes de error claros. |
| II. IA Asistiva | PASSED | Las zonas protegidas quedan expuestas para que el módulo de IA (US-13) las consuma como restricciones excluyentes. |
| III. Privacidad y Datos de Salud | PASSED | Control de autorización del lado del servidor en cada endpoint; descarga protegida por streaming autenticado; revocación inmediata ante rescisión. |
| IV. Pagos Informales | N/A | No procesa pagos. |
| V. Gestión de Medios | N/A | No aloja videos binarios. |
| VI. Calidad y Verificación Continua | PASSED | Tests de seguridad que verifican 403 Forbidden cuando un entrenador ajeno intenta consultar certificados o datos médicos. |

## Project Structure

### Documentation (this feature)

```text
specs/003-student-profile-and-health/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de almacenamiento protegido y control de acceso (Phase 0)
├── data-model.md        # Definición de entidades, restricciones y estados (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
└── contracts/
    └── student-health-api.yaml # Especificación OpenAPI 3.0 para perfil, salud y aptos
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── students.py      # Endpoints: /students/me/profile, /students/{id}/goals, /health-questionnaire, /injuries
│   │       └── medical.py       # Endpoints: /students/{id}/medical-clearance (upload/download/history)
│   ├── core/
│   │   └── storage.py       # Servicio de almacenamiento protegido (StorageService interface)
│   ├── models/
│   │   ├── student_profile.py
│   │   ├── health_questionnaire.py
│   │   ├── injury_history.py
│   │   └── medical_clearance.py
│   ├── schemas/
│   │   └── student_health.py
│   └── services/
│       ├── student_service.py
│       └── medical_service.py   # Lógica de RBAC de salud y gestión de vigencia
└── tests/
    ├── unit/
    │   └── test_medical_service.py
    └── integration/
        └── test_student_health_api.py

frontend/
├── src/
│   ├── pages/
│   │   ├── StudentProfilePage.tsx
│   │   ├── HealthQuestionnairePage.tsx
│   │   └── MedicalClearanceUploadPage.tsx
│   ├── components/
│   │   └── MedicalHistoryViewer.tsx
│   └── services/
│       └── studentHealthService.ts
```

**Migración (US-39/US-40)**: `student_profiles.full_name` → `first_name` + `last_name`; nuevas columnas `fitness_goals` y `personal_motivation`; `PHONE_PATTERN` existente se mantiene (ya cubre `+` opcional y 10-15 dígitos); `student_service` agrega ≥1 objetivo a la regla de publicación.

**Structure Decision**: Submódulo `students` y `medical` con capa de abstracción `StorageService` para desacoplar el sistema de archivos del servidor.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
