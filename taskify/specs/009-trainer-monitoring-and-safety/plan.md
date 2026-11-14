# Plan de implementación: Feature 009 — US-18, US-19 y US-30

**Branch**: `feature/us30-training-evolution` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Entrada**: US-18 y US-19 de `taskify/specs/009-trainer-monitoring-and-safety/spec.md`.

## Resumen

Completar la experiencia existente de “Mis alumnos” del entrenador sin reconstruirla. Mantener el listado actual de vínculos activos, la asignación de rutinas, el progreso, las sesiones, los registros de esfuerzo, los reportes de dolor y las advertencias de zonas protegidas. Agregar un modelo de lectura del entrenador sobre el alumno y una vista de detalle que componga los datos existentes de perfil, paquete, rutina y actividad. US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 y US-32 quedan explícitamente excluidas.
Agregar sobre ese listado la búsqueda local de US-19 por nombre y apellido, sin distinguir mayúsculas ni acentos, sin modificar el backend ni las acciones existentes. US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 y US-32 quedan explícitamente excluidas.

## Incremento US-30 — Evolución de entrenamientos

Agregar un gráfico de evolución en el detalle del alumno (US-18), junto al análisis de molestias de US-28. **Un único endpoint de solo lectura** `GET /api/v1/trainers/me/students/{student_id}/evolution?group_by=session|week|muscle_group&period=4w|12w|all&exercise_id=` calcula todo en el servidor sobre `WorkoutSession` finalizadas y sus `WorkoutSetLog` (sin tablas ni migraciones). Decisiones del spec (sesión 2026-11-14): tres métricas (carga, repeticiones totales, series), período por defecto 12 semanas, con `exercise_id` la carga es la carga máxima y sin él el volumen (repeticiones × carga), solo sesiones finalizadas, estados vacío / una sola sesión.

- **Backend**: nuevo `services/training_evolution_service.py`, que reutiliza `_performed`/`_number` de `session_comparison_service` (extraer a público en vez de duplicar), `get_or_create_profile` y el patrón de autorización de vínculo ACTIVO de US-24. Esquemas en `schemas/trainer_student.py`, ruta en `api/v1/trainers.py`. Grupo muscular desde `Exercise.target_muscle_group`.
- **Frontend**: `components/TrainingEvolution.tsx` montado en `TrainerStudentDetail.tsx`, con `services/trainerStudentService.ts` y `types/trainerStudent.ts`. Gráfico SVG propio, igual que las barras de `PainReportAnalysis` (no se agrega librería de gráficos).
- **Pruebas**: `backend/tests/test_us30_training_evolution_api.py` (agrupaciones, período, filtro por ejercicio, exclusión de sesiones en curso, vacío, autorización) y `npm run build`.

## Contexto técnico

**Lenguaje/Versión**: Python 3.12; TypeScript/React 18; Node.js 20

**Dependencias principales**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Pytest, React Router, Axios, servicios de dominio existentes

**Almacenamiento**: modelos existentes de SQLite/PostgreSQL; no se crearán tablas ni migraciones nuevas

**Pruebas**: pruebas de integración con Pytest; compilación de producción del frontend con `npm run build`

**Plataforma objetivo**: aplicación web responsiva en un servidor Linux

**Tipo de proyecto**: aplicación web existente con FastAPI + React

**Objetivos de rendimiento**: una solicitud para el listado y una para el detalle; el detalle debe evitar una expansión de solicitudes API por elemento y responder dentro del presupuesto actual de la aplicación para la cartera de un entrenador

**Restricciones**: autorización del lado del servidor en cada solicitud de detalle; solo `TrainingRelationship.status == "ACTIVE"` concede acceso; errores RFC 7807; marcas de tiempo UTC; no duplicar reglas de negocio

**Escala/Alcance**: alumnos activos de un entrenador; US-18, búsqueda local de US-19 y gráfico de evolución de US-30; sin filtrado por paquete, mensajería, gráficos, ciclo de vida de alertas ni cálculo de abandono

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
├── contracts/trainer-student-detail-api.yaml  (incluye /evolution de US-30)
└── tasks.md
```

### Código fuente

```text
backend/
├── src/
│   ├── api/v1/trainers.py
│   ├── schemas/trainer_student.py
│   └── services/
│       ├── trainer_student_service.py
│       └── training_evolution_service.py   (US-30)
└── tests/
    ├── test_trainer_student_api.py
    └── test_us30_training_evolution_api.py (US-30)
frontend/
└── src/
    ├── components/TrainerStudentDetail.tsx
    ├── components/TrainingEvolution.tsx    (US-30)
    ├── components/RoutineAssignmentPanel.tsx
    ├── utils/studentSearch.mjs
    ├── pages/TrainerStudentsPage.tsx
    ├── services/trainerStudentService.ts
    └── types/trainerStudent.ts
```

**Decisión de estructura**: agregar únicamente una capa delgada de orquestación orientada a lectura para US-18. Reutilizar `TrainingRelationship`, `StudentProfile`, `TrainingPlan`, `StudentRoutine`, los servicios existentes de asignación/progreso de rutinas y los servicios existentes de reportes. No crear modelos de reemplazo, un segundo listado de alumnos ni un subsistema paralelo de rutinas/métricas.

## Seguimiento de complejidad

No hay incumplimientos constitucionales.
