# Modelo de datos: US-18 — Resumen del alumno para el entrenador

US-18 no agrega tablas de base de datos. El modelo de lectura de la API compone entidades existentes.

## Entidades existentes

### TrainingRelationship

- Identifica el vínculo entre el entrenador y el alumno.
- Alcance requerido: `trainer_id` coincide con el perfil del entrenador autenticado y `status` es `ACTIVE`.
- Proporciona `plan_id`, `agreed_monthly_price`, `agreed_currency`, `start_date` e `initial_routine_id`.

### StudentProfile

- Proporciona nombre, apellido, fecha de nacimiento, imagen de perfil, biografía, objetivos físicos y estado del perfil.
- `protected_zones` se cargan únicamente después de verificar la autorización del vínculo activo.

### TrainingPlan

- Resuelve el paquete contratado originalmente mediante el vínculo.
- El precio y la moneda mostrados provienen del acuerdo del vínculo, no del precio actual del catálogo.

### Asignación de rutina

- Los datos existentes de `RoutineTemplate`, `AssignedRoutine` y `StudentRoutine` proporcionan la rutina asignada vigente.
- La respuesta de detalle no debe exponer una rutina en borrador como rutina actual del alumno.

### Datos de actividad

- Los registros existentes de `WorkoutSession` proporcionan las sesiones completadas y la marca de tiempo/RPE de la última sesión.
- Los registros existentes de `WorkoutSetLog` proporcionan la cantidad de series registradas y los datos para calcular el tonelaje de la última sesión.
- Los reportes existentes de esfuerzo y del mapa corporal siguen disponibles mediante sus servicios y endpoints actuales; US-18 no cambia su ciclo de vida.

## Modelos de lectura de la API

### TrainerStudentListItem

- `relationship_id`
- `student_id`
- `full_name`
- `profile_status`
- `package_title`
- `routine_name` anulable
- `has_activity`
- `unreviewed_alert_count` anulable/reservado para la integración de US-29; debe permanecer en `0` u omitirse hasta que exista esa historia

### TrainerStudentDetail

- `relationship`: ID del vínculo, estado, fecha de inicio, precio y moneda acordados del paquete
- `profile`: campos existentes del perfil del alumno apropiados para un entrenador autorizado
- `goals`: objetivos físicos y motivación
- `limitations`: nombres normalizados de zonas protegidas e indicadores de seguridad existentes
- `routine`: resumen de la rutina vigente y referencia al detalle existente de la rutina
- `metrics`: `finished_sessions`, `last_session_at`, `logged_sets`, `last_rpe`, `last_tonnage_kg`
- `available_existing_views`: referencias/identificadores necesarios para los componentes actuales de rutina, reportes y progreso

## Invariantes

1. Un elemento del listado o detalle solo puede devolverse para un vínculo activo perteneciente al entrenador autenticado.
2. Los vínculos terminados y vencidos quedan excluidos.
3. El precio del paquete mostrado para un alumno activo es el precio acordado en el vínculo.
4. El perfil, la rutina, la actividad, los objetivos o las zonas protegidas faltantes se representan como datos vacíos/nulos, no mediante valores predeterminados inventados.
5. US-18 no introduce ninguna operación de escritura.

---

# Modelo de datos: US-29 — Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo

## Justificación del diseño: `SafetyAlert` separada de `Notification`

`SafetyAlert` DEBE implementarse como entidad persistente propia (tabla `safety_alerts`) separada de `Notification` (`notifications`) por razones funcionales y técnicas verificadas en el sistema:

1. **Independencia entre lectura de notificación y revisión clínica**: En `frontend/src/components/NotificationBell.tsx`, al hacer clic sobre cualquier notificación se invoca `PATCH /api/v1/trainers/me/notifications/{id}/read`, lo que marca `Notification.is_read = true` antes de que el entrenador revise el reporte del alumno o decida una acción. Usar `Notification.is_read` violaría el CA-4, ya que quitaría el destacado del alumno antes de registrar la acción tomada (`Ajusté la rutina`, `Contacté al alumno`, `Sin acción`).
2. **Semántica clínica y campos específicos**: Una alerta requiere persistir `alert_type`, `zone` canónica, `rpe`, `report_id`, `session_id`, `exercise_id`, `action_taken`, `trainer_note`, `reviewed_at` y `student_seen_at` (CA-5 exclusivo para `PAIN`), además de una clave determinística `dedup_key` para unicidad ante reintentos y concurrencia.
3. **Preservación de contratos anteriores**: Mantener `Notification` como canal de aviso permite conservar intacta la notificación `PAIN_ALERT` exigida por los tests de US-61 (`related_entity_type = "BODY_MAP_PAIN_REPORT"`) mientras `SafetyAlert` gobierna la priorización del listado, el ciclo de revisión y el aviso de CA-5.

## Nueva entidad: `SafetyAlert` (`safety_alerts`)

### Atributos

| Campo | Tipo lógico / SQL | Nulable | Default / Regla | Descripción y FK |
|---|---|---|---|---|
| `id` | `VARCHAR(36)` (UUID) | No | `new_id` (PK) | Identificador único de la alerta. |
| `relationship_id` | `VARCHAR(36)` | No | Indexado | FK → `training_relationships.id` (`ON DELETE CASCADE`). Acota la alerta al vínculo activo en que ocurrió. |
| `trainer_id` | `VARCHAR(36)` | No | Indexado | FK → `trainer_profiles.id` (`ON DELETE CASCADE`). Entrenador titular del vínculo. |
| `student_id` | `VARCHAR(36)` | No | Indexado | FK → `student_profiles.id` (`ON DELETE CASCADE`). Alumno que originó el reporte. |
| `session_id` | `VARCHAR(36)` | Sí | Indexado | FK → `workout_sessions.id` (`ON DELETE SET NULL`). Sesión asociada (`IN_EXERCISE`, `POST_SESSION` con sesión, o `EXCESSIVE_EFFORT`). |
| `report_id` | `VARCHAR(36)` | Sí | Indexado | FK → `body_map_pain_reports.id` (`ON DELETE CASCADE`). Reporte de mapa corporal que originó `PAIN` o `REPEATED_DISCOMFORT`; `NULL` en `EXCESSIVE_EFFORT`. |
| `exercise_id` | `VARCHAR(36)` | Sí | — | FK → `exercises.id` (`ON DELETE SET NULL`). Ejercicio donde se reportó dolor/molestia en contexto `IN_EXERCISE`; `NULL` en `POST_SESSION` o `EXCESSIVE_EFFORT`. |
| `alert_type` | `VARCHAR(32)` | No | `PAIN` \| `REPEATED_DISCOMFORT` \| `EXCESSIVE_EFFORT` | Origen de la alerta (CA-1, CA-2 o CA-3). |
| `zone` | `VARCHAR(60)` | Sí | Canónica `BODY_AREAS` o `NULL` | Zona corporal afectada para `PAIN` y `REPEATED_DISCOMFORT`; `NULL` para `EXCESSIVE_EFFORT`. |
| `rpe` | `INTEGER` | Sí | `9` \| `10` o `NULL` | Esfuerzo percibido reportado cuando `alert_type == 'EXCESSIVE_EFFORT'`; `NULL` en otros tipos. |
| `dedup_key` | `VARCHAR(160)` | No | Único (`UNIQUE`) | Clave determinística de idempotencia y deduplicación. |
| `status` | `VARCHAR(16)` | No | `'PENDING'` | Estado de revisión (`PENDING` o `REVIEWED`). |
| `action_taken` | `VARCHAR(32)` | Sí | `NULL` | Acción elegida al revisar (`ADJUSTED_ROUTINE`, `CONTACTED_STUDENT`, `NO_ACTION`). |
| `trainer_note` | `VARCHAR(500)` | Sí | `NULL` | Nota opcional del entrenador al revisar (máximo 500 caracteres). |
| `created_at` | `DATETIME(timezone=True)` | No | UTC | Marca temporal de creación de la alerta (UTC). |
| `reviewed_at` | `DATETIME(timezone=True)` | Sí | `NULL` | Marca temporal UTC en que se marcó como `REVIEWED`. |
| `student_seen_at` | `DATETIME(timezone=True)` | Sí | `NULL` | Marca temporal UTC en que el alumno visualizó el aviso en su próxima sesión (solo aplica a `PAIN` revisadas). |

### Claves de unicidad (`dedup_key`), restricciones e índices

- **Formato determinístico de `dedup_key`**:
  - `PAIN`: `PAIN:{report_id}:{zone}` (garantiza a lo sumo una alerta por zona con dolor dentro de un mismo `BodyMapPainReport`, permitiendo reportes multizona independientes).
  - `REPEATED_DISCOMFORT`: `REPEATED_DISCOMFORT:{relationship_id}:{session_id}:{zone}` (garantiza a lo sumo una alerta por zona y sesión cuando se cumplen 2 sesiones consecutivas, evitando duplicados ante múltiples reportes `IN_EXERCISE`/`POST_SESSION` de la misma zona dentro de esa misma sesión).
  - `EXCESSIVE_EFFORT`: `EXCESSIVE_EFFORT:{session_id}` (garantiza a lo sumo una alerta por `WorkoutSession` con RPE 9 o 10, tanto si llega al finalizar la sesión como por reporte diferido).
- **Restricciones de tabla (`__table_args__`)**:
  - `UniqueConstraint("dedup_key", name="uq_safety_alerts_dedup_key")`
  - `CheckConstraint("alert_type IN ('PAIN', 'REPEATED_DISCOMFORT', 'EXCESSIVE_EFFORT')", name="ck_safety_alerts_type")`
  - `CheckConstraint("status IN ('PENDING', 'REVIEWED')", name="ck_safety_alerts_status")`
  - `CheckConstraint("action_taken IS NULL OR action_taken IN ('ADJUSTED_ROUTINE', 'CONTACTED_STUDENT', 'NO_ACTION')", name="ck_safety_alerts_action")`
  - `CheckConstraint("rpe IS NULL OR rpe IN (9, 10)", name="ck_safety_alerts_rpe")`
  - `Index("ix_safety_alerts_trainer_status_created", "trainer_id", "status", "created_at")`
  - `Index("ix_safety_alerts_relationship_status", "relationship_id", "status")`

### Relaciones con entidades existentes

- `SafetyAlert.relationship` → `TrainingRelationship` (N:1).
- `SafetyAlert.trainer` → `TrainerProfile` (N:1).
- `SafetyAlert.student` → `StudentProfile` (N:1).
- `SafetyAlert.session` → `WorkoutSession` (N:1 opcional).
- `SafetyAlert.report` → `BodyMapPainReport` (N:1 opcional).
- `SafetyAlert.exercise` → `Exercise` (N:1 opcional).
- Vínculo lógico con `Notification`:
  - `PAIN`: conserva `Notification(type="PAIN_ALERT", related_entity_type="BODY_MAP_PAIN_REPORT", related_entity_id=report.id, ...)` por reporte (US-61).
  - `REPEATED_DISCOMFORT`: emite `Notification(type="REPEATED_DISCOMFORT_ALERT", related_entity_type="SAFETY_ALERT", related_entity_id=alert.id, related_student_id=student_id, related_session_id=session_id)`.
  - `EXCESSIVE_EFFORT`: emite `Notification(type="EXCESSIVE_EFFORT_ALERT", related_entity_type="SAFETY_ALERT", related_entity_id=alert.id, related_student_id=student_id, related_session_id=session_id)`.

## Estados y ciclo de vida

```text
[Creación sincrónica] ---> PENDING
                              │
  Entrenador revisa (CA-4)    │ (action_taken requerido + trainer_note opcional)
                              ▼
                           REVIEWED  (reviewed_at != NULL, action_taken != NULL)
                              │
  Solo si alert_type == PAIN  │ Alumno abre próxima sesión (CA-5)
                              ▼
                     student_seen_at != NULL  (aviso consumido una sola vez)
```

## Reglas de integridad y actualización de modelos de lectura

1. **Integridad de revisión**: Ninguna alerta puede pasar a `REVIEWED` con `action_taken IS NULL`, ni sin establecer `reviewed_at`.
2. **Exclusividad de aviso al alumno (CA-5)**: Las consultas de avisos de alumno filtran siempre `alert_type == 'PAIN' AND status == 'REVIEWED' AND student_seen_at IS NULL AND relationship.status == 'ACTIVE'`. Las alertas `REPEATED_DISCOMFORT` y `EXCESSIVE_EFFORT` nunca generan aviso al alumno al ser revisadas (`student_seen_at` permanece `NULL`).
3. **Aislamiento por vínculo activo**: Toda lectura, conteo y mutación de `SafetyAlert` exige que el vínculo referenciado por `relationship_id` esté `ACTIVE` y pertenezca al entrenador o alumno autenticado. Al cambiar el estado del vínculo a `TERMINATED`, las alertas `PENDING` dejan de ser accesibles o prioritarias para el entrenador saliente y no contaminan el historial de un vínculo posterior.
4. **Actualización de modelos de lectura de US-18**:
   - `TrainerStudentListItem.unreviewed_alert_count`: pasa de estar reservado en `0`/`None` a reflejar la cantidad real de `SafetyAlert` en estado `PENDING` para ese `relationship_id` (`int >= 0`).
   - `TrainerStudentLimitations.safety_indicators`: pasa de `[]` a exponer resúmenes legibles de alertas `PENDING` del vínculo activo (por ejemplo tipo, zona/RPE y fecha).
5. **Elegibilidad de sesiones en consecutividad CA-2 (`REPEATED_DISCOMFORT`)**:
   - Solo participan en la línea temporal del vínculo activo las filas `WorkoutSession` que cumplen ambas condiciones: `WorkoutSession.started_at IS NOT NULL` **y** al menos una fila relacionada en `WorkoutSetLog` o `BodyMapPainReport`.
   - Una sesión participante cuenta e interrumpe la secuencia cuando no contiene `DISCOMFORT` en la zona evaluada **incluso si `finished_at IS NULL`**.
   - Quedan excluidas de la evaluación secuencial: sesiones creadas nunca iniciadas (`started_at IS NULL`), sesiones sin `WorkoutSetLog` ni `BodyMapPainReport` (aunque tengan `finished_at`), y filas `BodyMapPainReport` históricas con `session_id IS NULL`. Múltiples reportes de la misma zona vinculados al mismo `session_id` representan una única sesión.

## Migraciones necesarias

- **Creación de tabla nueva**: `safety_alerts` es creada automáticamente por `Base.metadata.create_all` al iniciar la aplicación una vez que `SafetyAlert` se registra en `backend/src/models/__init__.py` y se importa en `backend/src/main.py` (mismo mecanismo usado en US-26 con `session_adjustments`).
- **Verificación idempotente**: Validar y reforzar `backend/src/core/migrations.py` (y `backend/tests/test_database_migrations.py`) para asegurar que bases de datos SQLite/PostgreSQL existentes sin la tabla `safety_alerts` creen la tabla, restricciones e índices de forma aditiva e idempotente sin pérdida de datos previos.

---

# Modelo de datos: US-30 — Progreso del alumno

US-30 no agrega tablas ni migraciones; es un modelo de lectura sobre `WorkoutSession` (solo con `finished_at`), `WorkoutSetLog`, `Exercise.target_muscle_group`, `PersonalRecord` (US-59), `EffortFeedback` (US-64), `ExerciseReplacementLog` (US-54) y la rutina vigente del alumno, dentro de un vínculo ACTIVO del entrenador.

## Respuesta `TrainingEvolution`

- `period`: `{ key: 4w | 12w | all, start, end }` (fechas ISO; `start` es el lunes inicial); `group_by`: `session` | `week`; `muscle_group`: filtro opcional; `muscle_groups`: grupos de todo el historial; `has_sessions`
- `summary`:
  - `progress`: `{ improving, with_data, status }`
  - `adherence`: `{ completed_sessions, scheduled_sessions, pct, sets_completion_pct, status }`
  - `effort`: `{ avg_rpe_last_4, trend: rising | stable | falling, message_key, status }`
  - `to_review`: `{ count, status }`
- `exercises[]`: `{ exercise_id, name, muscle_group, metric: max_weight | max_reps | none, start, current, change_pct, last_improvement: { date, is_pr }, status, points[] }`; `status`: `progressing` | `stalled` | `declined` | `unchanged` | `few_data` | `no_metric`; punto: `{ key, period_start, period_end, weight, reps, target_weight, rpe, is_pr, is_partial }`
- `adherence[]`: `{ period_start, period_end, scheduled, completed, is_partial }` por semana
- `most_skipped[]`: `{ exercise_id, name, completion_pct, skip_count, main_reason: replacement_requested | null }`
- `rpe[]`: `{ key, period_start, period_end, rpe, has_report, trainer_feedback, is_partial }`
- `sets_by_muscle_group[]`: `{ muscle_group, avg_completed_per_week, avg_scheduled_per_week }`
- `to_review[]`: `{ type, exercise_id, label }`

## Reglas de cálculo

1. Solo sesiones finalizadas del vínculo ACTIVO; ajeno o inactivo devuelve 404. El período se alinea a semanas calendario (lunes a domingo, UTC); 4 o 12 semanas incluyen la semana en curso.
2. La semana en curso (`is_partial`) se grafica pero no entra en estados, porcentajes ni tendencias.
3. Métrica por sesión y ejercicio: la mejor serie con repeticiones numéricas (más peso y, a igual peso, más repeticiones); sin carga, más repeticiones; sin repeticiones numéricas: `no_metric`.
4. Estado (semanas completas, en este orden): menos de 2 sesiones → `few_data`; valor actual ≤ 90 % del máximo de las 3 semanas anteriores → `declined`; mejora en las últimas 3 semanas completas → `progressing`; sin mejora y con al menos 3 sesiones en esas semanas → `stalled`; si no, `unchanged`. Mejora: supera el mejor valor anterior.
5. Con `few_data` el inicio y el actual se calculan con todas las sesiones del período; el cambio porcentual es nulo.
6. `is_pr` solo marca la sesión del récord vigente: `PersonalRecord` guarda un único récord por alumno y ejercicio, no un historial.
7. Sesiones programadas por semana = días de la rutina vigente (criterio de US-32), desde la asignación; una semana completa suma `min(completadas, programadas)`. Cumplimiento de series = series registradas (sin superar lo programado por ejercicio, contando el reemplazo elegido) sobre las programadas de la versión vigente de la rutina.
8. Ejercicios más salteados: los 3 con cumplimiento menor al 70 %.
9. Esfuerzo: promedio de RPE de las últimas 4 sesiones con reporte (semanas completas), tendencia contra las 4 anteriores (±0,5 es estable). Mensaje por precedencia: esfuerzo excesivo (algún RPE ≥ 9) → fatiga (carga no sube y RPE sube) → exigir más (promedio < 6) → progreso con esfuerzo en aumento → progreso con margen. La carga "sube" si `progress.status` es verde.
10. Semáforos: progreso verde ≥ 50 %, amarillo 25–49 %; adherencia verde ≥ 80 %, amarillo 60–79 %; esfuerzo verde con promedio 6–8, rojo con promedio ≥ 9 o fatiga; para revisar verde 0, amarillo 1–2, rojo ≥ 3. Los umbrales son constantes del servicio.
11. `to_review` en orden: ejercicios que bajaron, estancados, fatiga o esfuerzo excesivo, ejercicios salteados y semanas sin entrenar (últimas 2 completas). `to_review.count` es la cantidad de puntos de la lista.
12. Series semanales por grupo: promedio de series registradas por semana completa; programadas = series de todos los días de la rutina vigente (cada día una vez por semana).
13. Operación de solo lectura.
