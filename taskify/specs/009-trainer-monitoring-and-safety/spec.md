# Especificación de la feature: Panel de Monitoreo del Entrenador, Métricas y Alertas de Seguridad

**Rama de la feature**: `009-trainer-monitoring-and-safety`

**Creada**: 2026-10-15

**Estado**: Borrador

**Entrada**: Mapa de historias de usuario y Backlog MVP: Centro de control del entrenador para supervisar alumnos activos, buscar y filtrar por paquete, comunicarse por canal directo, comparar ejecución planificada vs realizada, analizar cargas y RPE, ajustar próximas sesiones y recibir alertas tempranas de dolor y de riesgo de abandono.

**Historias de usuario cubiertas**: US-18, US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30, US-32

## Clarificaciones

### Sesión 2026-11-11 — US-18

- Q: ¿Qué alcance se implementa en este incremento de la feature 009? → A: Exclusivamente US-18; US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30 y US-32 permanecen fuera de alcance.
- Q: ¿Qué debe incluir el detalle de un alumno activo sin duplicar módulos existentes? → A: Perfil básico, paquete y tarifa acordada, objetivos, zonas protegidas, rutina vigente y un resumen de métricas ya disponibles; se reutilizan los servicios existentes de rutinas, sesiones, logs, feedback y reportes.
- Q: ¿Qué significa “métricas” para US-18 sin absorber US-24 o US-30? → A: Un resumen de actividad reciente (sesiones finalizadas, última sesión, series registradas, último RPE y tonelaje de la última sesión); no incluye gráficos, filtros ni comparación histórica avanzada.
- Q: ¿Cómo se deben ordenar y destacar las alertas en esta entrega? → A: El ordenamiento por alertas de seguridad queda fuera de este incremento y se implementará junto con US-29; US-18 conserva el punto de integración visual sin inventar estados de revisión.

### Sesión 2026-11-12 — US-20

- Q: ¿Qué se considera un "paquete registrado" para habilitar el filtro? → A: Los paquetes vigentes (no archivados) del entrenador más cualquier paquete archivado que todavía tenga contratado un alumno activo. Con un único paquete el filtro no se muestra.
- Q: ¿Cómo se muestran los cupos ocupados por plan? → A: Cada opción del filtro indica la cantidad de alumnos activos que contrataron ese paquete; un paquete sin alumnos aparece con cero cupos ocupados y un mensaje de estado vacío propio.
- Q: ¿Dónde se filtra? → A: Localmente en el cliente, sobre los alumnos activos ya cargados y combinado con la búsqueda por nombre de US-19. El backend solo expone `plan_id` y `plan_title` en `GET /api/v1/routine-templates/assignments`.

### Sesión 2026-11-12 — US-22

- Q: ¿Qué es "rutina del día" si los días de la rutina no están atados al calendario? → A: La sesión de entrenamiento que el alumno inició en el día calendario local del entrenador (se envía `date` y `utc_offset_minutes`). Sin sesión ese día, el estado es "No comenzada".
- Q: ¿Qué sesión se muestra si hubo más de una en el día? → A: La sesión en curso, si existe; si no, la última finalizada.
- Q: ¿Qué detalle se muestra? → A: Día de rutina, hora de inicio y fin, duración, RPE y, por ejercicio, cada serie con repeticiones, carga, tiempo de la serie y hora de registro. Los alumnos que están entrenando aparecen primero.

### Sesión 2026-11-12 — US-28

- Q: ¿Qué reportes se analizan? → A: Las zonas reportadas con molestia o dolor en el mapa corporal (US-61), tanto durante el ejercicio como post-sesión; las zonas "Normal" se descartan.
- Q: ¿Qué significa "grupo muscular" en el gráfico? → A: El grupo muscular objetivo del ejercicio asociado al reporte. Como el mapa corporal registra zonas, el gráfico también permite agrupar por zona corporal, ejercicio y día de rutina; los reportes post-sesión sin ejercicio se agrupan aparte.
- Q: ¿Dónde se muestra? → A: En el detalle del alumno (US-18), con un gráfico de barras apiladas dolor/molestia y el listado de reportes del más reciente al más antiguo. El backend solo agrega `exercise_muscle_group` al historial por zona existente.

### Sesión 2026-11-12 — US-32

- Q: ¿Qué cuenta como "reporte del entrenamiento"? → A: Una sesión de entrenamiento finalizada por el alumno.
- Q: ¿Cómo se calculan los "5 entrenamientos"? → A: Con la frecuencia de la rutina asignada (días de rutina por semana): entrenamientos sin reportar = ⌊días sin reportar × frecuencia / 7⌋. El riesgo se dispara con 5 entrenamientos sin reportar o 14 días, lo que ocurra primero. Sin rutina asignada no se esperan entrenamientos y no hay riesgo.
- Q: ¿Desde cuándo se cuentan los días? → A: Desde el último reporte, o desde el inicio del vínculo o la asignación de la rutina si nunca reportó (la fecha más reciente).
- Q: ¿Cómo recibe la alerta el entrenador? → A: Como notificación `ABANDONMENT_RISK` (una sola vez por período de inactividad), generada al consultar sus notificaciones o el riesgo de sus alumnos. En "Mis alumnos" los alumnos en riesgo aparecen primero con la etiqueta "Riesgo de abandono".

### Sesión 2026-11-13 — US-24

- Q: ¿Contra qué se comparan las métricas de una sesión "Finalizada"? → A: Contra ambas referencias. Por ejercicio se muestra lo planificado en la rutina (series, repeticiones y carga objetivo) frente a lo realizado, y además frente a la sesión anterior.
- Q: ¿Qué "entrenamientos previos" se usan? → A: La última sesión finalizada anterior del mismo día de rutina (misma rutina y mismo nombre de día) del mismo vínculo. Sin sesión previa, la comparación histórica se muestra vacía.
- Q: ¿Qué métricas se comparan? → A: Por ejercicio: series realizadas, repeticiones por serie, carga máxima, volumen (repeticiones × carga) y tiempo total de las series. Por sesión: duración, RPE y volumen total. Lo planificado corresponde a la versión vigente de la rutina, porque no se guardan versiones históricas. Si el alumno reemplazó un ejercicio (US-54), lo realizado del reemplazo se compara contra lo planificado del ejercicio original y se indica el reemplazo.
- Q: ¿Dónde se ve? → A: En "Rutinas del día" (US-22), dentro del detalle de una sesión "Finalizada", mediante la acción "Comparar métricas". Una sesión en curso no se puede comparar.

### Sesión 2026-11-13 — US-26

- Q: Los días de la rutina no están atados al calendario: ¿qué es la "próxima sesión programada" y qué modifica el ajuste? → A: El mismo día de rutina de la sesión revisada (por ejemplo, "Día A"). El ajuste modifica de forma persistente ese día en la copia de la rutina del alumno, reutilizando la edición de US-14, y queda en el historial de cambios. El alumno ve la marca "Ajustado por tu entrenador" y la nota en los ejercicios ajustados hasta que finaliza una sesión de ese día.
- Q: ¿Qué se puede modificar? → A: Las series, las repeticiones, el descanso y la carga objetivo de los ejercicios del día, y reemplazar un ejercicio por otro de la biblioteca del entrenador. No se agregan ni quitan días o bloques. La nota es opcional (hasta 500 caracteres).
- Q: ¿Qué información de la sesión se ve al ajustar? → A: Las cargas registradas por ejercicio, el RPE, las molestias y los dolores reportados en el mapa corporal durante esa sesión (US-61) y los pedidos de reemplazo o los ejercicios salteados (US-54).
- Q: ¿Un ejercicio contraindicado se advierte o se bloquea? → A: Se bloquea, igual que en US-14. La advertencia indica la limitación y la variante segura si existe, y el ajuste no se guarda.
- Q: ¿Qué pasa si el alumno está entrenando cuando se guarda el ajuste? → A: El ajuste queda pendiente y se aplica cuando el alumno finaliza la sesión en curso, o cuando inicia una nueva si abandonó la anterior. La sesión en curso no se modifica. Un ajuste nuevo del mismo día reemplaza al anterior.
- Q: ¿Qué pasa si la rutina cambió o tiene un borrador? → A: No se permite ajustar si la sesión revisada no corresponde a la rutina vigente del alumno, si el día ya no existe o si hay un borrador de US-14 sin confirmar.

### Sesión 2026-11-14 — US-30

- Q: ¿Qué representa cada una de las vistas "por entrenamiento" y "por semana"? → A: Por entrenamiento, un punto por sesión finalizada en orden cronológico; por semana, un punto por semana calendario de lunes a domingo. "Por grupo muscular" es un filtro (ver la sesión 2026-11-16).
- Q: ¿Qué período de tiempo cubre el gráfico de evolución de un alumno? → A: Un selector de período con 4 semanas, 12 semanas y todo el historial; el valor por defecto es 12 semanas.
- Q: ¿Dónde ve el entrenador la evolución del alumno? → A: En el detalle del alumno (US-18), con el título "Progreso de {nombre}". Qué se muestra y cómo se mide está en la sesión 2026-11-16.
- Q: ¿Qué sesiones cuentan para el gráfico de evolución? → A: Solo las sesiones finalizadas; las en curso y las abandonadas se excluyen.

### Sesión 2026-11-16 — US-30 (rediseño por preguntas)

Esta sesión reemplaza a la sesión 2026-11-15 y a los puntos de la sesión 2026-11-14 que se contradicen con ella.

**Enfoque**: el entrenador no abre la pantalla para mirar números sino para decidir qué hacer con el alumno. Por eso cada sección se titula con la pregunta que el entrenador se hace (¿está progresando?, ¿está entrenando lo que le programé?, ¿cómo le está costando?, ¿qué tengo que ajustar?), arranca con una respuesta en una línea calculada por el sistema y recién después muestra el detalle (tabla y gráfico) que la respalda. Los cuatro indicadores del encabezado resumen las respuestas y llevan a cada sección. El sistema señala lo que requiere atención, pero la decisión de ajustar la rutina sigue siendo del entrenador (US-26, desde "Rutinas del día").

- Q: ¿Cómo se organiza la pantalla "Progreso del alumno"? → A: En cuatro secciones, cada una con una pregunta como título y una respuesta en una línea calculada por el sistema: "¿Está progresando?" (progresión por ejercicio), "¿Está entrenando lo que le programé?" (adherencia y cumplimiento), "¿Cómo le está costando?" (esfuerzo percibido, RPE) y "¿Qué tengo que ajustar?" (puntos a revisar y series semanales por grupo muscular). Arriba, cuatro indicadores (Progreso, Adherencia, Esfuerzo y Para revisar) con color de estado y siempre con texto o ícono.
- Q: ¿Se mantiene el gráfico de volumen total y el de repeticiones y series? → A: No. Sumar kilos de ejercicios distintos engaña si el alumno cambia un ejercicio. El volumen queda solo en el resumen de sesión (US-63). Se elimina también el selector de ejercicio: elegir un ejercicio es tocar su fila en la tabla.
- Q: ¿Qué se mide por ejercicio? → A: Por sesión, el peso máximo de las series con repeticiones numéricas; en ejercicios sin carga, el máximo de repeticiones en una serie; los ejercicios con repeticiones no numéricas ("45 seg", "al fallo") se muestran como "Sin métrica" y no cuentan. Es mejora si se supera el mejor valor anterior (más peso, o el mismo peso con más repeticiones).
- Q: ¿Cómo se clasifica un ejercicio? → A: Solo con semanas completas (la semana en curso no entra en estados, porcentajes ni tendencias), en este orden: menos de 2 sesiones → "Pocos datos"; valor actual al menos 10 % menor que el máximo de las 3 semanas anteriores → "Bajó"; mejora en las últimas 3 semanas completas → "Progresando"; sin mejora y con al menos 3 sesiones en esas 3 semanas → "Estancado"; en otro caso → "Sin cambios". La tabla se ordena Bajó, Estancado y Progresando primero.
- Q: ¿Qué significa "sesiones programadas"? → A: Los días de rutina por semana de la rutina vigente (el mismo criterio que US-32), desde la asignación de la rutina. Las series programadas salen de la versión vigente de la rutina. Cumplimiento = series completadas sobre programadas (sin superar lo programado por ejercicio). Los ejercicios más salteados son los 3 con menor cumplimiento si es menor al 70 %; el único motivo disponible es "pedido de reemplazo" (US-54).
- Q: ¿Cómo se interpreta el esfuerzo? → A: Promedio de RPE de las últimas 4 sesiones con reporte y su tendencia contra las 4 anteriores (±0,5 es estable). El mensaje sigue esta precedencia: alguna sesión con RPE 9 o más, "esfuerzo excesivo"; carga plana y RPE subiendo, "posible fatiga"; promedio menor a 6, "podría exigirse más"; carga subiendo con RPE subiendo, "progresa pero el esfuerzo aumenta"; carga subiendo con RPE estable o bajando, "progresa con buen margen". La carga "sube" cuando el indicador de Progreso es verde. Las sesiones sin reporte quedan como hueco.
- Q: ¿Qué incluye "¿Qué tengo que ajustar?" y se enlaza a US-26? → A: Una lista automática de puntos a revisar, en orden: ejercicios que bajaron, estancados, fatiga o esfuerzo excesivo, ejercicios salteados y semanas sin entrenar en las últimas 2; más las series semanales promedio por grupo muscular contra las programadas. Cada punto salvo "semana sin entrenar" tiene el enlace "Ajustar en Rutinas del día", que lleva a esa pantalla (US-26) donde el entrenador elige la sesión y el ejercicio; no hay botón "Ajustar próxima sesión" ni preselección del ejercicio. Sin puntos: "Nada para ajustar por ahora".
- Q: ¿Qué controles tiene la pantalla? → A: Período (4 semanas, 12 semanas por defecto o todo el historial, alineado a semanas calendario y con el rango de fechas visible), Agrupar (por entrenamiento o por semana) y Grupo muscular (filtra la tabla y las series semanales). "Por grupo muscular" deja de ser una agrupación del eje temporal.
- Q: ¿Qué estados especiales hay? → A: Sin sesiones: "{nombre} todavía no registró entrenamientos" y sin gráficos. Una sola sesión: la tabla con estado "Pocos datos" y sin gráficos de línea. Sin RPE: "{nombre} no reportó esfuerzo en este período". Grupo muscular sin datos: "No hay ejercicios de {grupo} en este período". Los umbrales (3 semanas, 10 %, 70 %, rangos de RPE y colores) son constantes del módulo.
- Q: ¿Cómo se explica qué significa cada línea, marca y color de los gráficos? → A: Cada gráfico tiene una leyenda propia, con una muestra dibujada igual que en el gráfico (línea continua, línea entrecortada, punto lleno o hueco, anillo, barra o banda) y su significado en texto. Línea continua: mejor serie de cada período; entrecortada que llega a un punto hueco: período en curso, todavía incompleto; punteada gris: peso objetivo programado; anillo dorado: récord personal vigente; barra gris: sesiones programadas; barra azul: realizadas; contorno rojo: semana sin entrenar; banda verde: RPE 6–8 recomendado; ×: sesión sin reporte de esfuerzo; marca dorada vertical: series programadas. Ningún significado depende solo del color, y cada gráfico ofrece "Ver valores en tabla" como alternativa para teclado y táctil.

### Límite de alcance de este incremento

Los artefactos de implementación de esta iteración cubren únicamente los escenarios de aceptación 1–3 de US-18. El escenario 4, de priorización de alertas, permanece en la especificación de la feature como dependencia de US-29 y explícitamente no se implementa en este incremento. La búsqueda, el filtrado por paquete, la mensajería, las comparaciones avanzadas, los gráficos, los ajustes de sesiones, el ciclo de vida de las alertas de seguridad y el cálculo del riesgo de abandono siguen perteneciendo a sus respectivas historias de usuario.

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia de usuario 1 - [US-18: visualización de alumnos activos] (Prioridad: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero visualizar el listado de alumnos activos que tengo,
 para poder llevar un monitoreo general y particular de cada uno de mis alumnos.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador, cuando ingresa a la sección "Alumnos", entonces debe visualizar todos sus alumnos activos.

2. Dado un entrenador sin alumnos activos, cuando ingresa a la sección "Alumnos", entonces el sistema debe indicar que no tiene alumnos activos.

3. Dado un entrenador con alumnos activos, cuando selecciona un alumno en particular, entonces se muestra el perfil del alumno, paquete contratado, objetivos, limitaciones, rutinas cargadas y métricas del alumno.

4. Dado un entrenador con alumnos con alertas de seguridad sin revisar (US-29), cuando ingresa a "Alumnos", entonces esos alumnos aparecen primero y destacados. **Nota sobre la dependencia**: este escenario queda reservado para el incremento de US-29 y no forma parte del alcance actual de implementación de US-18.


---

### Historia de usuario 2 - [US-19: buscar por alumno] (Prioridad: P1, Estimación: 2 SP)

Como entrenador personal,
 quiero poder buscar alumnos dentro de mi listado de alumnos activos,
 para encontrar y consultar el perfil de un alumno en particular.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando el entrenador busca por nombre y apellido un alumno existente, entonces el sistema devuelve el alumno buscado.

2. Dado un entrenador con alumnos activos, cuando el entrenador busca por nombre y apellido un alumno inexistente, entonces el sistema no devuelve a ningun alumno.


---

### Historia de usuario 3 - [US-20: filtrar alumnos por paquete contratado] (Prioridad: P2, Estimación: 2 SP)

Como entrenador personal,
 quiero filtrar a mis alumnos por paquete contratado,
 para poder ver los cupos ocupados en cada uno de mis planes.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con un solo paquete de entrenamiento cargado, cuando entra a la sección de "Alumnos", entonces no puede filtrar por paquete ya que solamente hay un único paquete

2. Dado un entrenador con más de un paquete de entrenamiento registrado, cuando entra a la sección de "Alumnos", entonces el sistema permite filtrar por cada uno de los paquetes registrados.

3. Dado un entrenador con más de un paquete de entrenamiento registrado, cuando entra a la sección de "Alumnos" y filtra por un paquete en particular, entonces el sistema solamente debe mostrar los alumnos que hayan contratado dicho paquete.


---

### Historia de usuario 4 - [US-21: Canal de mensajes entrenador–alumno] (Prioridad: P1, Estimación: 4 SP)

Como entrenador personal o alumno,
 quiero intercambiar mensajes con mi alumno o mi entrenador dentro de la aplicación,
 para coordinar cambios y resolver dudas generales sin usar WhatsApp.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador y su alumno activo, cuando uno ingresa al perfil del otro, entonces puede abrir la conversación entre ambos.

2. Dado un mensaje enviado, cuando el destinatario no tiene la aplicación abierta, entonces recibe una notificación y ve el mensaje al abrir la conversación.

3. Dado un entrenador o un alumno en la conversación, cuando la abre, entonces ve el historial completo de mensajes.

4. Dado un alumno dado de baja (US-35), cuando intenta enviar un mensaje, entonces el sistema no lo permite.


---

### Historia de usuario 5 - [US-22: seguimiento de rutinas de alumnos] (Prioridad: P1, Estimación: 4 SP)

Como entrenador personal,
 quiero realizar un seguimiento de las rutinas del día del alumno,
 para conocer el estado del entrenamiento de mi alumno.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando entra a la sección de "Rutinas del día", entonces debe poder ver todas las rutinas de sus alumnos para ese día.

2. Dado un entrenador con alumnos activos, cuando entra a una rutina en particular, entonces puede ver el estado de la rutina (No comenzada, Entrenando, Finalizada)

3. Dado un entrenador con alumnos activos, cuando entra a una rutina en estado "Entrenando" o "Finalizada", entonces debe poder ver los tiempos y cargas de cada serie/ejercicio.


---

### Historia de usuario 6 - [US-24: ver métricas esperadas vs obtenidas por rutina] (Prioridad: P2, Estimación: 3 SP)

Como entrenador personal,
 quiero comparar las métricas esperadas del entrenamiento con las métricas obtenidas,
 para realizar un seguimiento de los entrenamientos de mis alumnos y adaptar las rutinas en base a lo obtenido.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando entra a una rutina en estado "Finalizada", entonces puede ver las métricas de tiempos y cargas del alumno y compararlas con entrenamientos previos del alumno.


---

### Historia de usuario 7 - [US-26: Ajustar la próxima sesión del alumno a partir de sus reportes] (Prioridad: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero ajustar la próxima sesión de un alumno a partir de lo que reportó en la anterior,
 para adaptar cargas o ejercicios según su rendimiento, sus molestias y sus pedidos.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador revisando una sesión "Finalizada" (cargas, RPE, molestias y pedidos de reemplazo), cuando decide ajustar, entonces puede modificar cargas, series o reemplazar ejercicios de la próxima sesión programada desde esa misma pantalla.

2. Dado un ajuste guardado, cuando el alumno abre su próxima sesión, entonces ve los ejercicios ajustados con la marca "Ajustado por tu entrenador" y la nota, si la hay.

3. Dado un ajuste que incluye un ejercicio contraindicado por las restricciones del alumno (US-42), cuando el entrenador intenta guardarlo, entonces el sistema muestra una advertencia.

4. Dado un alumno con una sesión en curso, cuando el entrenador guarda un ajuste, entonces el cambio se aplica a partir de la próxima sesión y no modifica la que está en curso.


---

### Historia de usuario 8 - [US-28: analizar cargas reportadas por alumnos] (Prioridad: P1, Estimación: 4 SP)

Como entrenador personal,
 quiero poder analizar los reportes de carga de los alumnos después de cada entrenamiento,
 para poder llevar un mejor seguimiento de cada alumno y adaptar los entrenamientos para prevenir lesiones.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces puede ver todos sus reportes de molestia y dolor asociados al ejercicio o rutina correspondiente.

2. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces puede ver un gráfico de molestia y dolor por grupo muscular y rutina/ejercicio.


---

### Historia de usuario 9 - [US-29: Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo] (Prioridad: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero recibir alertas inmediatas cuando un alumno reporta dolor, molestias repetidas o un esfuerzo excesivo,
 para actuar antes de que se produzca una lesión o una recaída.

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un alumno que reporta "dolor" en una zona (durante el ejercicio o al finalizar la sesión, US-61), cuando lo registra, entonces el entrenador recibe una notificación inmediata con el alumno, la zona, el ejercicio y la sesión.

2. Dado un alumno que reporta "molestia" en la misma zona en 2 sesiones consecutivas, cuando registra el segundo reporte, entonces el entrenador recibe una alerta.

3. Dado un alumno que reporta un RPE de 9 o 10 (US-60), cuando lo envía, entonces el entrenador recibe una alerta de esfuerzo excesivo.

4. Dado un entrenador con alertas sin revisar, cuando abre el listado de alumnos (US-18), entonces esos alumnos aparecen primero y destacados hasta que marca la alerta como "Revisada" indicando la acción tomada (ajusté la rutina, contacté al alumno o sin acción).

5. Dado un alumno que reportó dolor, cuando el entrenador marca la alerta como revisada, entonces el alumno ve en su próxima sesión que su reporte fue revisado, junto con la nota del entrenador si la dejó.


---

### Historia de usuario 10 - [US-30: ver métricas de evolución de entrenamientos] (Prioridad: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero ver un gráfico de evolución de los entrenamientos de mis alumnos mostrando pesos levantados, repeticiones y series realizadas,
 para evaluar el avance y evolución de los entrenamientos de mis alumnos

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces ve la evolución del peso máximo por ejercicio, la adherencia (sesiones realizadas vs. programadas), el esfuerzo percibido por sesión y el cumplimiento de series respecto de lo programado.

2. Dado un entrenador con alumnos activos, cuando consulta las métricas de evolución de entrenamiento de un alumno, entonces debe poder seleccionar el gráfico por grupo muscular, por entrenamiento, o por semana. El eje temporal se agrupa por entrenamiento (un punto por sesión finalizada) o por semana (un punto por semana calendario); el grupo muscular filtra la tabla de ejercicios y se grafica en las series semanales por grupo. Solo cuentan las sesiones finalizadas. El período se elige entre 4 semanas, 12 semanas (por defecto) y todo el historial, alineado a semanas calendario. Se muestra en el detalle del alumno. Ver la sesión de clarificaciones 2026-11-16.


---

### Historia de usuario 11 - [US-32: ver alumnos con riesgo de abandono] (Prioridad: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero ver los alumnos con riesgo de abandono,
 para poder crear incentivos y evitar que abandonen

**Por qué esta prioridad**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Prueba independiente**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Escenarios de aceptación**:

1. Dado un entrenador con alumnos activos, cuando un alumno no realizó el reporte del entrenamiento por 5 entrenamientos o 2 semanas (lo que ocurra primero), entonces el entrenador recibe una alerta de posible abandono

2. Dado un entrenador con alumnos activos, cuando tiene alumnos proximos a abandonar, entonces el sistema debe mostrar a estos alumnos primeros en el listado.


---

### Casos límite

- ¿Qué ocurre si un alumno reporta dolor en la misma zona durante dos sesiones consecutivas? El sistema eleva la alerta a nivel crítico en el panel del entrenador y sugiere revisar ejercicios vinculados a esa articulación.

- ¿Cuándo se marca un alumno con 'riesgo de abandono'? Cuando transcurren más de 7 días consecutivos sin que el alumno registre actividad estando su plan activo.

- ¿Cómo se asegura el canal de comunicación? Solo pueden enviarse mensajes alumnos y entrenadores con vínculo de entrenamiento vigente; la baja del vínculo inhabilita el envío de nuevos mensajes.



## Requisitos *(obligatorio)

### Requisitos funcionales

- **FR-001**: El sistema DEBE mostrar el listado de alumnos activos con su estado actual y paquete contratado (US-18).

- **FR-002**: El sistema DEBE permitir buscar alumnos activos por nombre y apellido (US-19), sin distinguir mayúsculas ni acentos y mostrando todos los alumnos cuando el campo esté vacío.

- **FR-003**: El sistema DEBE permitir filtrar alumnos según el paquete contratado (US-20), mostrando el filtro solo cuando haya más de un paquete registrado e indicando los cupos ocupados de cada paquete.

- **FR-004**: El sistema DEBE proveer un canal de comunicación directo entre entrenador y alumno (US-21), integrando las consultas técnicas sobre ejercicios provenientes de US-62 con tarjetas referenciales al ejercicio consultado (Decisión Alternativa B).

- **FR-005**: El sistema DEBE permitir al entrenador visualizar la rutina del día de cada alumno activo con su estado (No comenzada, Entrenando, Finalizada) y los tiempos y cargas de cada serie registrada (US-22).

- **FR-006**: El sistema DEBE contrastar métricas planificadas vs obtenidas por rutina (cargas, repeticiones, series) (US-24).

- **FR-007**: El sistema DEBE permitir ajustar las variables de la próxima sesión en base a los reportes del alumno (US-26).

- **FR-008**: El sistema DEBE permitir analizar los reportes de molestia y dolor del alumno por ejercicio, rutina y grupo muscular (US-28), y la evolución de cargas y RPE (US-30).

- **FR-009**: El sistema DEBE disparar alertas automáticas de seguridad ante reportes de dolor, molestias repetidas o esfuerzo excesivo (US-29).

- **FR-010**: El sistema DEBE alertar al entrenador y mostrar primero a los alumnos con riesgo de abandono: 5 entrenamientos sin reportar o 2 semanas sin reportes, lo que ocurra primero (US-32).



### Entidades principales *(incluir si la feature involucra datos)

- **TrainerDashboardOverview**: Vista consolidada de cartera de alumnos activos, clasificados por estado de actividad y paquete contratado.

- **TrainerStudentChat**: Canal de mensajería directa entre el entrenador y su alumno vinculado, que aloja tanto la comunicación general (US-21) como los hilos contextuales de dudas técnicas sobre ejercicios (US-62).

- **SafetyAlert**: Alerta automática generada por dolor agudo, molestias reiteradas en la misma articulación o RPE extremo consecutivo.

- **AbandonmentRiskAlert**: Indicador de riesgo de deserción activado cuando un alumno supera un umbral de días sin registrar entrenamientos.

- **SessionAdjustmentLog**: Registro de modificaciones aplicadas a la próxima sesión de un alumno en respuesta a sus reportes previos.



## Criterios de éxito *(obligatorio)

### Resultados medibles

- **SC-001**: Las alertas de dolor agudo aparecen destacadas en el panel del entrenador de forma inmediata.

- **SC-002**: El entrenador puede consultar el historial comparativo de cargas de un alumno en menos de 2 clics.

- **SC-003**: El ajuste de una sesión futura se refleja instantáneamente en la vista del alumno sin desincronizaciones.



## Supuestos

- El entrenador consulta su panel periódicamente desde web o móvil para supervisar a su cartera de alumnos.

- El cálculo de riesgo de abandono se actualiza diariamente según la fecha de última sesión registrada.


