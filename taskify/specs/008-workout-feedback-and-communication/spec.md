# Feature Specification: Reporte Post-Sesión, Mapa de Molestias y Feedback Técnico

**Feature Branch**: `008-workout-feedback-and-communication`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Cierre de sesión de entrenamiento por parte del alumno: calificación del esfuerzo percibido (escala RPE), señalamiento de sensaciones en mapa corporal interactivo (carga normal, molestia o dolor), resumen de tonelaje levantado, consultas técnicas sobre ejercicios y recepción de feedback del entrenador.

**User Stories Cubiertas**: US-60, US-61, US-62, US-63, US-64

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-60: Reporte de esfuerzo percibido (RPE) post-sesión] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero calificar mi esfuerzo percibido en una escala de 1 a 10 al finalizar la rutina, para que mi entrenador ajuste las cargas de mis próximos entrenamientos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que finaliza su rutina, cuando el sistema le solicita el reporte, entonces debe calificar el esfuerzo de la sesión en escala RPE del 1 al 10.

2. Dado un alumno que no completa la calificación de RPE, cuando finaliza la rutina, entonces esta queda marcada como ""Finalizada sin reporte"" y el sistema se lo recuerda en su próxima sesión.

3. Dado un alumno que reporta su RPE, cuando lo envía, entonces el dato queda disponible en el panel de seguimiento del entrenador junto con el resto de las métricas de la sesión.


---

### User Story 2 - [US-61: Reporte de molestias o dolor en mapa corporal] (Priority: P2, Estimación: 4 SP)

Como alumno,
 quiero marcar en un mapa corporal las zonas donde siento carga normal, molestia o dolor, durante o al final de la sesión,
 para que mi entrenador identifique rápidamente posibles riesgos de lesión.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno finalizando su sesión, cuando accede al mapa corporal, entonces puede seleccionar una o más zonas y clasificar la sensación como "carga normal", "molestia" o "dolor".

2. Dado un alumno ejecutando un ejercicio, cuando presiona "Reportar dolor", entonces puede marcar la zona en el mapa corporal y el sistema le ofrece la variante segura del ejercicio (US-53), si existe, o saltear el ejercicio.

3. Dado un alumno que reporta "dolor", cuando lo registra, entonces se genera la alerta al entrenador definida en US-29.

4. Dado un alumno o un entrenador consultando el historial de reportes por zona, cuando lo solicitan, entonces el sistema lo muestra con fecha, sesión y ejercicio asociados.


---

### User Story 3 - [US-62: Consultas técnicas sobre un ejercicio y respuesta del entrenador] (Priority: P2, Estimación: 4 SP)

Como alumno,
 quiero dejar comentarios o dudas sobre un ejercicio específico de mi rutina y recibir la respuesta de mi entrenador,
 para corregir mi técnica sin tener que mandar mensajes por fuera de la app.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno durante o después de su sesión, cuando accede a un ejercicio, entonces puede escribir un comentario o duda asociado a ese ejercicio.

2. Dado un alumno que envía una consulta, cuando la envía, entonces el entrenador recibe una notificación y la ve en una bandeja centralizada de consultas pendientes, agrupadas por alumno.

3. Dado un entrenador que responde una consulta, cuando la responde, entonces puede fijarla como "nota técnica" del ejercicio, y el alumno la ve obligatoriamente al iniciar ese ejercicio en su próxima sesión.

4. Dado un alumno o un entrenador consultando un ejercicio, cuando lo visualizan, entonces ven el historial de consultas y respuestas de ese ejercicio.


---

### User Story 4 - [US-63: Resumen de la sesión finalizada] (Priority: P2, Estimación: 2 SP)

Como alumno,
 quiero ver un resumen al terminar la sesión con lo que logré,
 para sentir satisfacción por el esfuerzo cumplido y saber cómo me fue.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que finaliza su sesión, cuando el sistema genera el resumen, entonces muestra el tonelaje total, la duración total y las series completadas frente a las programadas.

2. Dado un alumno que logró uno o más PRs en la sesión, cuando ve el resumen, entonces los PRs se muestran destacados.

3. Dado un alumno que finaliza su sesión, cuando ve el resumen, entonces ve su racha actualizada (US-68) y los logros desbloqueados en la sesión (US-67).


---

### User Story 5 - [US-64: Feedback sobre el esfuerzo reportado] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero recibir una devolución sobre el esfuerzo que reporté después de la sesión, para saber si podría haber rendido más o si debo ajustar la intensidad en la próxima.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que reportó su RPE al finalizar una sesión, cuando el entrenador revisa el reporte, entonces puede dejarle una devolución indicando si podría haber exigido más o menos esfuerzo.

2. Dado un alumno con una devolución disponible, cuando abre su próxima sesión, entonces puede visualizarla.

3. Dado un alumno sin devoluciones pendientes, cuando consulta la sección de feedback, entonces el sistema lo indica claramente en lugar de mostrarla vacía.


---

### Edge Cases

- ¿Qué ocurre si el alumno marca una zona con 'dolor agudo' en el mapa corporal? El sistema registra la criticidad y genera una alerta de seguridad prioritaria en el panel del entrenador.

- ¿Qué ocurre si el alumno finaliza el entrenamiento sin calificar el RPE? El sistema solicita la calificación mediante un diálogo simple pero permite continuar si el usuario decide omitirlo.

- ¿Cómo se calculan las métricas del resumen de sesión? El sistema suma el volumen total (peso × repeticiones de todas las series completadas) y lo compara con el promedio histórico del alumno.

- ¿Cómo interactúa la consulta técnica con el canal general de mensajes? (Decisión Alternativa B): Al enviar una duda técnica sobre un ejercicio (US-62), se genera un mensaje contextual en el chat general entrenador–alumno (US-21) con una tarjeta que referencia al ejercicio y serie ejecutada. El entrenador puede responder directamente desde el chat o desde la ficha del ejercicio, con la opción de fijar su respuesta como 'nota técnica' que el alumno verá obligatoriamente al iniciar dicho ejercicio en su próxima sesión.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al alumno calificar su esfuerzo percibido en escala RPE de 1 a 10 al finalizar la sesión (US-60).

- **FR-002**: El sistema DEBE proveer un mapa corporal interactivo para marcar zonas con carga normal, molestia o dolor (US-61).

- **FR-003**: El sistema DEBE permitir al alumno formular dudas o comentarios técnicos asociados a un ejercicio específico (US-62), integrando el mensaje en el canal de chat general (US-21) con tarjeta contextual del ejercicio (Decisión Alternativa B).

- **FR-004**: El sistema DEBE permitir al entrenador responder la consulta técnica y fijar su respuesta como 'nota técnica' vinculada al ejercicio, la cual se mostrará de forma obligatoria al alumno al iniciar ese ejercicio en su próxima sesión (US-62).

- **FR-005**: El sistema DEBE mostrar un resumen post-sesión con volumen total levantado y comparación histórica (US-63).

- **FR-006**: El sistema DEBE permitir al entrenador enviar feedback sobre el esfuerzo y ejecución reportados por el alumno (US-64).



### Key Entities *(include if feature involves data)*

- **PostWorkoutReport**: Reporte final de sesión que consolida hora de finalización, duración total, tonelaje levantado y valor RPE (1 a 10).

- **BodyMapPainReport**: Mapa anatómico corporal donde el alumno marca puntos con tres niveles de sensación: carga muscular normal, molestia leve o dolor agudo.

- **ExerciseTechnicalQuery**: Consulta técnica sobre un ejercicio vinculada a la sesión y transmitida como mensaje estructurado al canal general de chat (US-21), con estado de respuesta y bandera de fijación como nota técnica.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El reporte post-sesión completo puede completarse en menos de 45 segundos para garantizar adherencia.

- **SC-002**: Los reportes de dolor se transmiten de inmediato al módulo de monitoreo del entrenador.

- **SC-003**: Las dudas técnicas quedan vinculadas de forma contextual al ejercicio y a la serie correspondiente.



## Assumptions

- La escala RPE sigue el estándar de percepción de esfuerzo de 1 (muy suave) a 10 (esfuerzo máximo sin repeticiones en reserva).

- El mapa corporal cubre las vistas anterior y posterior del cuerpo humano.


