---
description: "Lista de tareas de US-35 de la feature 011"
---

# Tasks: US-35 — Dar de baja a un alumno

**Entrada**: `spec.md` (Sesión 2026-11-17), `plan-us35.md`, `contracts/student-termination-api.yaml`
**Alcance**: solo US-35. PR hacia `sprint6`. **Pruebas**: obligatorias (Principio VI).

## Fase 1: Backend

- [X] T001 [US35] Agregar `termination_category` (`String(24)`, nullable) a `backend/src/models/training_relationship.py` y su `ColumnMigration` en `backend/src/core/migrations.py`; prueba de migración aditiva e idempotente en `backend/tests/test_database_migrations.py`.
- [X] T002 [US35] Esquemas `StudentTerminationRequest` (categoría obligatoria; detalle ≤ 500, obligatorio con `OTRO`; mensajes "Elegí el motivo de la baja." y "Contá el motivo de la baja (hasta 500 caracteres).") y `StudentTerminationResult` en `backend/src/schemas/trainer_student.py`.
- [X] T003 [US35] `backend/src/services/student_termination_service.py`: `terminate_student(db, user, student_id, data, today)` valida el vínculo activo (404), lo pasa a `TERMINATED` con `end_date`, `terminated_at`, categoría y detalle, notifica al alumno (`SUBSCRIPTION_TERMINATED`, con nombre del entrenador, categoría y detalle) y devuelve el resultado con `available_slots`.
- [X] T004 [US35] Ruta `POST /api/v1/trainers/me/students/{student_id}/termination` en `backend/src/api/v1/trainers.py` con parámetro `date` (fecha local), errores RFC 7807.
- [X] T005 [US35] `backend/tests/test_us35_student_termination_api.py`: escenario 1 y 2 (estado, fechas, motivo; sale de "Mis alumnos" y de "Suscripciones"; libera cupo; pierde acceso al cuestionario de salud y al detalle del alumno; chat 409; pagos conservados; notificación al alumno con el motivo), escenario 3 (sin categoría, categoría inválida, `OTRO` sin detalle, detalle > 500), baja repetida → 404, entrenador ajeno → 404, alumno → 403, sin token → 401. La rutina del alumno deja de estar disponible por el filtro `ACTIVE` existente de `student_assigned_view` (sin prueba específica en esta story).

## Fase 2: Frontend

- [X] T006 [P] [US35] Tipos y `terminateStudent(studentId, payload)` en `frontend/src/types/trainerStudent.ts` y `frontend/src/services/trainerStudentService.ts`.
- [X] T007 [US35] `frontend/src/components/StudentTerminationDialog.tsx`: diálogo accesible con categorías (radios), detalle con contador, consecuencias, aviso de que el alumno verá el motivo y errores por campo.
- [X] T008 [US35] Botón "Dar de baja" en `frontend/src/components/TrainerStudentDetail.tsx`; al confirmar, `frontend/src/pages/TrainerStudentsPage.tsx` cierra el detalle, recarga la lista y muestra el mensaje de éxito. `SUBSCRIPTION_TERMINATED` en `studentNotificationPath` (`frontend/src/constants/routes.ts`) y en la campana.

## Fase 3: Verificación

- [X] T009 `ruff check backend`, `pytest --cov=backend/src` (≥ 90 %), `npm run build`.
- [X] T010 Recorrido en el navegador con la demo: baja desde el detalle, validación del motivo, efectos (lista, suscripciones, cupo), notificación del alumno y chat en modo lectura.
- [X] T011 Commit y PR hacia `sprint6`.
