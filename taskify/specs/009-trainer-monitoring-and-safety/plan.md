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

---

# Plan Técnico: US-29 — Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo

**Branch**: `feature/us29-security-alerts` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Entrada**: US-29, Clarificaciones `Sesión 2026-11-14 — US-29` y requisitos transversales en [spec.md](./spec.md).

## Resumen del incremento US-29

Extender la arquitectura de monitoreo existente (US-18, US-22, US-26, US-28, US-32, US-60 y US-61) incorporando el ciclo completo de generación, persistencia, notificación, priorización, revisión y aviso al alumno para alertas de seguridad:

1. **Dolor (`PAIN`, CA-1)**: Al registrar un reporte en mapa corporal (`POST /api/v1/body-map-reports`, US-61), se crea sincrónicamente una `SafetyAlert(alert_type="PAIN")` por cada zona con `PAIN`, vinculada al alumno, relación activa, zona, ejercicio (en `IN_EXERCISE`) y sesión, manteniendo sin cambios la notificación `PAIN_ALERT` existente.
2. **Molestia repetida (`REPEATED_DISCOMFORT`, CA-2)**: Al registrar `DISCOMFORT` en una zona dentro de una sesión participante (`session_id` presente y `started_at` definido), evaluar cronológicamente la sesión participante inmediatamente anterior del mismo vínculo activo (iniciada y con actividad registrada, finalizada o sin finalizar); si también registró `DISCOMFORT` en la misma zona canónica (sin sesión participante intermedia que corte la secuencia), se crea `SafetyAlert(alert_type="REPEATED_DISCOMFORT")` y `Notification(type="REPEATED_DISCOMFORT_ALERT")`.
3. **Esfuerzo excesivo (`EXCESSIVE_EFFORT`, CA-3)**: Al persistirse `WorkoutSession.rpe` con valor `9` o `10` —tanto al finalizar la sesión (`finish_student_workout_session`) como por reporte diferido (`update_student_workout_session_rpe`)—, se crea `SafetyAlert(alert_type="EXCESSIVE_EFFORT", rpe=9|10)` y `Notification(type="EXCESSIVE_EFFORT_ALERT")` de forma idempotente.
4. **Priorización y revisión (CA-4)**: Exponer consultas y revisión explícita de alertas (`ADJUSTED_ROUTINE` = "Ajusté la rutina", `CONTACTED_STUDENT` = "Contacté al alumno", `NO_ACTION` = "Sin acción", más nota opcional hasta 500 caracteres) de modo independiente al `Notification.is_read`. En el listado de alumnos activos (`GET /api/v1/trainers/me/students` y `RoutineAssignmentPanel.tsx`), priorizar en tres niveles: (1) alumnos con alertas sin revisar de US-29, (2) alumnos con riesgo de abandono de US-32, (3) resto alfabético.
5. **Aviso al alumno en próxima sesión (CA-5)**: Exclusivamente cuando una alerta `PAIN` pasa a `REVIEWED`, exponerla en la próxima sesión abierta por el alumno (`StudentRoutinesPage.tsx` en `sessionMode`) junto con la nota del entrenador (si existe) y marcarla como vista (`student_seen_at`) en un único consumo.

## Verificación de la Constitución (US-29)

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Los badges de alertas sin revisar, controles de revisión (botones/radios con área >= 44 × 44 px, contraste >= 4.5 : 1) y banner de aviso al alumno conservan diseño responsivo y mensajes claros sin exponer trazas internas. |
| II. Participación humana | N/A / PASS | Las alertas asisten al entrenador sin modificar rutinas automáticamente; cualquier ajuste de rutina sigue siendo decisión explícita del entrenador (por ejemplo vía US-26 o edición de rutina). |
| III. Privacidad de salud | PASS | Los reportes de dolor/molestia y alertas se autorizan en el servidor verificando `TrainingRelationship.status == "ACTIVE"` y coincidencia con el perfil del entrenador o alumno autenticado. Al pasar el vínculo a `TERMINATED`, el entrenador anterior pierde acceso inmediato. |
| IV. Pagos informales | N/A | No involucra cobros ni registros de pago. |
| V. Medios externos | N/A | No incorpora archivos multimedia binarios. |
| VI. Verificación continua | PASS | Se especifican pruebas unitarias, de integración API, concurrencia/idempotencia, privacidad y regresión completa (`pytest` >= 90%, `ruff check`, `npm test`, `npm run build`). |
| VII. Entrega incremental | PASS | Alcance exclusivo de US-29 sobre la rama `feature/us29-security-alerts` desde `develop` actualizado, preservando contratos e invariantes de todas las historias previas. |

## Arquitectura propuesta y relación `SafetyAlert` vs. `Notification`

- **`SafetyAlert` (`safety_alerts`)** es el registro de estado clínico y operativo de cada alerta de seguridad. Posee `status` (`PENDING` | `REVIEWED`), `action_taken`, `trainer_note`, `created_at`, `reviewed_at`, `student_seen_at` y `dedup_key` única.
- **`Notification` (`notifications`)** actúa exclusivamente como canal de aviso en la campana del entrenador (`NotificationBell.tsx`, polling cada 30 s). Al hacer clic en una notificación de la campana se marca `Notification.is_read = true` y se navega hacia `/entrenador/alumnos?studentId=...&sessionId=...&eventId=...&eventType=...`, pero la `SafetyAlert` permanece en `PENDING` (destacada y priorizada en el listado de alumnos) hasta que el entrenador envíe su revisión explícita en `PATCH /api/v1/trainers/me/safety-alerts/{alert_id}/review`.
- **Inmediatez dentro de la infraestructura actual**: sin WebSocket ni SSE, la persistencia de `SafetyAlert` y `Notification` ocurre en la misma transacción de base de datos del reporte (`body_map_report_service.py` o `routine_template_service.py`). Cualquier recarga o consulta API refleja las alertas al instante y los componentes existentes (`NotificationBell.tsx` cada 30 s, `RoutineAssignmentPanel.tsx` cada 3 s en progreso abierto) propagan el aviso automáticamente.

## Persistencia y migraciones

- **Nuevo modelo SQLAlchemy**: `backend/src/models/safety_alert.py` (`SafetyAlert`, tabla `safety_alerts`), detallado en [data-model.md](./data-model.md).
- **Registro de modelo**: Exportar `SafetyAlert` en `backend/src/models/__init__.py` e incluirlo en el bloque de registro de modelos de `backend/src/main.py` (para que `Base.metadata.create_all` cree la tabla en despliegues y entornos de test, conforme al patrón seguido por `SessionAdjustment` en US-26).
- **Migraciones**: Verificar compatibilidad con bases de datos preexistentes en `backend/src/core/migrations.py` asegurando idempotencia en SQLite y PostgreSQL (sin destruir datos previos ni modificar columnas ajenas), con validación en `backend/tests/test_database_migrations.py`. No se agregan columnas a tablas de otras historias salvo que fuera requerido por índice; todo el estado nuevo reside en `safety_alerts`.

## Servicios de dominio y puntos de integración backend

- **Nuevo servicio `backend/src/services/safety_alert_service.py`**:
  - `create_pain_alerts_for_report(db, report, relationship, profile, exercise, session)` (CA-1): crea idempotentemente una `SafetyAlert(alert_type="PAIN")` por cada zona con `intensity == "PAIN"` (`dedup_key = f"PAIN:{report.id}:{zone}"`), manteniendo la notificación `PAIN_ALERT` de US-61 en `body_map_report_service.py`.
  - `evaluate_repeated_discomfort_alerts(db, report, relationship, profile, exercise, session)` (CA-2): si `report.session_id` está presente, `session.started_at` no es nulo y `relationship` está `ACTIVE`, para cada zona con `intensity == "DISCOMFORT"` consulta las sesiones participantes anteriores del mismo `relationship.id` ordenadas por `(started_at DESC, id DESC)` —exigiendo `WorkoutSession.started_at IS NOT NULL` y actividad registrada (`EXISTS(WorkoutSetLog)` o `EXISTS(BodyMapPainReport)`), contando también sesiones no finalizadas (`finished_at IS NULL`), y excluyendo sesiones creadas nunca iniciadas, sesiones sin actividad y reportes `POST_SESSION` con `session_id IS NULL`—, toma únicamente la sesión participante inmediatamente anterior (`previous_session`) y, si tuvo `DISCOMFORT` en esa misma zona canónica, crea `SafetyAlert(alert_type="REPEATED_DISCOMFORT", dedup_key=f"REPEATED_DISCOMFORT:{relationship.id}:{session.id}:{zone}")` y emite `Notification(type="REPEATED_DISCOMFORT_ALERT", ...)`. Dos o más reportes en la misma sesión siguen contando como una única sesión.
  - `create_excessive_effort_alert(db, session)` (CA-3): verifica vínculo `ACTIVE`, `session.rpe in (9, 10)` y crea de forma idempotente (`dedup_key = f"EXCESSIVE_EFFORT:{session.id}"`) `SafetyAlert(alert_type="EXCESSIVE_EFFORT", rpe=session.rpe, zone=None)` más `Notification(type="EXCESSIVE_EFFORT_ALERT", ...)`.
  - `list_trainer_safety_alerts(db, trainer_user, status=None, student_id=None)`: devuelve alertas filtradas por `TrainingRelationship.trainer_id == trainer.id` y `TrainingRelationship.status == "ACTIVE"`, ordenadas por `status == 'PENDING'` primero y `created_at DESC`, enriquecidas con nombre del alumno, día de sesión, ejercicio y nombre visible de zona (`ZONE_DISPLAY_NAMES`).
  - `review_safety_alert(db, trainer_user, alert_id, payload)`: valida vínculo `ACTIVE` del entrenador autenticado, persiste `status = "REVIEWED"`, `action_taken`, `trainer_note` (strip; cadena vacía → `None`), y `reviewed_at = utc_now()`. Si la alerta ya estaba revisada o no pertenece a un vínculo activo propio, aplica validación/estado HTTP coherente (`404`/`409`/`422` RFC 7807).
  - `unreviewed_alert_summary_by_relationship(db, relationship_ids)` y `student_safety_indicators(db, relationship_id)`: provee conteos de alertas pendientes (`unreviewed_alert_count`), marca temporal de la alerta pendiente más reciente y textos descriptivos para `TrainerStudentLimitations.safety_indicators` (US-18).
  - `list_student_reviewed_pain_notices(db, student_user)` y `mark_safety_alert_seen(db, student_user, alert_id)` (CA-5): filtra estrictamente `alert_type == "PAIN"`, `status == "REVIEWED"`, `student_seen_at IS NULL` (para el listado de pendientes) y `TrainingRelationship.status == "ACTIVE"`; marca `student_seen_at = utc_now()` de forma idempotente.
- **Integración con US-61 (`backend/src/services/body_map_report_service.py`)**: dentro del bloque transaccional `with db.begin_nested():` de `create_body_map_report`, tras persistir el reporte y emitir la `Notification(type="PAIN_ALERT")` existente, invocar `create_pain_alerts_for_report` y `evaluate_repeated_discomfort_alerts` usando la misma sesión de BD (`commit=False` dentro del helper hasta el `db.commit()` del servicio).
- **Integración con US-60 (`backend/src/services/routine_template_service.py`)**: en `finish_student_workout_session` (tanto cuando finaliza con `rpe` como cuando finaliza primero y recibe `rpe` luego desde `None`) y en `update_student_workout_session_rpe` (cuando `session.rpe` pasa de `None` a `9` o `10`), dentro del bloque con bloqueo pesimista `with_for_update()`, disparar `create_excessive_effort_alert(db, session)` antes del `db.commit()` (o atómicamente en esa transición) garantizando cero duplicados si se reenvía el mismo RPE.
- **Integración con US-18 y US-32 (`backend/src/services/trainer_student_service.py`)**:
  - `list_trainer_students`: poblar `unreviewed_alert_count` por vínculo activo (entero >= 0) y aplicar la clave de ordenamiento de 3 niveles: (1) `unreviewed_alert_count > 0` primero (`-unreviewed_alert_count`, `-latest_alert_ts`, orden alfabético), (2) `at_risk == True` de `list_abandonment_risk(db, user, notify=False)` manteniendo `days_without_report DESC`, (3) resto alfabético.
  - `get_trainer_student_detail`: poblar `limitations.safety_indicators` con un resumen legible de alertas de seguridad activas/pendientes del vínculo.
- **Integración con US-28 y US-22 / US-26**: US-28 conserva sin cambios sus consultas de historial (`PainReportAnalysis.tsx` y `list_trainer_student_zone_history`), y US-22/US-26 conservan `DailyRoutineItem` y `SessionAdjustment` intactos; si el entrenador elige "Ajusté la rutina" en US-26, puede además usar esa acción al revisar la alerta de seguridad desde `/entrenador/alumnos`.

## Endpoints y schemas

- **Schemas (`backend/src/schemas/safety_alert.py`)**: `SafetyAlertType`, `SafetyAlertStatus`, `SafetyAlertAction`, `SafetyAlertReviewRequest`, `SafetyAlertView`, `StudentPainAlertReviewedNotice`. Se mantiene compatibilidad hacia atrás con `TrainerStudentListItem` en `backend/src/schemas/trainer_student.py` (`unreviewed_alert_count: int | None = None` pasa a devolverse poblado como `int` >= 0).
- **Endpoints expuestos en `backend/src/api/v1/trainers.py` y `backend/src/api/v1/students.py`** (documentados en [trainer-student-detail-api.yaml](./contracts/trainer-student-detail-api.yaml)):
  - `GET /api/v1/trainers/me/safety-alerts` (`status`, `student_id` opcionales)
  - `GET /api/v1/trainers/me/students/{student_id}/safety-alerts`
  - `PATCH /api/v1/trainers/me/safety-alerts/{alert_id}/review`
  - `GET /api/v1/students/me/safety-alerts/reviewed-notices`
  - `POST /api/v1/students/me/safety-alerts/{alert_id}/seen`

## Integración con Frontend

- **Cliente y tipos**: nuevos `frontend/src/types/safetyAlert.ts` y `frontend/src/services/safetyAlertService.ts`; utilidades puras testeables en `frontend/src/utils/safetyAlerts.mjs` y composición de ordenamiento junto a `frontend/src/utils/abandonmentRisk.mjs`.
- **Listado de alumnos y revisión (`RoutineAssignmentPanel.tsx`, `TrainerStudentDetail.tsx`)**:
  - `RoutineAssignmentPanel.tsx` carga las alertas pendientes (`getTrainerSafetyAlerts({ status: 'PENDING' })`) junto a asignaciones, planes y riesgo de abandono (US-32).
  - Ordena `visibleStudents` mediante `sortBySafetyAndAbandonment` respetando US-29 > US-32 > orden alfabético y conservando la búsqueda de US-19 y el filtro por paquete de US-20.
  - Muestra a los alumnos con alertas sin revisar primero y destacados visualmente (badge con cantidad de alertas pendientes y acceso directo a la revisión), manteniendo el badge `"Riesgo de abandono"` de US-32 y los demás indicadores sin perder información.
  - Permite abrir y revisar cada alerta pendiente (mostrando tipo, alumno, zona, ejercicio, sesión y RPE) seleccionando obligatoriamente una de las tres acciones (`Ajusté la rutina`, `Contacté al alumno`, `Sin acción`) y nota opcional, actualizando el listado y la prioridad inmediatamente al confirmar.
  - Extiende el detalle del alumno (`TrainerStudentDetail.tsx`) para mostrar los `safety_indicators` y permitir consultar/revisar sus alertas sin salir del flujo de monitoreo.
- **Notificaciones y navegación (`frontend/src/constants/routes.ts`, `RoutineAssignmentPanel.tsx`)**: incorporar `REPEATED_DISCOMFORT_ALERT` y `EXCESSIVE_EFFORT_ALERT` (junto a `PAIN_ALERT`) en `trainerNotificationPath` para enlazar al alumno y sesión correspondiente en `/entrenador/alumnos`. Mantener el polling de 30 s en `NotificationBell.tsx` y de 3 s en progreso abierto de `RoutineAssignmentPanel.tsx`.
- **Aviso al alumno en próxima sesión (`frontend/src/pages/StudentRoutinesPage.tsx`)**:
  - Al ingresar en `sessionMode`, consultar `getStudentReviewedPainNotices()`. Si existen avisos pendientes (solo `PAIN` revisados), mostrar un banner destacado sobre la sesión activa indicando el reporte revisado (zona, ejercicio/sesión), la acción tomada por el entrenador y la nota del entrenador cuando exista (omitiendo nota vacía si es nula).
  - Invocar `markSafetyAlertSeen(alert.id)` al mostrarse en la sesión para consumir el aviso una única vez sin ocultarlo prematuramente dentro de la sesión actual.

## Estructura de artefactos afectados por US-29

```text
backend/
├── src/
│   ├── models/
│   │   ├── safety_alert.py          # Nuevo modelo SafetyAlert
│   │   └── __init__.py              # Exportar SafetyAlert
│   ├── main.py                      # Registrar SafetyAlert en create_app
│   ├── core/migrations.py           # Verificación idempotente de esquema
│   ├── schemas/safety_alert.py      # Schemas de alerta, revisión y aviso alumno
│   ├── services/
│   │   ├── safety_alert_service.py  # Lógica de dominio US-29 (CA-1..CA-5)
│   │   ├── body_map_report_service.py # Hooks CA-1 (PAIN) y CA-2 (DISCOMFORT consecutivo)
│   │   ├── routine_template_service.py # Hook CA-3 (RPE 9/10 en finish y rpe update)
│   │   └── trainer_student_service.py # Priorización US-29 > US-32 + unreviewed_alert_count
│   └── api/v1/
│       ├── trainers.py              # Endpoints trainer de listado y revisión de alertas
│       └── students.py              # Endpoints alumno de avisos PAIN revisados (CA-5)
└── tests/
    └── test_us29_safety_alerts_api.py
frontend/
└── src/
    ├── types/safetyAlert.ts
    ├── services/safetyAlertService.ts
    ├── utils/safetyAlerts.mjs
    ├── utils/safetyAlerts.test.mjs
    ├── utils/abandonmentRisk.mjs
    ├── utils/abandonmentRisk.test.mjs
    ├── constants/routes.ts
    ├── components/RoutineAssignmentPanel.tsx
    ├── components/TrainerStudentDetail.tsx
    └── pages/StudentRoutinesPage.tsx
```

## Estrategia de pruebas

1. **Pruebas unitarias y de integración backend (`backend/tests/test_us29_safety_alerts_api.py`)**:
   - **CA-1**: Dolor `IN_EXERCISE` y `POST_SESSION` (simple y multizona) crea `SafetyAlert(PAIN)` con alumno, zona, ejercicio/sesión y mantiene intacta la notificación `PAIN_ALERT` de US-61.
   - **CA-2**: Molestia en la misma zona en 2 sesiones participantes consecutivas genera alerta y notificación `REPEATED_DISCOMFORT_ALERT`; reportes `NORMAL` no generan alerta; (i) sesión intermedia iniciada, con actividad y sin molestia en la zona interrumpe la secuencia (Sesión 1 molestia + Sesión 2 sin molestia + Sesión 3 molestia => sin alerta); (ii) sesión intermedia iniciada, con actividad, sin finalizar (`finished_at IS NULL`) y sin molestia en la zona también cuenta e interrumpe la secuencia; (iii) sesión creada pero nunca iniciada (`started_at IS NULL`) no cuenta ni interrumpe; (iv) sesión sin actividad registrada (`WorkoutSetLog` ni `BodyMapPainReport`) no cuenta ni interrumpe; (v) dos o más reportes de molestia en la misma zona dentro de una misma sesión cuentan como 1 sesión y no disparan CA-2; reportes `POST_SESSION` históricos sin `session_id` no participan de la secuencia.
   - **CA-3**: RPE 9 y RPE 10 generan alerta tanto en `finish_student_workout_session` como en `update_student_workout_session_rpe`; RPE <= 8 no genera alerta; reenvíos idempotentes y concurrencia no duplican la alerta.
   - **CA-4**: Priorización en `/api/v1/trainers/me/students`: alertas sin revisar (US-29) preceden a riesgo de abandono (US-32) y al resto; marcar notificación como leída (`is_read = true`) NO revisa la `SafetyAlert`; revisar exige una de las 3 acciones (`ADJUSTED_ROUTINE`, `CONTACTED_STUDENT`, `NO_ACTION`) y nota opcional, reduciendo `unreviewed_alert_count` y quitando la prioridad destacada al quedar en 0.
   - **CA-5**: Aviso en próxima sesión se devuelve y consume (`seen`) exclusivamente para alertas `PAIN` revisadas (con y sin nota); nunca se expone para `REPEATED_DISCOMFORT` ni `EXCESSIVE_EFFORT`.
   - **Seguridad y aislamiento**: Entrenador ajeno recibe `403`/`404` RFC 7807; al pasar un vínculo a `TERMINATED` se revoca el acceso y al iniciar vínculo con otro entrenador no se heredan rachas ni alertas previas.
2. **Pruebas unitarias frontend (`npm test`)**: ordenamiento combinado US-29 > US-32 > alfabético, mapeo de acciones, formateo de avisos al alumno (`PAIN` únicamente) y regresión de `abandonmentRisk.test.mjs`.
3. **Regresión y calidad CI**: `pytest` completo (incluyendo US-61, US-60, US-28, US-32, US-18, US-22, US-26 y `test_database_migrations.py`), `ruff check backend`, `npm test` y `npm run build` en `frontend/`.
