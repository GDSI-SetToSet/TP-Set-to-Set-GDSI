# Implementation Plan: Reporte de molestias o dolor en mapa corporal (US-61)

**Branch**: `feature/061-us61-body-map-pain-report` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `taskify/specs/008-workout-feedback-and-communication/spec.md` (User Story 2: US-61).

---

## 1. Summary

La User Story US-61 permite a los alumnos registrar sensaciones corporales («carga normal», «molestia» o «dolor») en un mapa anatómico interactivo tanto durante la ejecución de un ejercicio como al finalizar una sesión de entrenamiento.
- **Durante el ejercicio**: Permite reportar dolor y busca automáticamente variantes seguras del ejercicio contraindicado utilizando el motor de US-53 (`safe_variant_service`). Si existe una variante segura configurada por el entrenador, se la ofrece al alumno; si no existe, le permite saltear el ejercicio.
- **Al finalizar la sesión**: Permite marcar múltiples zonas y clasificarlas individualmente sin obligatoriedad, integrándose armónicamente con el reporte de RPE (US-60).
- **Alerta al entrenador**: Ante cualquier reporte que incluya la clasificación `PAIN` («dolor»), el sistema genera inmediatamente una alerta/notificación para el entrenador con vínculo activo (US-29 / `notification_service`), vinculada a la entidad del reporte, deduplicando ante reintentos.
- **Historial de reportes**: Tanto el alumno como su entrenador autorizado pueden consultar la evolución temporal de reportes agrupados o filtrados por zona corporal, fecha, sesión y ejercicio.

---

## 2. Technical Context

**Language/Version**:
- Backend: Python 3.12 (FastAPI, SQLAlchemy 2.0, Pydantic v2).
- Frontend: TypeScript 5.6, React 18, React Router v6, CSS modular/global, Lucide React.

**Primary Dependencies & Reused Mechanisms**:
- Backend:
  - `backend/src/services/safe_variant_service.py`: Reutilización de `resolve_variant(db, exercise, zones)` para evaluar variantes seguras de US-53.
  - `backend/src/services/notification_service.py`: Reutilización de `create_notification(db, recipient_id, type="PAIN_ALERT", ...)` para emisión desacoplada de alertas de US-29.
  - `backend/src/core/constants.py`: Catálogo canónico de zonas anatómicas (`BODY_AREAS`, `canonical_zone_key`, `BODY_AREAS_ES`).
  - `backend/src/core/migrations.py`: Migraciones aditivas e idempotentes para SQLite y PostgreSQL.
- Frontend:
  - `frontend/src/constants/bodyAreas.ts`: Catálogo de zonas (`BODY_AREAS`, `ZONES_ES`).
  - `frontend/src/components/SafeVariantNotice.tsx` y `safeVariantService.ts`: Componentes y tipos de variantes seguras.
  - `frontend/src/pages/StudentRoutinesPage.tsx`: Integración del modal de reporte durante ejercicio y en el modal de fin de rutina.

**Storage**:
- SQLite (desarrollo local y tests de CI con foreign keys activadas).
- PostgreSQL 16 (producción).
- Tablas aditivas: `body_map_pain_reports` y `body_map_pain_report_zones`.

**Testing**:
- Backend: Pytest con cobertura automatizada (`backend/tests/test_us61_body_map_pain_report_api.py`, `backend/tests/test_database_migrations.py`).
- Linter: Ruff (`ruff check backend`).

---

## 3. Constitution Check

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| **I. Accesibilidad y Usabilidad** | PASSED | Controles interactivos en mapa corporal con contraste WCAG 2.1 AA ($\ge 4.5:1$), áreas de pulsación $\ge 44 \times 44$ px, soporte táctil y de escritorio con vistas anterior y posterior, etiquetas semánticas y aria. |
| **II. IA Asistiva con Supervisión Humana** | N/A | No involucra IA generativa directa; respeta las variantes asignadas previamente por el entrenador. |
| **III. Privacidad y Datos Sensibles de Salud** | PASSED | Enforcement estricto del lado del servidor (server-side): el alumno solo accede a sus propios reportes; el entrenador solo puede acceder a reportes de alumnos con quienes mantenga un vínculo activo (`TrainingRelationship.status == 'ACTIVE'`). Validación en cada endpoint. |
| **IV. Pagos Informales** | N/A | No procesa pagos. |
| **V. Gestión Liviana de Medios Técnicos** | PASSED | Reutiliza los reproductores de video de variantes seguras ya configuradas sin manipular archivos pesados. |
| **VI. Calidad y Verificación Continua** | PASSED | Pruebas exhaustivas unitarias y de integración backend para todos los criterios y casos borde; linter Ruff limpio. |
| **VII. Entrega Incremental** | PASSED | Feature branch aislada `feature/061-us61-body-map-pain-report` basada en el último commit de `origin/develop`, sin cherry-picks ni mezclas de otras ramas. |

---

## 4. Domain & Data Model

### Entidad 1: `BodyMapPainReport` (`body_map_pain_reports`)
Representa el evento de reporte registrado por el alumno.

| Columna | Tipo | Nulable | Restricciones / Descripción |
|---|---|---|---|
| `id` | VARCHAR(36) | NO | Primary Key (UUIDv4) |
| `student_id` | VARCHAR(36) | NO | FK `student_profiles.id` ON DELETE CASCADE, indexado |
| `relationship_id` | VARCHAR(36) | SÍ | FK `training_relationships.id` ON DELETE SET NULL, indexado |
| `session_id` | VARCHAR(36) | SÍ | FK `workout_sessions.id` ON DELETE SET NULL, indexado |
| `exercise_id` | VARCHAR(36) | SÍ | FK `exercises.id` ON DELETE SET NULL, indexado |
| `context` | VARCHAR(32) | NO | Enum: `'POST_SESSION'`, `'IN_EXERCISE'` |
| `action_taken` | VARCHAR(32) | SÍ | Enum: `'NONE'`, `'VARIANT_OFFERED'`, `'VARIANT_ACCEPTED'`, `'EXERCISE_SKIPPED'` |
| `idempotency_key` | VARCHAR(64) | SÍ | UNIQUE INDEX, previene duplicados en reintentos |
| `created_at` | DATETIME | NO | UTC ISO 8601 |

### Entidad 2: `BodyMapPainReportZone` (`body_map_pain_report_zones`)
Detalla cada zona corporal marcada y su nivel de molestia dentro del reporte.

| Columna | Tipo | Nulable | Restricciones / Descripción |
|---|---|---|---|
| `id` | VARCHAR(36) | NO | Primary Key (UUIDv4) |
| `report_id` | VARCHAR(36) | NO | FK `body_map_pain_reports.id` ON DELETE CASCADE, indexado |
| `zone` | VARCHAR(50) | NO | Zona canónica (`BODY_AREAS`) |
| `intensity` | VARCHAR(20) | NO | Enum: `'NORMAL'`, `'DISCOMFORT'`, `'PAIN'` |
| `created_at` | DATETIME | NO | UTC ISO 8601 |

Constraint: `UniqueConstraint("report_id", "zone", name="uq_body_map_report_zone")`.

---

## 5. Integración con US-53 y US-29

### 5.1. Integración con US-53 (Variantes Seguras)
- En el endpoint `POST /api/v1/body-map-reports`, cuando `context == "IN_EXERCISE"` y se proporciona `exercise_id`:
  - Se obtienen las zonas reportadas (especialmente aquellas con `PAIN` o `DISCOMFORT`, complementadas con las zonas protegidas del perfil).
  - Se ejecuta `resolve_variant(db, exercise, reported_zones)`.
  - Si retorna `"VARIANT"`, se incluye la variante en la respuesta del reporte (`safe_variant.variant`).
  - Si retorna `"BLOCKED"`, se informa que no hay variante segura disponible y se habilita `can_skip = true`.
  - El alumno puede seleccionar la variante o saltear el ejercicio; el reporte original queda intacto y persistido.

### 5.2. Integración con US-29 (Alertas al Entrenador)
- Cuando al menos una zona del reporte tiene intensidad `PAIN`:
  - Se busca la relación activa de entrenamiento del alumno (`TrainingRelationship.status == "ACTIVE"`).
  - Si existe entrenador asignado, se emite una notificación mediante `notification_service.create_notification`:
    - `recipient_id = relationship.trainer.user_id`
    - `type = "PAIN_ALERT"`
    - `title = "Alerta de dolor físico"`
    - `message = "{student_name} reportó dolor en {zonas} durante {contexto}."`
    - `related_entity_type = "BODY_MAP_PAIN_REPORT"`
    - `related_entity_id = report.id`
    - `commit = False` (para garantizar atomicidad con la transacción del reporte).
  - Si el reporte contiene exclusivamente `NORMAL` o `DISCOMFORT`, NO se emite alerta al entrenador.
  - La deduplicación por reintento (`idempotency_key` o clave natural de reporte) evita emisiones duplicadas.

---

## 6. Endpoints y Seguridad

1. `POST /api/v1/body-map-reports`: Creación de reporte por el alumno autenticado.
2. `PATCH /api/v1/body-map-reports/{id}/action`: Actualización de la acción posterior por el alumno dueño.
3. `GET /api/v1/students/me/body-map-reports`: Historial de reportes del alumno autenticado.
4. `GET /api/v1/students/me/body-map-reports/by-zone`: Historial desagregado por zona corporal del alumno.
5. `GET /api/v1/trainers/me/students/{student_id}/body-map-reports`: Historial del alumno consultado por el entrenador (verificación estricta de relación activa).
6. `GET /api/v1/trainers/me/students/{student_id}/body-map-reports/by-zone`: Historial por zona del alumno para el entrenador activo.

---

## 7. Frontend Architecture

1. **Componente `BodyMapSelector`**:
   - Vista anatómica interactiva (anterior y posterior) con zonas seleccionables (`BODY_AREAS`).
   - Selector de intensidad para cada zona marcada: Carga normal (verde/azul neutro), Molestia (amarillo/naranja), Dolor (rojo).
   - Indicadores visuales y textuales de estado (no depende únicamente del color).
   - Accesibilidad: aria-pressed, keyboard focus, áreas de pulsación mínimas de 44x44px.
2. **Modal «Reportar dolor» durante el ejercicio (`StudentRoutinesPage`)**:
   - Botón accesible en cada ejercicio de la sesión en curso.
   - Abre el diálogo de reporte, permitiendo clasificar zonas.
   - Al confirmar:
     - Persiste el reporte en la API.
     - Si hay variante segura ofrecida por US-53, se presenta de forma destacada para reemplazar el ejercicio en la sesión.
     - Si no hay variante segura, se habilita la opción de saltear el ejercicio.
3. **Flujo de fin de rutina (`StudentRoutinesPage`)**:
   - Integración en el diálogo de finalización de sesión.
   - Pestaña o sección opcional del mapa corporal previa a la confirmación de finalización, coexistiendo con el RPE de US-60.
4. **Historial de sensaciones por zona (`StudentRoutinesPage` y `RoutineAssignmentPanel`)**:
   - Visualización cronológica de sensaciones reportadas con badges de intensidad, fecha, día de la sesión y ejercicio.
