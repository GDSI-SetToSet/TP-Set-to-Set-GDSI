# Research: US-14

**D1 — Copia por alumno de la rutina.** Decisión: al editar por primera vez se clona la plantilla (o rutina IA) en `StudentRoutine` vigente + borrador. Motivo: `initial_routine_id` apunta a la plantilla compartida; editarla afectaría a otros alumnos. Alternativa descartada: editar la plantilla in situ.

**D2 — Un borrador por alumno, publicación atómica.** Decisión: `StudentRoutine` tiene `status` (`ACTIVE` | `DRAFT`); confirmar reemplaza el contenido vigente en una transacción. Motivo: el alumno nunca ve una rutina a medio editar. Versionado restaurable descartado (aclarado en spec).

**D3 — Detección de conflicto con limitaciones.** Decisión: `Exercise` gana `contraindicated_zones` (lista de `body_area`) cargada por el entrenador; se bloquea si coincide con `ProtectedZone.body_area` del alumno (comparación normalizada, minúsculas y sin espacios extremos). Motivo: hoy no existe relación ejercicio↔zona y `body_area` es texto libre. Alternativa descartada: inferir desde `target_muscle_group` (poco confiable en salud).

**D4 — Variante segura sin US-53.** Decisión: la alerta incluye `safe_variant` solo si el ejercicio ya la tiene configurada; hasta que se implemente US-53 el campo viaja `null` y el bloqueo igual aplica. Motivo: Principio VII impide depender de una story no mergeada.

**D5 — "Sin materiales" al confirmar.** Decisión: la validación recorre los ejercicios editados y exige `has_no_materials_alternative` en el ejercicio de la rutina; el guardado de borrador no la exige (aclarado en spec).

**D6 — Conflicto de edición simultánea.** Decisión: bloqueo optimista con `version` entera en el borrador; `409` si no coincide. Motivo: simple, sin locks.

**D7 — Volumen semanal deseado.** Decisión: campo `desired_weekly_volume` (entero de sesiones/semana, opcional) en `StudentRoutine`, cargado por el entrenador (aclarado en spec). La intensidad se edita con el mismo endpoint de edición.

**D8 — Auditoría.** Decisión: `RoutineChangeLog` inmutable (autor, fecha UTC, resumen JSON de diferencias) escrito al confirmar; sin DELETE.

# Research: US-53

**D9 — Cruce de riesgo.** Decisión: se reutiliza `Exercise.contraindicated_zones` (etiquetas) contra `ProtectedZone.body_area` con la misma normalización de US-14; un ejercicio es "de riesgo" si comparte al menos una zona (aclarado en spec). Catálogo único de zonas: el ya existente (`bodyAreas.ts`); sin tabla nueva. Alternativa descartada: marcado manual por alumno (no garantiza SC-002).

**D10 — Variante como referencia a otro ejercicio.** Decisión: `ExerciseSafeVariant` apunta a un `Exercise` propio del mismo entrenador y declara `covered_zones`; así el video (US-12) y las notas técnicas (US-52) del ejercicio variante cubren el escenario 3 sin duplicar campos. Se valida que la variante no sea contraindicada para esas mismas zonas. Alternativa descartada: variante con texto/URL propios (duplica US-12/US-52).

**D11 — Resolución en cada consulta.** Decisión: no se guarda snapshot; el endpoint del alumno calcula `zonas en conflicto = ejercicio ∩ restricciones` y elige, entre las variantes con `covered_zones ⊇ conflicto`, la más antigua (orden por `created_at`, determinista). Sin ninguna → `BLOCKED`. Motivo: aplicar cambios de inmediato (aclarado en spec) y Principio III (autorización en backend en cada petición).

**D12 — Caso pendiente y deduplicación.** Decisión: `SafeVariantCase` (único por alumno + ejercicio) con `status` `PENDING|RESOLVED`. Al resolver `BLOCKED` sin caso o con caso `RESOLVED` se crea/reabre el caso y se emite **una** `Notification` al entrenador (reutiliza `create_notification`, `related_entity_type="SAFE_VARIANT_CASE"`); con caso `PENDING` no se emite otra. Al crear o editar una variante, los casos `PENDING` del ejercicio cuyo conflicto quede cubierto pasan a `RESOLVED`. Alternativa descartada: índice parcial único (portabilidad SQLite/PostgreSQL).

**D13 — Alcance del acceso del alumno.** Decisión: el alumno solo consulta ejercicios presentes en su `StudentRoutine` vigente con vínculo ACTIVE; otro ejercicio → `404`. Evita exponer la biblioteca del entrenador.

**D14 — Saltear el ejercicio.** Decisión: la respuesta `BLOCKED` indica `can_skip: true`; registrar el salto en la sesión corresponde a ejecución de entrenamiento (spec 007) y queda fuera. Integración con US-14: el campo `safe_variant` de la alerta pasa de `null` a la variante resuelta (cierra D4).
