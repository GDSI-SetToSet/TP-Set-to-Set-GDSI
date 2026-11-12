---
description: "Lista de tareas de US-18 y US-19 para alumnos activos"
---

# Tasks: US-18 y US-19 — Alumnos activos y búsqueda

**Entrada**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/trainer-student-detail-api.yaml`, `quickstart.md`

**Alcance**: US-18, US-19 y US-32. No implementado US-20, US-21, US-22, US-24, US-26, US-28, US-29 ni US-30.

## Phase 1: Línea base del flujo existente

- [X] T001 [US1] [US18] Registrar el comportamiento actual de `/entrenador/alumnos` y la consulta existente de vínculos activos en `backend/tests/test_trainer_student_api.py` y `frontend/src/pages/TrainerStudentsPage.tsx` sin cambiar el flujo existente de asignación/progreso.
- [X] T002 [P] [US1] [US18] Agregar cobertura de regresión para el alcance exclusivo de activos, el estado vacío, el aislamiento entre entrenadores y la continuidad de la asignación de rutinas en `backend/tests/test_trainer_student_api.py` y los archivos de pruebas existentes relevantes.

## Phase 2: Modelo de lectura y API

- [X] T003 [P] [US1] [US18] Definir los modelos de respuesta Pydantic para listado/detalle, acuerdo del paquete, perfil, limitaciones, rutina vigente y métricas compactas en `backend/src/schemas/trainer_student.py`.
- [X] T004 [US1] [US18] Implementar la orquestación de lectura autorizada en `backend/src/services/trainer_student_service.py`, reutilizando `TrainingRelationship`, `StudentProfile`, `TrainingPlan`, `StudentRoutine`, los servicios existentes de rutinas, las consultas de sesiones/registros y los servicios de reportes/zonas; no duplicar las reglas de autorización.
- [X] T005 [US1] [US18] Exponer `GET /api/v1/trainers/me/students` y `GET /api/v1/trainers/me/students/{student_id}` en `backend/src/api/v1/trainers.py` o en el registro existente del router de entrenadores, devolviendo errores RFC 7807 y excluyendo los vínculos no activos.
- [X] T006 [US1] [US18] Agregar pruebas de API para el éxito del listado/detalle, la ausencia de alumnos activos, el acuerdo del paquete, la composición de perfil/objetivos/limitaciones/rutina/métricas, el acceso entre entrenadores, el acceso a vínculos terminados y la ausencia de divulgación de rutinas en borrador en `backend/tests/test_trainer_student_api.py`.

## Phase 3: Integración con la pantalla existente

- [X] T007 [P] [US1] [US18] Agregar métodos tipados del cliente y tipos de respuesta para el contrato de listado/detalle de US-18 en `frontend/src/services/trainerStudentService.ts` y `frontend/src/types/trainerStudent.ts`.
- [X] T008 [US1] [US18] Integrar la selección y la representación del detalle en `frontend/src/pages/TrainerStudentsPage.tsx` y en un componente enfocado `frontend/src/components/TrainerStudentDetail.tsx`, preservando `RoutineAssignmentPanel` como superficie existente de asignación/progreso.
- [X] T009 [US1] [US18] Preservar y verificar los estados de carga, vacío, error, detalle autorizado, ausencia de rutina y ausencia de actividad en `frontend/src/pages/TrainerStudentsPage.tsx` y `frontend/src/components/TrainerStudentDetail.tsx` sin agregar interfaz de búsqueda, filtros, gráficos, mensajería ni revisión de alertas.

## Phase 4: Verificación

- [X] T010 [P] [US1] [US18] Extender las pruebas enfocadas del backend para cubrir los escenarios de `quickstart.md` y el comportamiento de autorización RFC 7807 en `backend/tests/test_trainer_student_api.py`.
- [X] T011 [P] [US1] [US18] Ejecutar `ruff check backend` y el comando de pruebas enfocado/completo del backend con cobertura, utilizando el formato compatible con CI existente en el repositorio.
- [X] T012 [US1] [US18] Ejecutar `npm run build` en `frontend/` y ejecutar manualmente `taskify/specs/009-trainer-monitoring-and-safety/quickstart.md`.
- [X] T013 [US1] [US18] Ejecutar `/speckit-analyze` sobre los artefactos delimitados a US-18 y verificar que ninguna tarea haga referencia a la implementación de otra historia.

## Phase 5: US-19 — Buscar por alumno

- [X] T014 [US19] Agregar el filtrado local por nombre y apellido, con normalización de mayúsculas y acentos, en `frontend/src/components/RoutineAssignmentPanel.tsx` y `frontend/src/utils/studentSearch.mjs`.
- [X] T015 [US19] Mostrar todos los alumnos activos con el campo vacío y `No se encontraron alumnos` cuando no haya coincidencias, preservando las acciones existentes en `frontend/src/components/RoutineAssignmentPanel.tsx`.
- [X] T016 [P] [US19] Agregar pruebas de búsqueda por nombre, apellido, nombre completo, ausencia de coincidencias, campo vacío, mayúsculas/minúsculas, exclusión de no activos y preservación de datos de acciones en `frontend/src/utils/studentSearch.test.mjs`.
- [X] T017 [US19] Ejecutar las pruebas enfocadas de US-19 y `npm run build` en `frontend/`.

## Phase 9: US-32 — Alumnos con riesgo de abandono

- [X] T036 [US32] Implementar `evaluate_risk` y `list_abandonment_risk` en `backend/src/services/abandonment_risk_service.py` (frecuencia según la rutina, umbral de 5 entrenamientos o 14 días, alerta `ABANDONMENT_RISK` deduplicada por período).
- [X] T037 [US32] Exponer `GET /api/v1/trainers/me/abandonment-risk` en `backend/src/api/v1/trainers.py` y evaluar el riesgo al listar `GET /api/v1/trainers/me/notifications` sin bloquear la lectura si falla.
- [X] T038 [P] [US32] Agregar pruebas de umbrales, deduplicación, orden, alumnos sin rutina, privacidad y tolerancia a fallos en `backend/tests/test_us32_abandonment_risk_api.py`.
- [X] T039 [US32] Priorizar a los alumnos en riesgo y mostrar la etiqueta "Riesgo de abandono" en `frontend/src/components/RoutineAssignmentPanel.tsx`, con `frontend/src/utils/abandonmentRisk.mjs` y sus pruebas; enlazar la notificación al alumno en `frontend/src/constants/routes.ts`.
- [X] T040 [US32] Ejecutar la suite completa del backend con cobertura, `ruff`, `npm test` y `npm run build`.

## Dependencias

T001 → T002/T003 (en paralelo) → T004 → T005 → T006 → T007/T008/T009 (T007 en paralelo con T006; T008 después de T007 y T005) → T010/T011/T012 → T013 → T014/T015/T016 (T016 en paralelo con T014/T015) → T017.

## Oportunidades de paralelización

- T002 y T003 pueden ejecutarse en paralelo.
- T007 puede ejecutarse en paralelo con la finalización de las pruebas del backend una vez estabilizado el contrato.
- T010, T011 y T012 pueden ejecutarse en paralelo después de completar la integración.
- T016 puede ejecutarse en paralelo con la implementación del filtro visual.

## MVP

El incremento de US-18 comprende T003–T009 y el incremento de US-19 comprende T014–T017: búsqueda local sobre alumnos activos ya cargados, sin cambios de backend. Las demás historias de la feature permanecen fuera de alcance.
