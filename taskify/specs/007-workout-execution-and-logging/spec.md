# Feature Specification: Ejecución del Entrenamiento, Videos Embebidos y Registro de Series

**Feature Branch**: `007-workout-execution-and-logging`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Experiencia en vivo del alumno durante la sesión de entrenamiento: consulta de la rutina del día, reproducción embebida de videos técnicos, temporizador de descansos entre series, checklist rápida con un toque, memoria del peso anterior y detección automática de récords personales (PR).

**User Stories Cubiertas**: US-50, US-51, US-56, US-57, US-58, US-59

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-50: Visualización de la rutina del día] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero visualizar mi rutina del día con los ejercicios, series, repeticiones y duración estimada, para saber exactamente qué hacer al llegar al gimnasio.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1.Dado un alumno con una rutina asignada para el día, cuando abre la sesión del día, entonces ve el listado de ejercicios con series, repeticiones y peso objetivo.

2. Dado un alumno consultando su rutina del día, cuando la visualiza, entonces el sistema muestra la duración estimada total y de cada bloque.

3. Dado un alumno sin rutina asignada para el día, cuando ingresa a la sección correspondiente, entonces el sistema lo indica claramente en lugar de mostrar una pantalla vacía.


---

### User Story 2 - [US-51: Reproducción de video técnico del ejercicio] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero reproducir un video corto con la técnica y postura correcta de cada ejercicio, para ejecutar los movimientos de forma segura sin necesidad de asistencia presencial.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno viendo un ejercicio de su rutina con video vinculado, cuando presiona el botón de video, entonces el sistema lo reproduce dentro de la misma pantalla, sin salir de la aplicación.

2. Dado un ejercicio sin video vinculado, cuando el alumno lo consulta, entonces no se muestra el botón de video y se muestran la descripción, el músculo trabajado y las notas técnicas (US-52).

3. Dado un alumno reproduciendo un video, cuando lo pausa, adelanta o repite, entonces el control se mantiene dentro de la misma pantalla.

4. Dado un alumno que ve una variante segura (US-53), cuando esta tiene video, entonces puede reproducirlo de la misma forma.


---

### User Story 3 - [US-56: Temporizador de descansos entre series] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero que se inicie automáticamente un temporizador de descanso al finalizar cada serie, para respetar los tiempos de pausa indicados por mi entrenador sin tener que controlarlo manualmente.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que marca una serie como completada, cuando finaliza la serie, entonces el temporizador de descanso se inicia automáticamente con el tiempo configurado por el entrenador.

2. Dado un temporizador de descanso en curso, cuando finaliza el tiempo, entonces el sistema alerta al alumno (sonido o vibración).

3. Dado un temporizador de descanso en curso, cuando el alumno lo desea, entonces puede pausarlo, adelantarlo o reiniciarlo manualmente.


---

### User Story 4 - [US-57: Registro de peso, series y repeticiones con memoria del peso anterior] (Priority: P1, Estimación: 4 SP)

Como alumno, quiero cargar el peso levantado y las repeticiones logradas en cada serie, viendo el peso que usé la vez anterior, para monitorear mi sobrecarga progresiva sin tener que recordar mis cargas de memoria.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno cargando una serie, cuando ingresa a la pantalla de registro, entonces el sistema muestra como referencia el peso y repeticiones registrados en la sesión anterior del mismo ejercicio.

2. Dado un alumno que no ingresa peso ni repeticiones en una serie, cuando intenta marcarla, entonces el sistema no la marca como completada.

3. Dado un alumno que carga los datos de una serie, cuando los guarda, entonces se sincronizan de inmediato con el panel del entrenador.


---

### User Story 5 - [US-58: Checklist rápida de series completadas] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero tildar cada serie de un ejercicio con un solo toque al completarla, para registrar mi avance de forma ágil sin interrumpir el ritmo del entrenamiento.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno ejecutando su rutina, cuando completa una serie, entonces puede marcarla con un control de un solo toque.

2. Dado un alumno que tilda una serie, cuando la marca, entonces el sistema la asocia automáticamente al peso y repeticiones cargados para esa serie.

3. Dado un alumno que tildó una serie por error, cuando lo hace antes de finalizar la sesión, entonces puede destildarla.


---

### User Story 6 - [US-59: Aviso de nuevo récord personal (PR)] (Priority: P2, Estimación: 3 SP)

Como alumno, quiero recibir un aviso en pantalla cuando registro un nuevo récord personal, para sentir que estoy progresando y mantener la motivación.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que carga una serie que supera su récord histórico para ese ejercicio, cuando la registra, entonces el sistema muestra un aviso destacado en pantalla.

2. Dado un alumno que logra un nuevo récord, cuando el sistema lo detecta, entonces lo guarda y reemplaza al anterior en el historial de PRs.

3. Dado un alumno que logra un nuevo PR, cuando el sistema lo registra, entonces el entrenador recibe una alerta


---

### Edge Cases

- ¿Qué ocurre si es la primera vez que el alumno ejecuta un ejercicio? La vista no muestra peso anterior y presenta un indicador para registrar la carga base inicial.

- ¿Cómo se reproduce el video técnico sin interrumpir el flujo? El reproductor se despliega embebido en la misma pantalla del ejercicio, sin redirigir al navegador ni a apps externas.

- ¿Qué sucede si el alumno supera su peso máximo histórico en una serie? Al tildar la serie, el sistema detecta el récord y muestra de inmediato una felicitación/aviso de PR en pantalla.

- ¿Qué ocurre si el alumno pausa o modifica el tiempo de descanso? El temporizador permite pausar, reiniciar o ajustar los segundos restantes sin bloquear la interfaz.

- ¿Qué ocurre si el alumno intenta acceder a la rutina del día teniendo la suscripción vencida? (Decisión Alternativa A): El sistema bloquea el acceso a la ejecución de nuevas rutinas y muestra una advertencia de suscripción vencida, permitiendo únicamente consultar el historial de entrenamientos pasados en modo solo lectura.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mostrar al alumno la rutina correspondiente al día con ejercicios, series, repeticiones y descansos, validando que la suscripción esté activa para permitir la ejecución y registro (US-50, Decisión Alternativa A).

- **FR-002**: El sistema DEBE reproducir videos técnicos vinculados directamente dentro de la pantalla del ejercicio de forma embebida (US-51).

- **FR-003**: El sistema DEBE iniciar un temporizador de descanso al completar cada serie según el tiempo configurado por el entrenador (US-56).

- **FR-004**: El sistema DEBE permitir registrar el peso y las repeticiones de cada serie mostrando el peso usado en la sesión anterior (US-57).

- **FR-005**: El sistema DEBE permitir tildar cada serie completada con un solo toque (checklist rápida) (US-58).

- **FR-006**: El sistema DEBE detectar automáticamente y notificar en pantalla el logro de un nuevo récord personal (PR) (US-59).



### Key Entities *(include if feature involves data)*

- **DailyWorkoutView**: Vista interactiva de la sesión del día con bloques de ejercicios, series programadas, descansos y duración estimada.

- **SetExecutionLog**: Registro de ejecución por serie: número de serie, peso utilizado (kg), repeticiones cumplidas, estado de completitud (checklist) y timestamp.

- **RestTimer**: Temporizador de pausa entre series con inicio automático o manual y notificación de fin de descanso.

- **PersonalRecordEvent**: Evento disparado cuando el kilaje o repetición lograda en un ejercicio supera la marca máxima histórica del alumno.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El registro de una serie con un toque responde en menos de 200 ms para no entorpecer el ritmo del entrenamiento.

- **SC-002**: El temporizador de descanso emite alerta visual y auditiva/háptica al llegar a cero.

- **SC-003**: El 100% de los récords personales legítimos son reconocidos y destacados en pantalla al confirmar la serie.



## Assumptions

- El alumno utiliza su dispositivo móvil en el gimnasio durante la ejecución de los ejercicios.

- Los videos de técnica no consumen almacenamiento interno de la app al transmitirse vía streaming embebido.


