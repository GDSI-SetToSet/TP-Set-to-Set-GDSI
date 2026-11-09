# Technical Research: Generación de Rutina Particular con IA (US-13)

**Feature**: `006-routine-planning-and-adaptation` (US-13)
**Date**: 2026-10-31

## 1. Arquitectura y Desacople del Proveedor de IA (Principio II de la Constitución)

- **Contexto**: El Principio II de la Constitución exige:
  > "El diseño DEBE desacoplar la integración del proveedor de IA mediante adaptadores o interfaces abstractas para permitir su reemplazo sin impactar las reglas del dominio."
  Asimismo, no existe actualmente una API externa contratada ni dependencias de SDKs de terceros instaladas.
- **Decisión**: Implementar el patrón Adapter con una interfaz abstracta `AIRoutineAdapter` en `backend/src/services/ai_routine_adapter.py`.
- **Implementación por Defecto (`HeuristicAIRoutineAdapter`)**:
  - Implementación determinista, basada en reglas biomecánicas y adaptaciones fisiológicas reales.
  - No depende de claves de API externas ni cuotas en desarrollo o CI.
  - Admite extensión plug-and-play hacia proveedores como OpenAI o Google Gemini a través de HTTP (`httpx`), configurable vía variable de entorno `AI_ROUTINE_PROVIDER`.
- **Lógica de Adaptación Biomecánica**:
  1. **Análisis de Incompatibilidades y Zonas Protegidas**:
     - Si el `target_muscle_group` o nombre de un ejercicio de la rutina genérica coincide con alguna `ProtectedZone` del alumno (p.ej. ejercicio de "Hombro" frente a zona "Hombro derecho" o ejercicio de "Piernas" frente a "Rodilla izquierda"):
       - Se busca en la biblioteca del entrenador (`trainer_exercises`) un ejercicio alternativo seguro de distinta zona no restringida.
       - Si existe alternativa, se sustituye y se documenta en el resumen.
       - Si no existe alternativa segura, se elimina el ejercicio para salvaguardar la articulación / músculo protegido.
  2. **Análisis de Restricciones del Cuestionario de Salud**:
     - Si el alumno declara problemas cardíacos, dolor de pecho en actividad o problemas osteoarticulares severos, se disminuye la intensidad general (p.ej. `EXIGENTE` -> `ALTA`, `ALTA` -> `MEDIA`, `MEDIA` -> `BAJA`) y se aumenta el tiempo de descanso por serie.
  3. **Adaptación según Objetivos (`fitness_goals`)**:
     - `HIPERTROFIA`: volumen moderado a alto (3-4 series, 8-12 reps, 60-90s descanso).
     - `FUERZA`: volumen moderado (3-5 series, 4-6 reps, 120-180s descanso).
     - `RESISTENCIA` / `PERDIDA_GRASA`: series de repeticiones más altas (15-20 reps, 30-45s descanso).
     - `SALUD_POSTURAL` / `REHABILITACION`: énfasis en movilidad, cargas controladas y descansos adecuados.
  4. **Resumen de Adaptaciones (`adaptation_summary`)**:
     - La IA genera un resumen legible para el entrenador detallando qué ejercicios se modificaron, cuáles se sustituyeron o eliminaron, y por qué.

## 2. Supervisión Humana Obligatoria (Human-in-the-Loop) y Estados de la Rutina

- **Decisión**: La propuesta generada por IA se persiste inicialmente con `status = "PENDING_REVIEW"`.
- **Razón**: Por principio constitucional, el sistema jamás debe activar una rutina directamente al alumno. El entrenador debe ver la propuesta, examinar las modificaciones y aprobarla explícitamente mediante una acción HTTP POST (`/api/v1/routines/assigned/{id}/approve`).
- **Transición de Estado**:
  - `PENDING_REVIEW` -> Creada por IA, visible para el entrenador para su revisión.
  - `APPROVED` -> Aprobada manualmente por el entrenador; queda vinculada y disponible como la rutina actual del alumno (`initial_routine_id` en `TrainingRelationship`).

## 3. Inmutabilidad de la Plantilla Genérica (`RoutineTemplate`)

- **Decisión**: La plantilla genérica original de la biblioteca no se modifica en absoluto. La rutina particular se almacena en tablas dedicadas (`assigned_routines`, `assigned_routine_days`, etc.).
- **Razón**: El entrenador puede reutilizar la misma plantilla genérica para otros alumnos sin que las adaptaciones particulares de un alumno contaminen la biblioteca.

## 4. Autorización y Privacidad en Servidor (Principio III)

- **Decisión**: El backend valida que exista una `TrainingRelationship` en estado `ACTIVE` entre el entrenador autenticado y el alumno seleccionado antes de permitir la generación de la rutina y la lectura de datos de salud y objetivos.
- **Razón**: Protección estricta de datos de salud conforme al Principio III. Si un entrenador intenta generar una rutina o consultar datos de un alumno sin relación activa, recibe HTTP 403 Forbidden.

## 5. Selección de Alumno Activo

- **Decisión**: Proveer el endpoint `GET /api/v1/trainers/me/active-students` para que el entrenador consulte sus alumnos con vínculo activo y pueda seleccionarlos en la interfaz.

---

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

# Research: US-54

**D15 — Alternativas derivadas, no curadas.** Decisión: las alternativas se calculan por consulta: ejercicios del mismo entrenador, no dados de baja, distintos del original, con el mismo `target_muscle_group` y sin zonas de `contraindicated_zones` en común con las `ProtectedZone` del alumno (D9); si la alternativa tiene variante segura (D11) se muestra esa variante. Sin tabla nueva ni dependencia de la modalidad (`GYM`/`HOME`). Alternativa descartada: vínculo manual ejercicio→alternativa (más trabajo para el entrenador; ceiling: agregarlo, al estilo `ExerciseSafeVariant`, si piden curar la lista).

**D16 — Registro propio del reemplazo.** Decisión: `ExerciseReplacementLog` (alumno, rutina, día, fecha UTC, ejercicio original, alternativa o salto), con una fila por ejercicio original que se sobrescribe. No depende de una entidad sesión (spec 007 no implementada; Principio VII) y sigue el criterio de D14. Se reconcilia con la sesión cuando 007 exista. La rutina vigente no se modifica; las series se registran con el `exercise_id` realmente realizado (`WorkoutSetLog`).
