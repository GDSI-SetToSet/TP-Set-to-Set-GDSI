# Tasks: Reporte de molestias o dolor en mapa corporal (US-61)

**Feature Branch**: `feature/061-us61-body-map-pain-report`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Contract**: [contracts/body-map-pain-reports-api.yaml](./contracts/body-map-pain-reports-api.yaml)

---

## Phase 1: Setup & Data Modeling (Backend)
- [x] T001 [US61] Crear modelos SQLAlchemy `BodyMapPainReport` y `BodyMapPainReportZone` en `backend/src/models/body_map_report.py` con relaciones, claves foráneas a `student_profiles`, `workout_sessions`, `exercises` y `training_relationships`, índices para consultas cronológicas y por zona, y restricción de unicidad para zonas en un mismo reporte.
- [x] T002 [US61] Registrar los nuevos modelos en `backend/src/models/__init__.py`, `backend/src/core/migrations.py` y `backend/tests/conftest.py`.
- [x] T003 [US61] Crear schemas Pydantic en `backend/src/schemas/body_map_report.py`: `ReportZoneInput`, `ReportZoneOutput`, `BodyMapReportCreate`, `BodyMapReportResponse`, `BodyMapReportActionUpdate`, `BodyMapZoneHistoryItem`.

---

## Phase 2: Business Logic & Service Implementation (Backend)
- [x] T004 [US61] Crear servicio `backend/src/services/body_map_report_service.py` con:
  - `create_body_map_report(db, user, payload)`: valida pertenencia de alumno, sesión y ejercicio; valida catálogo de zonas e intensidades; evalúa variante segura con US-53 si es en ejercicio; dispara notificación de alerta al entrenador si hay `PAIN` (US-29); maneja idempotencia; transaccionalidad atómica.
  - `update_report_action(db, user, report_id, action_taken)`: actualiza la acción tomada tras el reporte garantizando pertenencia.
  - `list_student_body_map_reports(db, user, filters)`: consulta reportes propios del alumno con filtros de zona, intensidad, sesión y paginación.
  - `list_student_zone_history(db, user, filters)`: historial desagregado por zona corporal del alumno.
  - `list_trainer_student_body_map_reports(db, trainer_user, student_id, filters)`: consulta con verificación estricta de vínculo activo (`TrainingRelationship.status == "ACTIVE"`).
  - `list_trainer_student_zone_history(db, trainer_user, student_id, filters)`: historial por zona para entrenador con vínculo activo.

---

## Phase 3: API Endpoints & Routing (Backend)
- [x] T005 [US61] Crear endpoints en `backend/src/api/v1/body_map_reports.py`:
  - `POST /api/v1/body-map-reports`
  - `PATCH /api/v1/body-map-reports/{report_id}/action`
  - `GET /api/v1/students/me/body-map-reports`
  - `GET /api/v1/students/me/body-map-reports/by-zone`
  - `GET /api/v1/trainers/me/students/{student_id}/body-map-reports`
  - `GET /api/v1/trainers/me/students/{student_id}/body-map-reports/by-zone`
- [x] T006 [US61] Registrar el nuevo router en `backend/src/main.py`.

---

## Phase 4: Database Migrations & Validation (Backend)
- [x] T007 [US61] Incorporar tablas y verificaciones en `backend/src/core/migrations.py` garantizando compatibilidad SQLite y PostgreSQL.
- [x] T008 [US61] Crear suite de pruebas exhaustiva en `backend/tests/test_us61_body_map_pain_report_api.py` cubriendo creación, múltiples zonas, clasificaciones válidas e inválidas, pertenencia de sesión/ejercicio, alertas para PAIN, ausencia para NORMAL/DISCOMFORT, variantes de US-53, autorización de alumno y entrenador, e idempotencia ante reintentos.
- [x] T009 [US61] Incorporar pruebas de migración en `backend/tests/test_database_migrations.py`.

---

## Phase 5: Frontend Implementation
- [x] T010 [US61] Crear tipos en `frontend/src/types/bodyMapReport.ts` y servicio en `frontend/src/services/bodyMapReportService.ts`.
- [x] T011 [US61] Crear componente interactivo `BodyMapSelector.tsx` con soporte de vistas anterior y posterior, selección múltiple de zonas, asignación individual de intensidades (`Carga normal`, `Molestia`, `Dolor`), contraste accesible y soporte móvil/escritorio.
- [x] T012 [US61] Crear diálogo modal `InExercisePainReportModal.tsx` para «Reportar dolor» durante el ejercicio, integrando la variante segura de US-53 y la opción de salteo de ejercicio.
- [x] T013 [US61] Integrar el reporte en `StudentRoutinesPage.tsx` durante el ejercicio y al finalizar la sesión (coexistiendo armónicamente con US-60 RPE).
- [x] T014 [US61] Integrar historial de molestias en la vista de progreso del alumno y en el panel del entrenador (`RoutineAssignmentPanel.tsx`).
- [x] T015 [US61] Estilos visuales en `frontend/src/styles/body-map.css`.

---

## Phase 6: Verification & Regression
- [x] T016 [US61] Ejecutar suite de pruebas de US-61, US-60, US-53 y migraciones con Pytest.
- [x] T017 [US61] Ejecutar Ruff linter.
- [x] T018 [US61] Control de alcance, diff git y reporte final.
