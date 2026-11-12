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
