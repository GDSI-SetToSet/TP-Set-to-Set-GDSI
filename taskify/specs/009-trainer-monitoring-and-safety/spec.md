# Feature Specification: Panel de Monitoreo del Entrenador, Métricas y Alertas de Seguridad

**Feature Branch**: `009-trainer-monitoring-and-safety`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Centro de control del entrenador para supervisar alumnos activos, buscar y filtrar por paquete, comunicarse por canal directo, comparar ejecución planificada vs realizada, analizar cargas y RPE, ajustar próximas sesiones y recibir alertas tempranas de dolor y de riesgo de abandono.

**User Stories Cubiertas**: US-18, US-19, US-20, US-21, US-22, US-24, US-26, US-28, US-29, US-30, US-32

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-18: visualización de alumnos activos] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero visualizar el listado de alumnos activos que tengo,
 para poder llevar un monitoreo general y particular de cada uno de mis alumnos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador, cuando ingresa a la sección "Alumnos", entonces debe visualizar todos sus alumnos activos.

2. Dado un entrenador sin alumnos activos, cuando ingresa a la sección "Alumnos", entonces el sistema debe indicar que no tiene alumnos activos.

3. Dado un entrenador con alumnos activos, cuando selecciona un alumno en particular, entonces se muestra el perfil del alumno, paquete contratado, objetivos, limitaciones, rutinas cargadas y métricas del alumno.

4. Dado un entrenador con alumnos con alertas de seguridad sin revisar (US-29), cuando ingresa a "Alumnos", entonces esos alumnos aparecen primero y destacados.


---

### User Story 2 - [US-19: buscar por alumno] (Priority: P1, Estimación: 2 SP)

Como entrenador personal,
 quiero poder buscar alumnos dentro de mi listado de alumnos activos,
 para encontrar y consultar el perfil de un alumno en particular.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando el entrenador busca por nombre y apellido un alumno existente, entonces el sistema devuelve el alumno buscado.

2. Dado un entrenador con alumnos activos, cuando el entrenador busca por nombre y apellido un alumno inexistente, entonces el sistema no devuelve a ningun alumno.


---

### User Story 3 - [US-20: filtrar alumnos por paquete contratado] (Priority: P2, Estimación: 2 SP)

Como entrenador personal,
 quiero filtrar a mis alumnos por paquete contratado,
 para poder ver los cupos ocupados en cada uno de mis planes.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con un solo paquete de entrenamiento cargado, cuando entra a la sección de "Alumnos", entonces no puede filtrar por paquete ya que solamente hay un único paquete

2. Dado un entrenador con más de un paquete de entrenamiento registrado, cuando entra a la sección de "Alumnos", entonces el sistema permite filtrar por cada uno de los paquetes registrados.

3. Dado un entrenador con más de un paquete de entrenamiento registrado, cuando entra a la sección de "Alumnos" y filtra por un paquete en particular, entonces el sistema solamente debe mostrar los alumnos que hayan contratado dicho paquete.


---

### User Story 4 - [US-21: Canal de mensajes entrenador–alumno] (Priority: P1, Estimación: 4 SP)

Como entrenador personal o alumno,
 quiero intercambiar mensajes con mi alumno o mi entrenador dentro de la aplicación,
 para coordinar cambios y resolver dudas generales sin usar WhatsApp.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador y su alumno activo, cuando uno ingresa al perfil del otro, entonces puede abrir la conversación entre ambos.

2. Dado un mensaje enviado, cuando el destinatario no tiene la aplicación abierta, entonces recibe una notificación y ve el mensaje al abrir la conversación.

3. Dado un entrenador o un alumno en la conversación, cuando la abre, entonces ve el historial completo de mensajes.

4. Dado un alumno dado de baja (US-35), cuando intenta enviar un mensaje, entonces el sistema no lo permite.


---

### User Story 5 - [US-22: seguimiento de rutinas de alumnos] (Priority: P1, Estimación: 4 SP)

Como entrenador personal,
 quiero realizar un seguimiento de las rutinas del día del alumno,
 para conocer el estado del entrenamiento de mi alumno.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando entra a la sección de "Rutinas del día", entonces debe poder ver todas las rutinas de sus alumnos para ese día.

2. Dado un entrenador con alumnos activos, cuando entra a una rutina en particular, entonces puede ver el estado de la rutina (No comenzada, Entrenando, Finalizada)

3. Dado un entrenador con alumnos activos, cuando entra a una rutina en estado "Entrenando" o "Finalizada", entonces debe poder ver los tiempos y cargas de cada serie/ejercicio.


---

### User Story 6 - [US-24: ver métricas esperadas vs obtenidas por rutina] (Priority: P2, Estimación: 3 SP)

Como entrenador personal,
 quiero comparar las métricas esperadas del entrenamiento con las métricas obtenidas,
 para realizar un seguimiento de los entrenamientos de mis alumnos y adaptar las rutinas en base a lo obtenido.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando entra a una rutina en estado "Finalizada", entonces puede ver las métricas de tiempos y cargas del alumno y compararlas con entrenamientos previos del alumno.


---

### User Story 7 - [US-26: Ajustar la próxima sesión del alumno a partir de sus reportes] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero ajustar la próxima sesión de un alumno a partir de lo que reportó en la anterior,
 para adaptar cargas o ejercicios según su rendimiento, sus molestias y sus pedidos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador revisando una sesión "Finalizada" (cargas, RPE, molestias y pedidos de reemplazo), cuando decide ajustar, entonces puede modificar cargas, series o reemplazar ejercicios de la próxima sesión programada desde esa misma pantalla.

2. Dado un ajuste guardado, cuando el alumno abre su próxima sesión, entonces ve los ejercicios ajustados con la marca "Ajustado por tu entrenador" y la nota, si la hay.

3. Dado un ajuste que incluye un ejercicio contraindicado por las restricciones del alumno (US-42), cuando el entrenador intenta guardarlo, entonces el sistema muestra una advertencia.

4. Dado un alumno con una sesión en curso, cuando el entrenador guarda un ajuste, entonces el cambio se aplica a partir de la próxima sesión y no modifica la que está en curso.


---

### User Story 8 - [US-28: analizar cargas reportadas por alumnos] (Priority: P1, Estimación: 4 SP)

Como entrenador personal,
 quiero poder analizar los reportes de carga de los alumnos después de cada entrenamiento,
 para poder llevar un mejor seguimiento de cada alumno y adaptar los entrenamientos para prevenir lesiones.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces puede ver todos sus reportes de molestia y dolor asociados al ejercicio o rutina correspondiente.

2. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces puede ver un gráfico de molestia y dolor por grupo muscular y rutina/ejercicio.


---

### User Story 9 - [US-29: Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero recibir alertas inmediatas cuando un alumno reporta dolor, molestias repetidas o un esfuerzo excesivo,
 para actuar antes de que se produzca una lesión o una recaída.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que reporta "dolor" en una zona (durante el ejercicio o al finalizar la sesión, US-61), cuando lo registra, entonces el entrenador recibe una notificación inmediata con el alumno, la zona, el ejercicio y la sesión.

2. Dado un alumno que reporta "molestia" en la misma zona en 2 sesiones consecutivas, cuando registra el segundo reporte, entonces el entrenador recibe una alerta.

3. Dado un alumno que reporta un RPE de 9 o 10 (US-60), cuando lo envía, entonces el entrenador recibe una alerta de esfuerzo excesivo.

4. Dado un entrenador con alertas sin revisar, cuando abre el listado de alumnos (US-18), entonces esos alumnos aparecen primero y destacados hasta que marca la alerta como "Revisada" indicando la acción tomada (ajusté la rutina, contacté al alumno o sin acción).

5. Dado un alumno que reportó dolor, cuando el entrenador marca la alerta como revisada, entonces el alumno ve en su próxima sesión que su reporte fue revisado, junto con la nota del entrenador si la dejó.


---

### User Story 10 - [US-30: ver métricas de evolución de entrenamientos] (Priority: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero ver un gráfico de evolución de los entrenamientos de mis alumnos mostrando pesos levantados, repeticiones y series realizadas,
 para evaluar el avance y evolución de los entrenamientos de mis alumnos

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces debe poder ver un gráfico de evolución de peso levantado, repeticiones y series realizadas.

2. Dado un entrenador con alumnos activos, cuando consulta las métricas de evolución de entrenamiento de un alumno, entonces debe poder seleccionar el gráfico por grupo muscular, por entrenamiento, o por semana.


---

### User Story 11 - [US-32: ver alumnos con riesgo de abandono] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero ver los alumnos con riesgo de abandono,
 para poder crear incentivos y evitar que abandonen

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando un alumno no realizó el reporte del entrenamiento por 5 entrenamientos o 2 semanas (lo que ocurra primero), entonces el entrenador recibe una alerta de posible abandono

2. Dado un entrenador con alumnos activos, cuando tiene alumnos proximos a abandonar, entonces el sistema debe mostrar a estos alumnos primeros en el listado.


---

### Edge Cases

- ¿Qué ocurre si un alumno reporta dolor en la misma zona durante dos sesiones consecutivas? El sistema eleva la alerta a nivel crítico en el panel del entrenador y sugiere revisar ejercicios vinculados a esa articulación.

- ¿Cuándo se marca un alumno con 'riesgo de abandono'? Cuando transcurren más de 7 días consecutivos sin que el alumno registre actividad estando su plan activo.

- ¿Cómo se asegura el canal de comunicación? Solo pueden enviarse mensajes alumnos y entrenadores con vínculo de entrenamiento vigente; la baja del vínculo inhabilita el envío de nuevos mensajes.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mostrar el listado de alumnos activos con su estado actual y paquete contratado (US-18).

- **FR-002**: El sistema DEBE permitir buscar alumnos por nombre o email (US-19).

- **FR-003**: El sistema DEBE permitir filtrar alumnos según el paquete contratado (US-20).

- **FR-004**: El sistema DEBE proveer un canal de comunicación directo entre entrenador y alumno (US-21), integrando las consultas técnicas sobre ejercicios provenientes de US-62 con tarjetas referenciales al ejercicio consultado (Decisión Alternativa B).

- **FR-005**: El sistema DEBE permitir al entrenador visualizar la rutina activa y el avance de cada alumno (US-22).

- **FR-006**: El sistema DEBE contrastar métricas planificadas vs obtenidas por rutina (cargas, repeticiones, series) (US-24).

- **FR-007**: El sistema DEBE permitir ajustar las variables de la próxima sesión en base a los reportes del alumno (US-26).

- **FR-008**: El sistema DEBE permitir analizar la evolución de cargas y RPE reportados por el alumno (US-28, US-30).

- **FR-009**: El sistema DEBE disparar alertas automáticas de seguridad ante reportes de dolor, molestias repetidas o esfuerzo excesivo (US-29).

- **FR-010**: El sistema DEBE identificar y destacar alumnos con riesgo de abandono por inactividad prolongada (US-32).



### Key Entities *(include if feature involves data)*

- **TrainerDashboardOverview**: Vista consolidada de cartera de alumnos activos, clasificados por estado de actividad y paquete contratado.

- **TrainerStudentChat**: Canal de mensajería directa entre el entrenador y su alumno vinculado, que aloja tanto la comunicación general (US-21) como los hilos contextuales de dudas técnicas sobre ejercicios (US-62).

- **SafetyAlert**: Alerta automática generada por dolor agudo, molestias reiteradas en la misma articulación o RPE extremo consecutivo.

- **AbandonmentRiskAlert**: Indicador de riesgo de deserción activado cuando un alumno supera un umbral de días sin registrar entrenamientos.

- **SessionAdjustmentLog**: Registro de modificaciones aplicadas a la próxima sesión de un alumno en respuesta a sus reportes previos.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Las alertas de dolor agudo aparecen destacadas en el panel del entrenador de forma inmediata.

- **SC-002**: El entrenador puede consultar el historial comparativo de cargas de un alumno en menos de 2 clics.

- **SC-003**: El ajuste de una sesión futura se refleja instantáneamente en la vista del alumno sin desincronizaciones.



## Assumptions

- El entrenador consulta su panel periódicamente desde web o móvil para supervisar a su cartera de alumnos.

- El cálculo de riesgo de abandono se actualiza diariamente según la fecha de última sesión registrada.


