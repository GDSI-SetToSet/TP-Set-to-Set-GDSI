# Feature Specification: Búsqueda de Entrenadores, Perfiles Públicos y Solicitudes de Alta

**Feature Branch**: `004-discovery-and-matchmaking`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Flujo de descubrimiento y contratación donde el alumno busca y filtra entrenadores, consulta perfiles y tarifas, selecciona un paquete y envía su solicitud; y el entrenador revisa las solicitudes recibidas para aceptarlas o rechazarlas.

**User Stories Cubiertas**: US-44, US-46, US-47, US-48, US-06, US-07, US-49

## Clarifications

### Session 2026-10-23

- Q: Si el entrenador edita la tarifa o archiva un paquete mientras hay una solicitud pendiente o un vínculo activo, ¿qué arancel queda acordado? → A: El vigente al enviar la solicitud. La solicitud guarda una copia de la tarifa y la moneda al crearse, el vínculo la hereda al aceptarse y ninguno de los dos se recalcula a partir del paquete (no retroactividad, spec 002 US-03).
- Q: ¿Se puede enviar una solicitud por un paquete archivado? → A: No. Solo se pueden seleccionar paquetes activos (`is_active = true`); las solicitudes pendientes de un paquete que se archiva después siguen siendo válidas con su arancel guardado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-44: Búsqueda y filtrado de entrenadores] (Priority: P1, Estimación: 4 SP)

Como alumno, quiero buscar entrenadores en la plataforma utilizando filtros de especialidad, precio, ubicación y disponibilidad, para encontrar un profesional que se adapte a mis objetivos y presupuesto.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno en el buscador, cuando aplica filtros de especialidad, precio y disponibilidad, entonces el sistema muestra los entrenadores que cumplen esos criterios.

2. Dado un alumno que aplica filtros sin resultados coincidentes, cuando realiza la búsqueda, entonces el sistema lo indica y sugiere ampliar la búsqueda.

3. Dado un alumno consultando los resultados, cuando los visualiza, entonces ve un resumen del perfil de cada entrenador (foto, especialidad, tarifa y cupos disponibles).

4. Dado un alumno que combina más de un filtro, cuando modifica alguno de ellos, entonces el sistema actualiza los resultados dinámicamente.


---

### User Story 2 - [US-46: Visualización del perfil público del entrenador] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero visualizar el perfil completo de un entrenador (biografía, metodología, certificaciones y reseñas), para evaluar si su forma de entrenar se ajusta a lo que busco antes de enviar una solicitud.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que entra al perfil de un entrenador, cuando lo visualiza, entonces puede ver su biografía, especialidad, certificaciones y tarifas publicadas.

2. Dado un entrenador sin cupos disponibles, cuando un alumno visita su perfil, entonces el sistema muestra la etiqueta ""Sin cupos disponibles"" y deshabilita el botón de solicitud.

3. Dado un entrenador con alumnos activos o reseñas, cuando un alumno visita su perfil, entonces puede ver esa información.


---

### User Story 3 - [US-47: Selección de plan o paquete de entrenamiento] (Priority: P1, Estimación: 2 SP)

Como alumno, quiero seleccionar el paquete de entrenamiento y la tarifa que ofrece un entrenador, para elegir la opción que se ajusta a mi presupuesto y disponibilidad antes de solicitar el entrenamiento.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno en el perfil de un entrenador con más de un paquete publicado, cuando consulta los paquetes, entonces el sistema le permite elegir cuál desea contratar.

2. Dado un alumno que selecciona un paquete, cuando confirma la elección, entonces el sistema la asocia a la solicitud que enviará a ese entrenador.

3. Dado un alumno que no selecciona ningún paquete, cuando intenta enviar la solicitud, entonces el sistema no se lo permite y le pide elegir uno.


---

### User Story 4 - [US-48: Envío de solicitud de entrenamiento a un entrenador] (Priority: P1, Estimación: 4 SP)

Como alumno, quiero enviar una solicitud para ser entrenado por un profesional que elegí, para iniciar el proceso de contratación de sus servicios.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que envía una solicitud a un entrenador, cuando la solicitud se envía, entonces el entrenador recibe una notificación junto con el perfil, objetivos y cuestionario de salud del alumno.

2. Dado un entrenador sin cupos disponibles, cuando un alumno intenta enviarle una solicitud, entonces el sistema no la permite y lo informa al alumno.

3. Dado un alumno con una solicitud pendiente, cuando consulta su perfil, entonces puede visualizar el estado (""Pendiente"", ""Aceptada"" o ""Rechazada"").

4. Dado un alumno cuya solicitud fue rechazada, cuando consulta el resultado, entonces puede ver el mensaje explicativo del entrenador (si lo hubiera) y enviar una nueva solicitud a otro profesional.


---

### User Story 5 - [US-06: ver solicitudes de alumnos] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero ver las solicitudes pendientes de alumnos que quieren contratarme como entrenador,
 para evaluar los objetivos del alumno y ver si coinciden con mi perfil de entrenador.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Se deben poder ver todas las solicitudes pendientes de alumnos para el mes.

2. Al llegar una nueva solicitud, se debe reflejar en la aplicación aumentando el número de solicitudes pendientes.

3. Al entrar a una solicitud, se debe poder ver el perfil del alumno y sus objetivos.

4. Si el cupo mensual del entrenador está lleno, entonces no deben entrar nuevas solicitudes


---

### User Story 6 - [US-07: gestionar solicitudes de alumnos] (Priority: P1, Estimación: 5 SP)

Como entrenador personal,
 quiero poder aceptar o rechazar las solicitudes de alumnos,
 para seleccionar aquellos alumnos cuyos objetivos estén más alineados a mi forma de entrenar.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Al ingresar a la solicitud de un alumno, debe haber una opción para aceptar o rechazar su solicitud.

2. Al aceptar una solicitud, entonces el alumno debe aparecer en el listado de activos del entrenador.

3. Al aceptar una solicitud, el cupo mensual del entrenador se actualiza y la solicitud ya no está visible para el entrenador.

4. Si el cupo mensual del entrenador está lleno, al intentar aceptar un nuevo alumno el sistema no permite y notifica al entrenador que su cupo ya está completo.

5. Al rechazar una solicitud, entonces el cupo mensual del entrenador no se actualiza y la solicitud ya no está visible para el entrenador


---

### User Story 7 - [US-49: Confirmación y bienvenida al programa del entrenador] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero recibir una confirmación y un mensaje de bienvenida cuando un entrenador acepta mi solicitud, para saber que ya puedo comenzar a entrenar con él.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador que acepta una solicitud, cuando la confirma, entonces el alumno recibe una notificación de bienvenida al programa.

2. Dado un alumno cuya solicitud fue aceptada, cuando consulta su perfil, entonces ve al entrenador asignado y el plan contratado.

3. Dado un alumno recién aceptado, cuando el entrenador ya cargó su primera rutina, entonces el alumno obtiene acceso inmediato a ella.


---

### Edge Cases

- ¿Qué ocurre si un alumno intenta enviar una solicitud a un entrenador que no tiene cupos disponibles? El sistema bloquea el envío e indica que el profesional no posee cupos libres.

- ¿Qué ocurre con las solicitudes pendientes cuando el cupo llega a 0? (Decisión Alternativa A): Las solicitudes pendientes recibidas previamente permanecen visibles en la bandeja del entrenador, pero el botón 'Aceptar' queda bloqueado e inhabilitado, mostrando la advertencia 'Cupos agotados; libere un cupo para poder aceptar'. El entrenador puede rechazarlas manualmente con motivo o mantenerlas a la espera de que se libere un cupo.

- ¿Qué sucede si el entrenador rechaza una solicitud o el alumno la cancela? (Revocación Inmediata de Datos de Salud): La solicitud cambia a estado 'REJECTED' o 'CANCELLED'. El permiso temporal de lectura del entrenador sobre el cuestionario de salud (US-41), molestias previas (US-42) y certificado médico (US-43) se revoca de inmediato en el backend. El entrenador conserva únicamente el registro de auditoría de la solicitud (nombre, fecha, motivo), sin acceso a los datos médicos del alumno.

- ¿Qué ocurre si un alumno intenta enviar una solicitud a un entrenador con el que ya tiene una solicitud pendiente o una suscripción activa? El sistema lo previene e informa el estado actual.

- ¿Qué ocurre si el alumno aplica filtros de búsqueda que no coinciden con ningún entrenador? El sistema muestra un mensaje indicando la ausencia de resultados y sugiere ampliar los criterios.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al alumno buscar entrenadores aplicando filtros combinados por especialidad, precio y disponibilidad (US-44).

- **FR-002**: El sistema DEBE mostrar en los resultados del buscador un resumen del perfil de cada entrenador (foto, tarifas, especialidad y cupos) (US-44).

- **FR-003**: El sistema DEBE permitir al alumno consultar el perfil público completo del entrenador con certificaciones, metodología y tarifas (US-46).

- **FR-004**: El sistema DEBE permitir al alumno seleccionar un paquete de entrenamiento publicado (US-47).

- **FR-005**: El sistema DEBE permitir al alumno enviar una solicitud formal de entrenamiento adjuntando su perfil y objetivos (US-48).

- **FR-006**: El sistema DEBE listar al entrenador las solicitudes entrantes pendientes, otorgando permiso de lectura temporal exclusivo sobre la información básica, cuestionario de salud y apto médico para evaluación (US-06).

- **FR-007**: El sistema DEBE permitir al entrenador aceptar o rechazar solicitudes de alumnos (US-07). Si los cupos están agotados, el botón 'Aceptar' se bloquea manteniendo las solicitudes en bandeja para gestión manual (Decisión Alternativa A).

- **FR-008**: Al aceptar una solicitud, el sistema DEBE descontar un cupo disponible y emitir el mensaje de bienvenida y confirmación al alumno (US-07, US-49).

- **FR-009**: El sistema DEBE revocar de forma inmediata e irreversible el acceso del entrenador a los datos de salud del alumno (cuestionario, molestias, apto médico) en el backend si la solicitud es rechazada o cancelada (US-06, US-07, US-48, Constitución).

- **FR-010**: Al crear una solicitud, el sistema DEBE guardar en ella la tarifa mensual y la moneda vigentes del paquete seleccionado, y al aceptarla DEBE copiarlas al vínculo. Editar la tarifa o archivar el paquete después no modifica el arancel de solicitudes ya enviadas ni de vínculos existentes. Solo se pueden solicitar paquetes activos (US-47, US-48, US-07; spec 002 US-03).



### Key Entities *(include if feature involves data)*

- **TrainerSearchFilter**: Criterios combinables de búsqueda: especialidad, rango de tarifa, disponibilidad horaria y modalidad.

- **EnrollmentRequest**: Solicitud de vinculación enviada por un alumno a un entrenador para un paquete específico, con estado ('PENDING', 'ACCEPTED', 'REJECTED'), fecha, mensaje inicial y el arancel acordado (tarifa y moneda del paquete al momento de enviarla).

- **OnboardingWelcome**: Mensaje de confirmación y bienvenida generado automáticamente al aceptar una solicitud, con instrucciones iniciales.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La actualización de resultados en el buscador ante cambios de filtros responde en menos de 1 segundo.

- **SC-002**: No es posible enviar solicitudes a entrenadores con cupos agotados bajo ninguna condición.

- **SC-003**: La aceptación de una solicitud vincula formalmente al alumno con el entrenador y habilita los flujos de planificación y seguimiento.



## Assumptions

- El alumno puede enviar solicitudes a diferentes entrenadores siempre que no tenga una relación activa incompatible.

- La vinculación inicial no requiere pago previo en la app; las cuotas se gestionan en el módulo de pagos informales.


