# Plan de implementación: Feature 009 — US-18 y US-19

**Branch**: `feature/us18-active-students` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Entrada**: US-18 y US-19 de `taskify/specs/009-trainer-monitoring-and-safety/spec.md`.

## Resumen

Completar la experiencia existente de “Mis alumnos” del entrenador sin reconstruirla. Mantener el listado actual de vínculos activos, la asignación de rutinas, el progreso, las sesiones, los registros de esfuerzo, los reportes de dolor y las advertencias de zonas protegidas. Agregar un modelo de lectura del entrenador sobre el alumno y una vista de detalle que componga los datos existentes de perfil, paquete, rutina y actividad. US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 y US-32 quedan explícitamente excluidas.
Agregar sobre ese listado la búsqueda local de US-19 por nombre y apellido, sin distinguir mayúsculas ni acentos, sin modificar el backend ni las acciones existentes. US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 y US-32 quedan explícitamente excluidas.

## Contexto técnico

**Lenguaje/Versión**: Python 3.12; TypeScript/React 18; Node.js 20

**Dependencias principales**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Pytest, React Router, Axios, servicios de dominio existentes

**Almacenamiento**: modelos existentes de SQLite/PostgreSQL; no se crearán tablas ni migraciones nuevas

**Pruebas**: pruebas de integración con Pytest; compilación de producción del frontend con `npm run build`

**Plataforma objetivo**: aplicación web responsiva en un servidor Linux

**Tipo de proyecto**: aplicación web existente con FastAPI + React

**Objetivos de rendimiento**: una solicitud para el listado y una para el detalle; el detalle debe evitar una expansión de solicitudes API por elemento y responder dentro del presupuesto actual de la aplicación para la cartera de un entrenador

**Restricciones**: autorización del lado del servidor en cada solicitud de detalle; solo `TrainingRelationship.status == "ACTIVE"` concede acceso; errores RFC 7807; marcas de tiempo UTC; no duplicar reglas de negocio

**Escala/Alcance**: alumnos activos de un entrenador; US-18 y búsqueda local de US-19; sin filtrado por paquete, mensajería, gráficos, ciclo de vida de alertas ni cálculo de abandono

## Verificación de la Constitución

*PUERTA DE CONTROL: Debe aprobarse antes de la investigación de la Fase 0. Volver a verificar después del diseño de la Fase 1.*

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Reutilizar el diseño responsivo actual de “Mis alumnos”; la selección del detalle y los estados vacío/carga/error conservan controles accesibles y mensajes comprensibles. |
| II. Participación humana | N/A | US-18 solo lee rutinas y métricas; no asigna ni activa rutinas. |
| III. Privacidad de salud | PASS | El acceso al detalle se autoriza en el servidor y requiere un vínculo activo entre entrenador y alumno; las zonas protegidas y los reportes solo se devuelven dentro de esa autorización. |
| IV. Pagos informales | N/A | No hay mutaciones ni procesamiento de pagos. |
| V. Medios externos | N/A | No se agrega almacenamiento de medios ni comportamiento de video. |
| VI. Verificación continua | PASS | Se requieren pruebas de aceptación y autorización del backend, además de la compilación del frontend. |
| VII. Entrega incremental | PASS | Una historia, una rama/objetivo de PR, sin implementar las demás historias de la feature. |

## Estructura del proyecto

### Documentación

```text
taskify/specs/009-trainer-monitoring-and-safety/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/trainer-student-detail-api.yaml
└── tasks.md
```

### Código fuente

```text
backend/
├── src/
│   ├── api/v1/trainers.py
│   ├── schemas/trainer_student.py
│   └── services/trainer_student_service.py
└── tests/test_trainer_student_api.py
frontend/
└── src/
    ├── components/TrainerStudentDetail.tsx
    ├── components/RoutineAssignmentPanel.tsx
    ├── utils/studentSearch.mjs
    ├── pages/TrainerStudentsPage.tsx
    ├── services/trainerStudentService.ts
    └── types/trainerStudent.ts
```

**Decisión de estructura**: agregar únicamente una capa delgada de orquestación orientada a lectura para US-18. Reutilizar `TrainingRelationship`, `StudentProfile`, `TrainingPlan`, `StudentRoutine`, los servicios existentes de asignación/progreso de rutinas y los servicios existentes de reportes. No crear modelos de reemplazo, un segundo listado de alumnos ni un subsistema paralelo de rutinas/métricas.

## Seguimiento de complejidad

No hay incumplimientos constitucionales.
