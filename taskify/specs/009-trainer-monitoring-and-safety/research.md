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

# Investigación: US-30 — Progreso del alumno

## Un solo endpoint de lectura, calculado en el servidor

- Decisión: `GET /api/v1/trainers/me/students/{student_id}/evolution?period=&group_by=&muscle_group=` devuelve las cuatro secciones ya calculadas (progresión por ejercicio, adherencia, RPE y puntos a revisar). Sin tablas ni migraciones.
- Justificación: el cliente no recalcula reglas de negocio, estados ni zonas horarias, y la autorización por vínculo ACTIVO queda en un solo lugar.
- Alternativas: calcular en el cliente sobre los logs (rechazado: duplica reglas y expone todo el historial); tabla de métricas precalculadas (rechazado: sin migraciones, escala de un entrenador).

## Qué se descarta y por qué

- Decisión: se elimina el volumen total y el gráfico de repeticiones y series totales, y el selector de ejercicio.
- Justificación: sumar kilos de ejercicios distintos engaña (cambiar un ejercicio pesado por uno liviano baja el volumen aunque el alumno progrese) y los totales reflejan cómo está armada la rutina, no el rendimiento. El tonelaje sigue en el resumen de sesión (US-63).

## Datos disponibles y sus límites

- Récords (🏆): `PersonalRecord` guarda un único registro vigente por alumno y ejercicio, no un historial; solo se marca la sesión del récord actual.
- Sesiones programadas: los días de la rutina no están atados al calendario (US-22), así que se aproximan con los días por semana de la rutina vigente, igual que US-32. Si la rutina cambió, las semanas pasadas se miden con la vigente.
- Series programadas: salen de la versión vigente de la rutina (no se guardan versiones históricas, igual que US-24).
- Motivo de un ejercicio salteado: `ExerciseReplacementLog` no tiene motivo ni bandera de salto; el único motivo disponible es el pedido de reemplazo.
- Alternativas: modelar un calendario de sesiones programadas (rechazado: fuera del alcance de US-30).

## Reglas

- Semana calendario de lunes a domingo en UTC (límite conocido: una sesión cerca de la medianoche local puede caer en la semana contigua). La semana en curso no entra en estados, porcentajes ni tendencias.
- Orden de estados: pocos datos → bajó → progresando → estancado → sin cambios; "mejora" es superar el mejor valor anterior. Ejercicios con repeticiones no numéricas ("45 seg", "al fallo") quedan como "Sin métrica".
- Mensaje de esfuerzo: precedencia explícita para evitar solapamientos (ver `data-model.md`). Umbrales como constantes del módulo, sin sistema de configuración.
- Sin botón "Ajustar próxima sesión": US-26 parte de una sesión finalizada y vive en "Rutinas del día"; enlazarlo exigiría elegir sesión y preseleccionar ejercicio.
