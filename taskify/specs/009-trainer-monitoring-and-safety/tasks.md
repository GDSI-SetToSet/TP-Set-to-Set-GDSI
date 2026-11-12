---
description: "Lista de tareas exclusiva de US-18 para el resumen de alumnos activos"
---

# Tareas: US-18 — Visualización de alumnos activos

**Entrada**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/trainer-student-detail-api.yaml`, `quickstart.md`

**Alcance**: únicamente US-18. No implementar US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 ni US-32.

## Fase 1: Línea base del flujo existente

- [X] T001 [US1] [US18] Registrar el comportamiento actual de `/entrenador/alumnos` y la consulta existente de vínculos activos en `backend/tests/test_trainer_student_api.py` y `frontend/src/pages/TrainerStudentsPage.tsx` sin cambiar el flujo existente de asignación/progreso.
- [X] T002 [P] [US1] [US18] Agregar cobertura de regresión para el alcance exclusivo de activos, el estado vacío, el aislamiento entre entrenadores y la continuidad de la asignación de rutinas en `backend/tests/test_trainer_student_api.py` y los archivos de pruebas existentes relevantes.

## Fase 2: Modelo de lectura y API

- [X] T003 [P] [US1] [US18] Definir los modelos de respuesta Pydantic para listado/detalle, acuerdo del paquete, perfil, limitaciones, rutina vigente y métricas compactas en `backend/src/schemas/trainer_student.py`.
- [X] T004 [US1] [US18] Implementar la orquestación de lectura autorizada en `backend/src/services/trainer_student_service.py`, reutilizando `TrainingRelationship`, `StudentProfile`, `TrainingPlan`, `StudentRoutine`, los servicios existentes de rutinas, las consultas de sesiones/registros y los servicios de reportes/zonas; no duplicar las reglas de autorización.
- [X] T005 [US1] [US18] Exponer `GET /api/v1/trainers/me/students` y `GET /api/v1/trainers/me/students/{student_id}` en `backend/src/api/v1/trainers.py` o en el registro existente del router de entrenadores, devolviendo errores RFC 7807 y excluyendo los vínculos no activos.
- [X] T006 [US1] [US18] Agregar pruebas de API para el éxito del listado/detalle, la ausencia de alumnos activos, el acuerdo del paquete, la composición de perfil/objetivos/limitaciones/rutina/métricas, el acceso entre entrenadores, el acceso a vínculos terminados y la ausencia de divulgación de rutinas en borrador en `backend/tests/test_trainer_student_api.py`.

## Fase 3: Integración con la pantalla existente

- [X] T007 [P] [US1] [US18] Agregar métodos tipados del cliente y tipos de respuesta para el contrato de listado/detalle de US-18 en `frontend/src/services/trainerStudentService.ts` y `frontend/src/types/trainerStudent.ts`.
- [X] T008 [US1] [US18] Integrar la selección y la representación del detalle en `frontend/src/pages/TrainerStudentsPage.tsx` y en un componente enfocado `frontend/src/components/TrainerStudentDetail.tsx`, preservando `RoutineAssignmentPanel` como superficie existente de asignación/progreso.
- [X] T009 [US1] [US18] Preservar y verificar los estados de carga, vacío, error, detalle autorizado, ausencia de rutina y ausencia de actividad en `frontend/src/pages/TrainerStudentsPage.tsx` y `frontend/src/components/TrainerStudentDetail.tsx` sin agregar interfaz de búsqueda, filtros, gráficos, mensajería ni revisión de alertas.

## Fase 4: Verificación

- [X] T010 [P] [US1] [US18] Extender las pruebas enfocadas del backend para cubrir los escenarios de `quickstart.md` y el comportamiento de autorización RFC 7807 en `backend/tests/test_trainer_student_api.py`.
- [X] T011 [P] [US1] [US18] Ejecutar `ruff check backend` y el comando de pruebas enfocado/completo del backend con cobertura, utilizando el formato compatible con CI existente en el repositorio.
- [X] T012 [US1] [US18] Ejecutar `npm run build` en `frontend/` y ejecutar manualmente `taskify/specs/009-trainer-monitoring-and-safety/quickstart.md`.
- [X] T013 [US1] [US18] Ejecutar `/speckit-analyze` sobre los artefactos delimitados a US-18 y verificar que ninguna tarea haga referencia a la implementación de otra historia.

## Dependencias

T001 → T002/T003 (en paralelo) → T004 → T005 → T006 → T007/T008/T009 (T007 en paralelo con T006; T008 después de T007 y T005) → T010/T011/T012 → T013.

## Oportunidades de paralelización

- T002 y T003 pueden ejecutarse en paralelo.
- T007 puede ejecutarse en paralelo con la finalización de las pruebas del backend una vez estabilizado el contrato.
- T010, T011 y T012 pueden ejecutarse en paralelo después de completar la integración.

## MVP

El incremento completo de US-18 comprende T003–T009: listado/detalle autorizado de alumnos activos e integración en la pantalla existente de “Mis alumnos”. T010–T013 son puertas de entrega obligatorias y no amplían el alcance.
