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
