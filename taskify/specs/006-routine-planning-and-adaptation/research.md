# Research: US-14

**D1 — Copia por alumno de la rutina.** Decisión: al editar por primera vez se clona la plantilla (o rutina IA) en `StudentRoutine` vigente + borrador. Motivo: `initial_routine_id` apunta a la plantilla compartida; editarla afectaría a otros alumnos. Alternativa descartada: editar la plantilla in situ.

**D2 — Un borrador por alumno, publicación atómica.** Decisión: `StudentRoutine` tiene `status` (`ACTIVE` | `DRAFT`); confirmar reemplaza el contenido vigente en una transacción. Motivo: el alumno nunca ve una rutina a medio editar. Versionado restaurable descartado (aclarado en spec).

**D3 — Detección de conflicto con limitaciones.** Decisión: `Exercise` gana `contraindicated_zones` (lista de `body_area`) cargada por el entrenador; se bloquea si coincide con `ProtectedZone.body_area` del alumno (comparación normalizada, minúsculas y sin espacios extremos). Motivo: hoy no existe relación ejercicio↔zona y `body_area` es texto libre. Alternativa descartada: inferir desde `target_muscle_group` (poco confiable en salud).

**D4 — Variante segura sin US-53.** Decisión: la alerta incluye `safe_variant` solo si el ejercicio ya la tiene configurada; hasta que se implemente US-53 el campo viaja `null` y el bloqueo igual aplica. Motivo: Principio VII impide depender de una story no mergeada.

**D5 — "Sin materiales" al confirmar.** Decisión: la validación recorre los ejercicios editados y exige `has_no_materials_alternative` en el ejercicio de la rutina; el guardado de borrador no la exige (aclarado en spec).

**D6 — Conflicto de edición simultánea.** Decisión: bloqueo optimista con `version` entera en el borrador; `409` si no coincide. Motivo: simple, sin locks.

**D7 — Volumen semanal deseado.** Decisión: campo `desired_weekly_volume` (entero de sesiones/semana, opcional) en `StudentRoutine`, cargado por el entrenador (aclarado en spec). La intensidad se edita con el mismo endpoint de edición.

**D8 — Auditoría.** Decisión: `RoutineChangeLog` inmutable (autor, fecha UTC, resumen JSON de diferencias) escrito al confirmar; sin DELETE.
