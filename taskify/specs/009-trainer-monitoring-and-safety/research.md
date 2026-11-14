# Investigación: US-18 — Visualización de alumnos activos

## Alcance e implementación existente

- Decisión: extender el flujo existente de “Mis alumnos” en lugar de crear una segunda sección.
- Justificación: `TrainerStudentsPage` ya renderiza `RoutineAssignmentPanel`, que lista los vínculos activos, asigna rutinas, abre el progreso y muestra indicadores de sesiones/reportes.
- Alternativas consideradas: se rechazó un nuevo panel independiente de alumnos porque duplicaría el listado, el contexto de autorización, las acciones de rutinas y la interfaz de progreso.

## Autorización

- Decisión: cada consulta de listado y detalle debe limitarse al perfil del entrenador autenticado y a `TrainingRelationship.status == "ACTIVE"`.
- Justificación: este es el invariante existente del vínculo y lo exige el Principio III de la Constitución. El ID de un alumno por sí solo nunca debe autorizar el acceso.
- Alternativas consideradas: se rechazó reutilizar desde el frontend los endpoints de autoservicio del alumno porque no son un agregado orientado al entrenador y harían que la protección de la privacidad dependiera de la composición del cliente.

## Modelo de lectura

- Decisión: agregar un agregado orientado a lectura para el detalle del alumno del entrenador, respaldado por modelos y servicios existentes.
- Justificación: la respuesta actual de asignación solo contiene nombre, vínculo, asignación de rutina y cantidad de conflictos. US-18 también necesita paquete, perfil, objetivos, zonas protegidas, rutina vigente y un resumen compacto de actividad.
- Alternativas consideradas: se rechazó agregar campos no relacionados a cada respuesta de asignación de rutina porque acoplaría los payloads de asignación a la vista de monitoreo.

## Límite de métricas

- Decisión: US-18 expone únicamente un resumen compacto de actividad: cantidad de sesiones finalizadas, marca de tiempo de la última sesión, cantidad de series registradas, último RPE y tonelaje de la última sesión.
- Justificación: estos valores ya están representados por las sesiones/registros de entrenamiento y el servicio existente de resumen de sesiones. Los gráficos, las comparaciones históricas, los filtros y el análisis de tendencias pertenecen a US-24 y US-30.
- Alternativas consideradas: se rechazó implementar un nuevo gráfico o consulta analítica porque ampliaría el alcance.

## Datos del paquete y la rutina

- Decisión: leer el paquete contratado mediante `TrainingRelationship.plan_id`, `agreed_monthly_price` y `agreed_currency`; resolver la rutina vigente mediante la lógica existente de asignaciones/rutinas del alumno.
- Justificación: el vínculo almacena la fotografía comercial acordada, evitando que cambios retroactivos en el precio del paquete afecten a los alumnos activos.
- Alternativas consideradas: se rechazó leer el catálogo actual de paquetes del entrenador porque podría mostrar un precio diferente del paquete acordado con el alumno.

## Límite de alertas

- Decisión: no implementar el ordenamiento de alertas ni el estado de revisión en el incremento de US-18.
- Justificación: la especificación actual de la feature asigna la generación de alertas y su ciclo de revisión a US-29. US-18 dejará un punto claro de integración para un futuro campo `unreviewed_alert_count`/priority.
- Alternativas consideradas: se rechazó inferir el estado de una alerta a partir del texto de una notificación o de la presencia de un reporte porque produciría una semántica de revisión incorrecta.

---

## Decisiones técnicas — US-29: Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo

### Decisión 9 — Entidad persistente `SafetyAlert` separada de `Notification`

- **Decisión**: Modelar `SafetyAlert` (`safety_alerts`) como entidad persistente de dominio independiente de `Notification` (`notifications`).
- **Justificación**: En la arquitectura actual (`frontend/src/components/NotificationBell.tsx`), al hacer clic sobre una notificación se llama inmediatamente a `PATCH /api/v1/trainers/me/notifications/{id}/read`, marcando `Notification.is_read = true` antes de que el entrenador evalúe la clínica del alumno o decida una acción. Si el estado "Revisada" de CA-4 dependiera de `Notification.is_read`, el alumno dejaría de figurar destacado en el listado antes de que el entrenador seleccione la acción tomada (`Ajusté la rutina`, `Contacté al alumno` o `Sin acción`) y la nota opcional. Asimismo, CA-5 exige rastrear por separado si el alumno ya vio la revisión en su próxima sesión (`student_seen_at`) únicamente para alertas originadas por dolor (`PAIN`).
- **Alternativas consideradas**:
  - Reutilizar `Notification` agregándole columnas de revisión: rechazada porque mezcla un buzón genérico efímero (usado para solicitudes, récords, zonas protegidas y abandono) con una entidad clínica auditada que posee estado propio, nota, acción obligatoria, clave de deduplicación y seguimiento de lectura por el alumno.
  - Reutilizar `SessionAdjustment` (US-26): rechazada porque el entrenador puede marcar una alerta como `Contacté al alumno` o `Sin acción` sin ajustar ninguna rutina ni esperar a sesiones en curso.

### Decisión 10 — Preservación del contrato `PAIN_ALERT` de US-61 y notificaciones de US-29

- **Decisión**: Conservar intacta la creación de `Notification(type="PAIN_ALERT", ...)` dentro de `create_body_map_report` (`backend/src/services/body_map_report_service.py`) y emitir además las notificaciones de US-29 `REPEATED_DISCOMFORT_ALERT` (CA-2) y `EXCESSIVE_EFFORT_ALERT` (CA-3) en forma sincrónica en la misma transacción que crea la `SafetyAlert`. Para "notificación inmediata" dentro de la arquitectura actual sin WebSocket/SSE, se garantiza consistencia transaccional inmediata en las APIs de consulta, reflejada automáticamente en UI mediante el polling existente de `NotificationBell.tsx` (30 s) y del panel de progreso de `RoutineAssignmentPanel.tsx` (3 s).
- **Justificación**: `backend/tests/test_us61_body_map_pain_report_api.py` (`test_notification_alert_generated_on_pain_classification`) verifica exactamente los campos `type="PAIN_ALERT"`, `title="Alerta de dolor reportado"`, `related_entity_type="BODY_MAP_PAIN_REPORT"`, `related_entity_id=report.id`, `related_student_id` y `related_session_id`. Mantener esa única `Notification` por reporte con zonas `PAIN` preserva retrocompatibilidad 100%, mientras se crea una `SafetyAlert(alert_type="PAIN")` por cada zona con `intensity="PAIN"` para permitir seguimiento y revisión por zona, ejercicio y sesión (CA-1).
- **Alternativas consideradas**: Introducir WebSockets/SSE; descartada porque excede el alcance de US-29 y la infraestructura vigente ya opera mediante REST + polling explícito.

### Decisión 11 — Algoritmo de detección de molestias en 2 sesiones consecutivas (CA-2)

- **Decisión**: Al persistir un `BodyMapPainReport` con al menos una zona `intensity="DISCOMFORT"` asociado a una `WorkoutSession` (`session_id` presente y `WorkoutSession.started_at IS NOT NULL`) dentro de un vínculo `ACTIVE`, evaluar por cada zona con `DISCOMFORT`:
  1. Obtener la lista cronológica de sesiones participantes anteriores del mismo `relationship_id` con `(WorkoutSession.started_at, WorkoutSession.id) < (current_session.started_at, current_session.id)` (ordenadas descendentemente por `started_at DESC, id DESC`), donde una sesión se considera participante únicamente si cumple ambas condiciones:
     - Fue **iniciada** (`WorkoutSession.started_at IS NOT NULL`).
     - Tiene **actividad registrada** (existe al menos un `WorkoutSetLog` o un `BodyMapPainReport` asociado a esa sesión).
     - Cuenta **aunque no haya sido finalizada** (`finished_at IS NULL` o `finished_at IS NOT NULL`, indistintamente, siempre que cumpla las dos condiciones anteriores).
     - Quedan **excluidas**: sesiones creadas pero nunca iniciadas (`started_at IS NULL`), sesiones sin actividad registrada (sin `WorkoutSetLog` ni `BodyMapPainReport`, incluso si cerradas vacías) y reportes históricos `POST_SESSION` con `session_id IS NULL` (por no poder asociarse a una sesión concreta).
  2. Inspeccionar únicamente la sesión participante inmediatamente anterior (`previous_session`) a `current_session`.
  3. Verificar si `previous_session` contiene al menos un `BodyMapPainReportZone` con `zone == target_zone` y `intensity == "DISCOMFORT"`.
  4. Solo si cumple (3), crear `SafetyAlert(alert_type="REPEATED_DISCOMFORT", zone=target_zone, session_id=current_session.id, report_id=report.id)` y la `Notification(type="REPEATED_DISCOMFORT_ALERT")`.
- **Justificación**: Cumple estrictamente la regla definitiva de consecutividad: toda sesión intermedia iniciada y con actividad registrada sin `DISCOMFORT` en esa zona (sin reportes de dolor/molestia, con `NORMAL`, con `PAIN` sin `DISCOMFORT`, o con molestia en otra zona), finalizada o sin finalizar, aparece como `previous_session`, no cumple el paso 3 e interrumpe la secuencia. En cambio, sesiones planificadas nunca iniciadas o vacías sin actividad no introducen falsos cortes. Dos o más reportes de molestia en la misma zona dentro de la misma `current_session.id` siguen contando como una sola sesión porque el paso 1 busca estrictamente sesiones anteriores distintas de `current_session.id` y la clave de deduplicación `REPEATED_DISCOMFORT:{relationship_id}:{current_session.id}:{zone}` garantiza unicidad por sesión y zona. Los escenarios de prueba verifican sesión intermedia iniciada con actividad y sin molestia (finalizada y sin finalizar), sesión creada sin iniciar, sesión sin actividad y doble reporte en una misma sesión.
- **Alternativas consideradas**: Contar los últimos 2 registros históricos de `BodyMapPainReportZone`, incluir sesiones por `finished_at IS NOT NULL` sin exigir actividad, o excluir sesiones no finalizadas con actividad; rechazadas porque producen falsos positivos con reportes de la misma sesión o `POST_SESSION` sin `session_id`, o distorsionan la secuencia con sesiones vacías o activas sin finalizar.

### Decisión 12 — Enganche dual e idempotente para RPE 9/10 (CA-3)

- **Decisión**: Invocar la generación de `SafetyAlert(alert_type="EXCESSIVE_EFFORT", rpe=session.rpe, zone=None)` + `Notification(type="EXCESSIVE_EFFORT_ALERT")` tanto en `finish_student_workout_session` como en `update_student_workout_session_rpe` (`backend/src/services/routine_template_service.py`) dentro del alcance protegido por `with_for_update()` cuando la sesión registra `rpe in (9, 10)` por primera vez (`previous_rpe is None`) y mientras exista un vínculo `ACTIVE` coincidente.
- **Justificación**: En US-60 existen dos flujos reales para reportar el RPE (`POST .../finish` con RPE incluido y `PATCH`/`POST .../rpe` diferido desde el modal resumen o el recordatorio). Ambas funciones bloquean la fila de `WorkoutSession` con `with_for_update()` y devuelven la sesión idempotente si `session.rpe == rpe` (o `409 Conflict` si difiere). Verificar el estado previo + unicidad `EXCESSIVE_EFFORT:{session.id}` garantiza exactamente una alerta por sesión ante reintentos o concurrencia.
- **Alternativas consideradas**: Emitir la alerta únicamente en `update_student_workout_session_rpe`; rechazada porque omitiría los reportes RPE 9/10 enviados directamente al finalizar la sesión.

### Decisión 13 — Priorización de 3 niveles en listado de alumnos (US-18 + US-29 + US-32)

- **Decisión**: Integrar el ordenamiento de alumnos activos en backend (`list_trainer_students` en `backend/src/services/trainer_student_service.py`) y en frontend (`RoutineAssignmentPanel.tsx`, ampliando la lógica compartida de `frontend/src/utils/abandonmentRisk.mjs` / nueva utilidad `frontend/src/utils/safetyAlerts.mjs`):
  1. **Prioridad 1 (US-29)**: Alumnos con `unreviewed_alert_count > 0`, ordenados por mayor cantidad de alertas pendientes (`-unreviewed_alert_count`), alerta pendiente más reciente (`latest_unreviewed_alert_at DESC`) y desempate estable/alfabético.
  2. **Prioridad 2 (US-32)**: Alumnos sin alertas de seguridad pendientes (`unreviewed_alert_count == 0`) pero con riesgo de abandono activo (`at_risk == true`), manteniendo su orden por `days_without_report DESC` y desempate alfabético.
  3. **Prioridad 3**: Resto de alumnos activos en orden alfabético.
- **Justificación**: Satisface explícitamente la Decisión Confirmada 1, utiliza el campo ya reservado `unreviewed_alert_count` en `TrainerStudentListItem` (`backend/src/schemas/trainer_student.py`) y preserva intacto el cálculo y badge `"Riesgo de abandono"` de US-32 (`test_us32_abandonment_risk_api.py` sigue pasando cuando no hay alertas de seguridad pendientes).
- **Alternativas consideradas**: Reemplazar el badge de abandono por el de alertas; rechazada por mandato expreso de conservar ambos indicadores y su prioridad secundaria.

### Decisión 14 — Aviso al alumno en su próxima sesión exclusivo para `PAIN` (CA-5)

- **Decisión**: Seguir el patrón probado de US-64 (`EffortFeedback` en `StudentRoutinesPage.tsx` cuando `sessionMode === true`):
  - Exponer `GET /api/v1/students/me/safety-alerts/reviewed-notices` filtrando exclusivamente `alert_type == "PAIN"`, `status == "REVIEWED"`, `student_seen_at IS NULL` y `TrainingRelationship.status == "ACTIVE"`.
  - Cuando el alumno entra a su próxima sesión de entrenamiento (`sessionMode`), la pantalla obtiene los avisos pendientes de dolor revisado, renderiza el banner informativo (indicando la zona, ejercicio/sesión, que fue revisado por su entrenador, la acción tomada y la nota del entrenador solo si `trainer_note` no es nula) y dispara `POST /api/v1/students/me/safety-alerts/{alert_id}/seen` para persistir `student_seen_at`, consumiendo el aviso una única vez.
- **Justificación**: Cumple la Decisión Confirmada 2 (exclusivo para `PAIN`, excluido para `REPEATED_DISCOMFORT` y `EXCESSIVE_EFFORT`) y reutiliza un flujo ya familiar para el alumno en `StudentRoutinesPage.tsx` sin acoplar el ciclo de vida de alertas al modelo de ajustes de rutina (`SessionAdjustment`) ni ocultar revisiones sin nota.
- **Alternativas consideradas**: Reutilizar `SessionAdjustment` o mostrar notificaciones genéricas; rechazada porque `SessionAdjustment` solo existe cuando se modifica una rutina del día y dura hasta finalizar ese día específico, mientras CA-5 exige mostrar la revisión en la próxima sesión incluso cuando el entrenador eligió "Contacté al alumno" o "Sin acción".

### Decisión 15 — Aislamiento entre entrenadores, cambio de vínculo y deduplicación

- **Decisión**: Todas las consultas, conteos (`unreviewed_alert_count`), revisiones y cálculos de consecutividad filtran obligatoriamente por `TrainingRelationship.status == "ACTIVE"` y `TrainingRelationship.trainer_id == trainer_profile.id` en el servidor (Principio III de la Constitución). Ante una terminación o cambio de entrenador (`status = "TERMINATED"`), el entrenador saliente pierde acceso inmediato a las alertas del alumno, y el nuevo vínculo (`relationship_id` distinto) inicia sin heredar sesiones ni secuencias previas de molestias. Además, la columna única `dedup_key` en `safety_alerts` respalda en base de datos la idempotencia ante condiciones de carrera y reintentos.
- **Justificación**: Garantiza privacidad de datos sensibles de salud, previene escalamiento de privilegios (IDOR) y mantiene la integridad estadística ante concurrencia en SQLite y PostgreSQL.
- **Alternativas consideradas**: Filtrar por `student_id` únicamente; rechazada porque violaría el Principio III al mezclar historiales clínicos entre distintos entrenadores o vínculos cerrados.
