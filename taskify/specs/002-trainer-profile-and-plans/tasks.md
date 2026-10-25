---
description: "Task list for 002-trainer-profile-and-plans"
---

# Tasks: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Input**: Design documents from `taskify/specs/002-trainer-profile-and-plans/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/trainer-api.yaml`, `quickstart.md`

**Tests**: Obligatorios para el backend por Constitución, Principio VI. El frontend se valida con compilación TypeScript/Vite y recorrido manual.

**Organization**: Las tareas se agrupan por historia para que US-02, US-03 y US-04 puedan implementarse y entregarse de forma independiente, una historia por PR.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo porque afecta archivos distintos y no depende de una tarea incompleta.
- **[Story]**: `US1` = US-02, `US2` = US-03, `US3` = US-04.
- Las rutas de código son relativas a la raíz del repositorio; las rutas de documentación son relativas a `taskify/`.

## Phase 1: Setup compartido

**Purpose**: Preparar la estructura del módulo sin implementar comportamiento de una historia.

- [x] T001 Crear los módulos y exports del dominio entrenador en `backend/src/models/trainer_profile.py`, `backend/src/schemas/trainer.py`, `backend/src/services/trainer_service.py`, `backend/src/api/v1/trainers.py` y sus respectivos `__init__.py`
- [x] T002 Registrar el router de entrenadores en `backend/src/main.py` y los imports de modelos para inicialización de metadata en `backend/src/models/__init__.py` y `backend/tests/conftest.py`

---

## Phase 2: User Story 1 — US-02 Perfil profesional del entrenador (Priority: P1) 🎯 MVP

**Goal**: Permitir que el entrenador guarde progresivamente su perfil, lo publique al completar nombre, contacto y especialidad, lo edite y permita su consulta a cualquier usuario autenticado.

**Independent Test**: Un entrenador guarda solo su biografía y conserva estado `DRAFT`; luego completa nombre, teléfono válido y especialidad, obtiene estado `PUBLISHED`, y otro usuario autenticado puede consultar el perfil. Un visitante sin sesión y una consulta a un perfil `DRAFT` no obtienen sus datos.

### Tests for User Story 1

- [x] T003 [P] [US1] Crear pruebas unitarias del cálculo `DRAFT`/`PUBLISHED`, guardado parcial, rechazo de cadenas vacías, teléfono `^\+?[0-9]{8,15}$` y protección de un perfil ya publicado en `backend/tests/test_trainer_service.py`
- [x] T004 [P] [US1] Crear pruebas de integración para `GET`/`PUT /api/v1/trainers/me/profile` y `GET /api/v1/trainers/{trainer_id}/profile`, cubriendo roles, autenticación, 404 para DRAFT y errores RFC 7807 en `backend/tests/test_trainer_api.py`

### Implementation for User Story 1

- [x] T005 [US1] Implementar `TrainerProfile` 1:1 con `User` en `backend/src/models/trainer_profile.py`: UUID, `user_id` único, `full_name` nullable String(150), `contact_phone` nullable String(50), `specialty` nullable String(100), `status` `DRAFT|PUBLISHED` con defecto `DRAFT`, `bio` y `certifications` nullable, `max_students` Integer con defecto 0, timestamps UTC
- [x] T006 [P] [US1] Implementar schemas de lectura y actualización parcial en `backend/src/schemas/trainer.py`, rechazando valores enviados vacíos y teléfonos fuera de `^\+?[0-9]{8,15}$`
- [x] T007 [US1] Implementar creación perezosa del perfil DRAFT, actualización parcial, transición a PUBLISHED solo con `full_name`, `contact_phone` y `specialty`, rechazo de incompletar un perfil publicado y consulta autenticada solo de PUBLISHED en `backend/src/services/trainer_service.py`
- [x] T008 [US1] Implementar `GET`/`PUT /api/v1/trainers/me/profile` solo para rol `TRAINER` y `GET /api/v1/trainers/{trainer_id}/profile` para cualquier usuario autenticado en `backend/src/api/v1/trainers.py`, preservando errores RFC 7807
- [x] T009 [P] [US1] Definir tipos, paths y cliente para perfiles en `frontend/src/types/trainer.ts`, `frontend/src/constants/routes.ts` y `frontend/src/services/trainerService.ts`
- [x] T010 [US1] Crear la pantalla responsive de edición y guardado parcial, con aviso DRAFT, estado PUBLISHED y errores por campo en `frontend/src/pages/TrainerProfileEditPage.tsx`
- [x] T011 [US1] Registrar la ruta protegida del entrenador y el acceso desde su inicio en `frontend/src/App.tsx` y `frontend/src/pages/HomePage.tsx`
- [x] T012 [P] [US1] Agregar estilos accesibles con contraste WCAG 2.1 AA y objetivos táctiles mínimos de 44×44 px en `frontend/src/styles/trainer-profile.css` y cargarla desde `frontend/src/styles.css`
- [x] T013 [US1] Ejecutar pruebas backend con cobertura ≥90%, Ruff, compilación frontend y recorrer el Escenario 1 de `taskify/specs/002-trainer-profile-and-plans/quickstart.md`

**Checkpoint**: US-02 funciona de punta a punta y puede entregarse en un PR independiente hacia `develop`.

---

## Phase 3: User Story 2 — US-03 Paquetes y tarifas (Priority: P1)

**Goal**: Permitir crear, editar y archivar paquetes mensuales sin alterar precios acordados previamente.

**Independent Test**: Un entrenador con perfil PUBLISHED crea un paquete válido, ARS se aplica por defecto, las tarifas fuera de `0..1.000.000` se rechazan y el archivado no modifica vínculos activos existentes.

- [x] T014 [P] [US2] Crear pruebas unitarias de tarifa, moneda, archivado y no retroactividad en `backend/tests/test_training_plan_service.py`
- [x] T015 [P] [US2] Crear pruebas de integración de creación, listado, edición y archivado en `backend/tests/test_training_plan_api.py`
- [x] T016 [US2] Implementar `TrainingPlan` en `backend/src/models/training_plan.py`: título String(100), descripción nullable, `monthly_price` Numeric(10,2) entre 0 y 1.000.000, `currency` String(3) con defecto `ARS`, `is_active` con defecto true y timestamps UTC
- [x] T017 [P] [US2] Agregar schemas de creación, actualización y respuesta de paquetes en `backend/src/schemas/trainer.py`
- [x] T018 [US2] Implementar reglas de publicación, edición, archivado y no retroactividad en `backend/src/services/trainer_service.py`
- [x] T019 [US2] Implementar endpoints autenticados de paquetes en `backend/src/api/v1/trainers.py`
- [x] T020 [P] [US2] Agregar tipos y operaciones de paquetes en `frontend/src/types/trainer.ts` y `frontend/src/services/trainerService.ts`
- [x] T021 [US2] Crear gestión responsive de paquetes con validaciones por campo en `frontend/src/pages/TrainerPlansManagementPage.tsx`, `frontend/src/components/PlanCard.tsx` y `frontend/src/styles/trainer-plans.css`
- [x] T022 [US2] Registrar rutas y navegación de paquetes en `frontend/src/App.tsx` y `frontend/src/constants/routes.ts`
- [x] T023 [US2] Ejecutar calidad automatizada y recorrer el Escenario 2 de `taskify/specs/002-trainer-profile-and-plans/quickstart.md`

---

## Phase 4: User Story 3 — US-04 Gestión de cupos (Priority: P1)

**Goal**: Configurar un máximo de 0 a 100 alumnos, calcular disponibilidad y bloquear solicitudes o aceptaciones cuando se agotan los cupos.

**Independent Test**: El entrenador configura el límite, el perfil muestra cupos disponibles y el backend rechaza nuevas solicitudes y aceptaciones pendientes cuando `active_students_count >= max_students`.

- [x] T024 [P] [US3] Crear pruebas unitarias de límites 0..100 y cálculo de disponibilidad (incluyendo conteo real de relaciones `ACTIVE` vs `TERMINATED`) en `backend/tests/test_trainer_quota_service.py`; la prueba de concurrencia en un proceso al aceptar solicitudes se incorpora en `backend/tests/test_trainer_requests_actions_api.py` junto con T026
- [x] T025 [P] [US3] Crear pruebas de integración para actualización de cupos, perfil publicado y bloqueo 409 en `backend/tests/test_trainer_quota_api.py`
- [x] T026 [US3] Integrar el conteo de relaciones activas y el bloqueo transaccional de aceptación en los modelos y servicios de vínculos correspondientes bajo `backend/src/models/` y `backend/src/services/`
  - ✅ Completado en US-07 (`spec 004`, tareas `T015`, `T016` y `T018`): `count_active_students` en `backend/src/services/trainer_service.py` consulta los vínculos `TrainingRelationship` con `status == 'ACTIVE'`, `TrainingRelationship` define el índice único parcial `uq_active_training_relationship` sobre `(student_id, trainer_id) WHERE status = 'ACTIVE'`, y `accept_training_request` en `backend/src/services/discovery_service.py` aplica bloqueo `with_for_update()` (efectivo a nivel de fila entre workers en PostgreSQL bajo `READ COMMITTED`) más `_REQUEST_RESOLUTION_LOCK` (efectivo entre hilos de un mismo proceso/worker y utilizado por los tests sobre SQLite en memoria, ya que SQLite omite `FOR UPDATE`).
- [x] T027 [P] [US3] Agregar schemas de cupo con `max_students` entre 0 y 100, `active_students`, `available_slots` y `has_available_quota` en `backend/src/schemas/trainer.py`
- [x] T028 [US3] Implementar actualización y cálculo de cupos en `backend/src/services/trainer_service.py` y `PATCH /api/v1/trainers/me/quota` en `backend/src/api/v1/trainers.py`
- [x] T029 [P] [US3] Crear `frontend/src/components/QuotaBadge.tsx` y operaciones de cupo en `frontend/src/services/trainerService.ts`
- [x] T030 [US3] Integrar edición y visualización accesible de cupos en las pantallas de perfil del entrenador bajo `frontend/src/pages/`
- [x] T031 [US3] Ejecutar calidad automatizada y recorrer el Escenario 3 de `taskify/specs/002-trainer-profile-and-plans/quickstart.md`

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Actualizar `README.md` con rutas y recorrido funcional del módulo de entrenador
- [ ] T033 Verificar que `taskify/specs/002-trainer-profile-and-plans/contracts/trainer-api.yaml` refleje todos los endpoints implementados y que todos los errores sigan RFC 7807
- [ ] T034 Ejecutar regresión completa, Ruff, cobertura backend ≥90%, compilación frontend y todos los escenarios de `taskify/specs/002-trainer-profile-and-plans/quickstart.md`

## Dependencies & Execution Order

- Setup → US-02 → PR hacia `develop`.
- US-03 comienza únicamente después de que US-02 esté revisada y mergeada en `develop`.
- US-04 requiere US-02 y los modelos de solicitudes/vínculos correspondientes integrados en `develop`.
- En `facundo-s1` se ejecutan T001–T013; el desglose de US-03 y US-04 se conserva completo para ramas futuras.

## Parallel Opportunities

- T003 y T004 pueden escribirse en paralelo antes de implementar US-02.
- T006, T009 y T012 afectan archivos distintos y pueden avanzar en paralelo después de T005.
- Las pruebas T014/T015 y T024/T025 son paralelizables dentro de sus historias.
- No se implementan historias distintas en la misma rama o PR.

## Implementation Strategy

1. Completar T001–T002.
2. Implementar y validar T003–T013 para entregar US-02 en `facundo-s1`.
3. Abrir PR de US-02 hacia `develop` y esperar su integración.
4. Crear ramas nuevas desde `develop` actualizado para US-03 y US-04.
