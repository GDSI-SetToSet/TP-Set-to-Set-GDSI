---
description: "Task list for 004-discovery-and-matchmaking (US-06 and US-07)"
---

# Tasks: Solicitudes de Alta y Gestión de Alumnos (US-06 y US-07)

**Input**: Design documents from `taskify/specs/004-discovery-and-matchmaking/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/matchmaking-api.yaml`, `quickstart.md`

**Tests**: Obligatorios para el backend por Constitución, Principio VI (cobertura $\ge 90\%$). El frontend se valida mediante compilación TypeScript (`tsc -b`), build de producción (`npm run build`) y verificación funcional manual contra los escenarios de aceptación.

**Organization**: Las tareas se estructuran por historia de usuario para permitir entregas independientes mediante Pull Requests individuales hacia `develop` (Principio VII: una historia por PR).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos independientes, sin dependencias previas no satisfechas).
- **[Story]**: `US5` = US-06 (Ver solicitudes de alumnos), `US6` = US-07 (Gestionar solicitudes de alumnos).
- Rutas relativas a la raíz del repositorio (`backend/`, `frontend/`, `taskify/`).

---

## Phase 1: Shared Setup & Precedents Sync

**Purpose**: Asegurar coherencia en contratos, schemas y precedentes integrados (`facundo-strint2` mergeado en `develop`).

- [x] T001 Sincronizar el contrato `taskify/specs/004-discovery-and-matchmaking/contracts/matchmaking-api.yaml` con el detalle de solicitud (`GET /matchmaking/requests/{id}`), motivo de rechazo opcional en `POST /reject` y schemas de respuesta
- [x] T002 Crear la checklist de calidad de requerimientos en `taskify/specs/004-discovery-and-matchmaking/checklists/requirements.md` y verificar completitud contra la Constitución

---

## Phase 2: User Story 5 — US-06 Ver solicitudes de alumnos (Priority: P1, 3 SP)

**Goal**: Permitir al entrenador consultar sus solicitudes entrantes pendientes en su bandeja de entrada con contador en el inicio, ver el detalle de cada solicitud con el resumen del alumno y acceder a sus objetivos, cuestionario de salud y apto médico mediante permisos autorizados en el backend.

**Independent Test**: Un entrenador autenticado con solicitudes pendientes ingresa a su inicio y ve el contador; abre la bandeja y visualiza las solicitudes ordenadas por fecha; entra al detalle de una solicitud y puede ver los objetivos del alumno, su cuestionario y el link al apto médico. Un entrenador sin solicitudes o un alumno no pueden acceder a dicha información.

### Tests for User Story 5 (US-06)

- [x] T003 [P] [US5] Crear pruebas de integración en `backend/tests/test_trainer_requests_inbox_api.py` para:
  - Listado de solicitudes de entrenador con filtro `status=PENDING` (solo ve sus solicitudes, no las de otros entrenadores).
  - Consulta de detalle `GET /api/v1/matchmaking/requests/{id}` con datos de alumno y paquete.
  - Alumnos que intentan consultar la bandeja de entrenador reciben HTTP 403 Forbidden.
  - Entrenador con solicitud `PENDING` puede consultar `GET /api/v1/students/{id}/goals`, `GET /api/v1/students/{id}/health-questionnaire` y descargar apto `GET /api/v1/students/{id}/medical-clearance/download`.
  - Entrenador sin solicitud o con solicitud `REJECTED` recibe HTTP 403 al intentar acceder a los datos de salud del alumno.
  - Respuesta incluye `can_be_accepted: false` cuando el entrenador tiene el cupo lleno (`active_students >= max_students`).

### Implementation for User Story 5 (US-06)

- [x] T004 [US5] Implementar en `backend/src/services/student_service.py` la lógica de autorización en [`trainer_has_access(db, trainer, student_profile_id)`](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/backend/src/services/student_service.py#L107) validando existencia de `TrainingRequest` con `status == 'PENDING'` o `TrainingRelationship` con `status == 'ACTIVE'` entre el entrenador y el alumno (depende de T003).
- [x] T005 [P] [US5] Implementar schemas `TrainingRequestStudentSummary`, `TrainingRequestDetailResponse` y query params de bandeja en `backend/src/schemas/discovery.py`.
- [x] T006 [US5] Implementar servicios `list_trainer_requests` y `get_trainer_request_detail` con cálculo dinámico de `can_be_accepted` en `backend/src/services/discovery_service.py` (depende de T004, T005).
- [x] T007 [US5] Exponer endpoints `GET /api/v1/matchmaking/requests` (con soporte para entrenador autenticado y filtro `status`) y `GET /api/v1/matchmaking/requests/{request_id}` en `backend/src/api/v1/discovery.py` (depende de T006).
- [x] T008 [P] [US5] Agregar tipos TypeScript y métodos de API para la bandeja de entrenador y detalle de solicitud en `frontend/src/types/discovery.ts` y `frontend/src/services/discoveryService.ts`.
- [x] T009 [US5] Crear la página `TrainerRequestsInboxPage.tsx` con listado de solicitudes pendientes, tarjeta de resumen, estado vacío, botón de refresco manual y estilos accesibles bajo la paleta azul del entrenador en `frontend/src/pages/TrainerRequestsInboxPage.tsx` y `frontend/src/styles/discovery.css`.
- [x] T010 [US5] Crear la página `TrainerRequestDetailPage.tsx` mostrando información de contacto del alumno, arancel acordado, mensaje inicial, sección de objetivos, link al cuestionario de salud y descarga del apto médico en `frontend/src/pages/TrainerRequestDetailPage.tsx`.
- [x] T011 [US5] Registrar rutas `trainerRequests: '/entrenador/solicitudes'` y `trainerRequestDetail: '/entrenador/solicitudes/:requestId'` en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`.
- [x] T012 [US5] Agregar badge con contador de solicitudes pendientes y acceso directo a la bandeja en `frontend/src/pages/HomePage.tsx` para el rol entrenador.
- [x] T013 [US5] Ejecutar suite de pruebas (`pytest backend/tests --cov=backend/src --cov-fail-under=90`), `ruff check backend`, `npm run build` y validación manual de los 5 escenarios de aceptación de US-06.

**Checkpoint**: US-06 está completa de punta a punta, probada y lista para abrir PR hacia `develop`.

---

## Phase 3: User Story 6 — US-07 Gestionar solicitudes de alumnos (Priority: P1, 5 SP)

**Goal**: Permitir al entrenador aceptar o rechazar solicitudes de alumnos, aplicando control transaccional de cupos con bloqueo pesimista, creación del vínculo activo inmutable, revocación inmediata de acceso a datos de salud ante rechazo y prevención de acciones repetidas.

**Independent Test**: Un entrenador con cupo acepta una solicitud y verifica que se crea el vínculo activo, se descuenta un cupo y la solicitud sale de la bandeja. Con cupo lleno, el botón Aceptar está deshabilitado y un intento forzado vía API devuelve HTTP 409 sin modificar el cupo. Al rechazar una solicitud con motivo opcional, la solicitud pasa a REJECTED y el entrenador pierde inmediatamente el acceso a los datos de salud del alumno.

### Tests for User Story 6 (US-07)

- [x] T014 [P] [US6] Crear pruebas de integración en `backend/tests/test_trainer_requests_actions_api.py` para:
  - `POST /api/v1/matchmaking/requests/{id}/accept`: crea `TrainingRelationship` en estado `ACTIVE`, copia arancel y moneda acordados, suma 1 a `count_active_students` y cambia estado a `ACCEPTED`.
  - Aceptación con cupo lleno (`active_students >= max_students`): devuelve HTTP 409 Conflict con mensaje RFC 7807 *"Cupos agotados; libere un cupo para poder aceptar."* y no modifica la base de datos.
  - `POST /api/v1/matchmaking/requests/{id}/reject`: actualiza a `REJECTED`, persiste motivo opcional (o `null` si no se envía) y fecha de resolución, no altera cupo.
  - Revocación inmediata: tras rechazo, `trainer_has_access` devuelve `False` y consultas a salud devuelven HTTP 403 Forbidden.
  - Idempotencia: intentar aceptar o rechazar una solicitud ya resuelta (`ACCEPTED` o `REJECTED`) devuelve HTTP 409 Conflict *"La solicitud ya fue procesada."*.
  - Solo el entrenador destinatario puede aceptar o rechazar su solicitud (otro entrenador recibe HTTP 403).

### Implementation for User Story 6 (US-07)

- [x] T015 [US6] Crear el modelo `TrainingRelationship` en `backend/src/models/training_relationship.py` según `data-model.md` (`id`, `student_id`, `trainer_id`, `plan_id`, `agreed_monthly_price`, `agreed_currency`, `status`, `start_date`, `end_date`, `terminated_at`, `termination_reason`) y registrarlo en `backend/src/models/__init__.py`, `backend/src/main.py` y `backend/tests/conftest.py`.
- [x] T016 [US6] Actualizar [`count_active_students(db, profile)`](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/backend/src/services/trainer_service.py#L83) en `backend/src/services/trainer_service.py` para consultar la cantidad real de `TrainingRelationship` con `status == 'ACTIVE'` de ese entrenador (**completa y cierra formalmente la tarea T026 de la spec 002**) (depende de T015).
- [x] T017 [P] [US6] Crear schemas `TrainingRequestAcceptPayload` (`welcome_message: str | None`), `TrainingRequestRejectPayload` (`rejection_reason: str | None`) y `TrainingRelationshipResponse` en `backend/src/schemas/discovery.py`.
- [x] T018 [US6] Implementar funciones transaccionales atómicas `accept_training_request` (con `with_for_update` sobre `TrainerProfile`, verificación de cupo disponible e inserción de `TrainingRelationship`) y `reject_training_request` en `backend/src/services/discovery_service.py` (depende de T015, T016, T017).
- [x] T019 [US6] Exponer endpoints `POST /api/v1/matchmaking/requests/{request_id}/accept` y `POST /api/v1/matchmaking/requests/{request_id}/reject` en `backend/src/api/v1/discovery.py` manejando excepciones de cupo y conflicto RFC 7807 (depende de T018).
- [x] T020 [P] [US6] Crear el componente modal de confirmación `RequestActionModal.tsx` en `frontend/src/components/RequestActionModal.tsx` para aceptar (con campo opcional de bienvenida) y rechazar (con textarea opcional de motivo).
- [x] T021 [US6] Integrar acciones de aceptar y rechazar en `TrainerRequestDetailPage.tsx`, inhabilitando el botón Aceptar si `can_be_accepted == False` con mensaje descriptivo de cupo agotado, y redirigiendo a la bandeja con feedback visual de éxito (depende de T019, T020).
- [x] T022 [US6] Ejecutar suite de pruebas completa backend y frontend, verificando cobertura $\ge 90\%$, linter Ruff y recorrido de los 6 escenarios de aceptación de US-07.

**Checkpoint**: US-07 está completa de punta a punta, probada y lista para abrir PR hacia `develop`.

---

## Phase 4: Polish & Documentation Updates

**Purpose**: Cerrar tareas cruzadas y actualizar guías de verificación.

- [x] T023 Actualizar `taskify/specs/004-discovery-and-matchmaking/quickstart.md` documentando los comandos curl y pasos de verificación de bandeja y resolución de solicitudes para US-06 y US-07.
- [x] T024 Marcar como completada la tarea `T026` en `taskify/specs/002-trainer-profile-and-plans/tasks.md` referenciando el conteo activo de `TrainingRelationship`.
- [x] T025 Ejecutar regresión completa del proyecto (`pytest backend/tests`, `ruff check backend`, `cd frontend && npm run build`) confirmando 0 errores.
