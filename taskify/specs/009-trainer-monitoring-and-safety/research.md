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

# Investigación: US-30 — Evolución de entrenamientos

## Cálculo en servidor, un solo endpoint

- Decisión: `GET /api/v1/trainers/me/students/{student_id}/evolution` con `group_by`, `period` y `exercise_id` opcional; devuelve puntos ya agregados.
- Justificación: las series ya están en `WorkoutSetLog` ligadas a `WorkoutSession`; agregar en servidor evita traer todas las series al cliente y mantiene la autorización por vínculo ACTIVO. El cliente cambia agrupación sin recalcular.
- Alternativas: agregar en el cliente sobre los logs (rechazado: expone volumen de datos y duplica reglas); una tabla de métricas precalculadas (rechazado: sin migraciones, escala de un entrenador).

## Métricas y reutilización

- Decisión: reutilizar el cálculo de `_performed`/`_number` de US-24 (volumen = repeticiones × carga; repeticiones no numéricas no suman volumen). Carga = máximo de `weight_kg` con `exercise_id`, o volumen sin él. Repeticiones totales = suma de repeticiones numéricas; series = cantidad de logs.
- Justificación: una sola definición de volumen en toda la feature.
- Alternativas: reimplementar métricas (rechazado: divergencia con US-24).

## Agrupaciones y período

- Decisión: `session` = un punto por sesión finalizada (por `finished_at`); `week` = semana calendario lunes a domingo en UTC, clave por el lunes; `muscle_group` = una serie por `Exercise.target_muscle_group` con un punto por semana. El período filtra por `finished_at` ≥ ahora − 4/12 semanas; `all` no filtra.
- Justificación: coincide con el spec; semana en UTC mantiene el criterio de marcas de tiempo UTC del proyecto. Límite conocido: una sesión cerca de la medianoche local puede caer en la semana contigua.
- Alternativas: semana en horario local del entrenador (rechazado: requiere `utc_offset_minutes` en todas las consultas por una ganancia mínima).

## Gráfico

- Decisión: SVG/CSS propio sin dependencia nueva, como el análisis de US-28.
- Justificación: no hay librería de gráficos instalada; tres líneas simples no justifican una.
- Alternativas: Recharts/Chart.js (rechazado: dependencia nueva para un gráfico simple).

## Casos vacíos

- Decisión: el backend devuelve `points: []` sin sesiones y la UI muestra "Sin entrenamientos en este período"; con una sola sesión muestra el punto y la nota de mínimo 2 sesiones (la UI decide con `points.length`).
