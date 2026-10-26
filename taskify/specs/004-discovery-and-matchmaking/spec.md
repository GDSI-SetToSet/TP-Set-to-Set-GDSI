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

### Session 2026-10-24

- Q: En US-06, ¿qué significa «solicitudes pendientes de alumnos para el mes»? → A: La bandeja del entrenador muestra todas las solicitudes en estado `PENDING` dirigidas a su perfil, ordenadas de forma descendente por fecha de creación (`created_at DESC`), independientemente del mes calendario en que se enviaron. "Para el mes" refiere a la contratación del servicio mensual del paquete, evitando descartar solicitudes pendientes de meses anteriores.
- Q: En US-04 y US-07, ¿cómo se define el «cupo mensual» del entrenador? → A: El cupo (`max_students`) es la capacidad máxima concurrente de alumnos activos (`TrainingRelationship` con `status == 'ACTIVE'`). No se reinicia automáticamente al inicio de mes calendario; se libera únicamente cuando un vínculo activo pasa a `TERMINATED` o `EXPIRED`.
- Q: ¿Cómo opera el bloqueo por cupos agotados en creación y aceptación? → A: 1) Creación (`POST /requests`): si `available_slots <= 0`, se bloquea el envío y responde HTTP 409 Conflict con mensaje `"Este entrenador no tiene cupos disponibles."`. 2) Existentes: las solicitudes `PENDING` previas permanecen visibles en la bandeja del entrenador; la UI deshabilita el botón "Aceptar" (`can_be_accepted = false`) mostrando `"Cupos agotados; libere un cupo para poder aceptar"`, manteniendo habilitado el botón de rechazo. 3) Aceptación forzada (`POST /requests/{id}/accept`): si no hay cupo al intentar aceptar, responde HTTP 409 Conflict con mensaje `"Cupos agotados; libere un cupo para poder aceptar."`.
- Q: ¿Cómo se actualiza la bandeja y el contador de solicitudes pendientes? → A: Al cargar la pantalla, al navegar a la misma y mediante refresco manual. El MVP no incorpora WebSockets, SSE ni infraestructura adicional en tiempo real.
- Q: ¿Qué datos del alumno están disponibles para evaluación en US-06 y cómo se autoriza su acceso? → A: El entrenador puede visualizar la información básica del alumno (nombre, apellido, teléfono, fecha de nacimiento/edad y mensaje introductorio) en el detalle de la solicitud, y tiene autorización temporal para consultar sus objetivos (`GET /students/{id}/goals`), cuestionario de salud (`GET /students/{id}/health-questionnaire`) y descargar su apto médico (`GET /students/{id}/medical-clearance/download`). La autorización se valida en el backend mediante `trainer_has_access`, verificando que el entrenador autenticado sea el destinatario de una solicitud `PENDING` o de un vínculo `ACTIVE`. No se habilita acceso público ni genérico a perfiles.
- Q: En US-07, ¿qué abarca «el alumno debe aparecer en el listado de activos»? → A: La aceptación en US-07 crea formalmente el vínculo `TrainingRelationship` con `status = 'ACTIVE'`, descuenta un cupo disponible y retira la solicitud de la bandeja de pendientes. La pantalla completa de alumnos activos, su buscador y filtros por paquete pertenecen a US-18 (spec 009).
- Q: En US-07, ¿el motivo de rechazo (`rejection_reason`) es obligatorio u opcional? → A: Es opcional en el backend y en la interfaz (se alinea con US-48 escenario 4: "mensaje explicativo, si lo hubiera"). La discrepancia con el contrato OpenAPI original (que lo requería obligatoriamente) se resuelve relajando el campo a opcional/nullable, sin que esto rompa compatibilidad con clientes o pruebas existentes.
- Q: ¿Cómo se gestiona la concurrencia y la idempotencia en la aceptación/rechazo? → A: La aceptación se procesa en una transacción atómica con bloqueo a nivel de fila (`with_for_update`) sobre el perfil del entrenador para evitar sobreasignación de cupos. Si una solicitud ya no está en estado `PENDING` (por ejemplo, ya fue aceptada, rechazada o cancelada), cualquier intento de resolverla nuevamente se rechaza con HTTP 409 Conflict (*"La solicitud ya fue procesada."*).

### Session 2026-10-25

- Q: ¿Cómo se entrega la notificación de bienvenida al alumno si el MVP no utiliza WebSockets ni SSE? → A: Siguiendo la arquitectura definida para US-06 (sesión 2026-10-24), las notificaciones se persisten en base de datos (`Notification`) al confirmarse la aceptación. El alumno las consume vía API (`GET /api/v1/students/me/notifications`) al iniciar sesión, abrir la app o refrescar su centro de notificaciones.
- Q: ¿Qué información del entrenador y plan contratado debe mostrarse en el perfil del alumno aceptado? → A: Debe exponer los datos del entrenador asignado (nombre, foto de perfil, especialidad y datos de contacto), el paquete contratado (nombre, descripción, tarifa acordada y moneda heredadas de forma inmutable), la fecha de inicio del vínculo y el estado actual de su programa.
- Q: En el escenario 3 de US-49, ¿cómo se vincula la primera rutina con el alumno recién aceptado? → A: Si el entrenador ya cargó y publicó una rutina (`status = 'PUBLISHED'` o `'ACTIVE'`) asociada al vínculo o al alumno, la consulta del plan activo devuelve la referencia de dicha rutina (`routine_id`, `routine_name`), permitiendo el acceso directo con un clic. Si el entrenador aún no la cargó, la interfaz muestra el estado amigable *"Rutina en preparación por tu entrenador"*, sin fallar ni bloquear la pantalla.

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

1. Dado un entrenador personal con solicitudes pendientes, cuando accede a su bandeja de solicitudes, entonces el sistema lista todas sus solicitudes en estado `PENDING` ordenadas desde la más reciente, mostrando nombre del alumno, paquete solicitado, tarifa mensual acordada y fecha de envío.

2. Dado un entrenador con solicitudes pendientes recibidas, cuando consulta su panel de inicio o refresca la bandeja, entonces el sistema refleja el número total de solicitudes pendientes sin atender.

3. Dado un alumno que envía una solicitud a un entrenador, cuando el entrenador abre o refresca su bandeja de solicitudes, entonces el contador de pendientes aumenta en 1 y la solicitud aparece listada.

4. Dado un entrenador que abre una solicitud pendiente específica, cuando accede al detalle, entonces puede ver los datos de contacto del alumno, sus objetivos deportivos, motivación personal, y consultar su cuestionario de salud y apto médico mediante autorización validada en el backend.

5. Dado un entrenador con el cupo completo (`active_students >= max_students`) que tiene solicitudes pendientes previas, cuando consulta su bandeja, entonces las solicitudes siguen visibles, pero el botón "Aceptar" se muestra deshabilitado indicando "Cupos agotados; libere un cupo para poder aceptar" y el botón "Rechazar" permanece habilitado.


---

### User Story 6 - [US-07: gestionar solicitudes de alumnos] (Priority: P1, Estimación: 5 SP)

Como entrenador personal,
 quiero poder aceptar o rechazar las solicitudes de alumnos,
 para seleccionar aquellos alumnos cuyos objetivos estén más alineados a mi forma de entrenar.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador en el detalle de una solicitud pendiente, cuando revisa las opciones de gestión, entonces dispone de las acciones para aceptar o rechazar la solicitud.

2. Dado un entrenador con cupo disponible que acepta una solicitud pendiente, cuando confirma la aceptación (con mensaje de bienvenida opcional), entonces el sistema cambia la solicitud a `ACCEPTED`, crea un vínculo de entrenamiento activo (`TrainingRelationship`), incrementa la cantidad de alumnos activos y remueve la solicitud de la bandeja de pendientes.

3. Dado un entrenador con cupos agotados (`active_students >= max_students`), cuando intenta forzar la aceptación de una solicitud pendiente vía API, entonces el sistema rechaza la operación con HTTP 409 Conflict y el mensaje "Cupos agotados; libere un cupo para poder aceptar.", manteniendo la solicitud en `PENDING` y el cupo inalterado.

4. Dado un entrenador que rechaza una solicitud pendiente, cuando confirma el rechazo (pudiendo indicar un motivo explicativo opcional), entonces el sistema actualiza la solicitud a `REJECTED`, registra la fecha de resolución y el motivo (si se ingresó), remueve la solicitud de la bandeja y mantiene el cupo inalterado.

5. Dado un entrenador que rechazó una solicitud, cuando intenta acceder posteriormente a los datos de salud o certificado médico del alumno, entonces el backend deniega el acceso con HTTP 403 Forbidden por no existir solicitud pendiente ni vínculo activo.

6. Dado que una solicitud ya fue resuelta previamente (`ACCEPTED`, `REJECTED` o `CANCELLED`), cuando se intenta aceptar o rechazar nuevamente, entonces el sistema rechaza la petición con HTTP 409 Conflict informando que la solicitud ya fue procesada.


---

### User Story 7 - [US-49: Confirmación y bienvenida al programa del entrenador] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero recibir una confirmación y un mensaje de bienvenida cuando un entrenador acepta mi solicitud, para saber que ya puedo comenzar a entrenar con él.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario y cerrar el ciclo de onboarding y contratación.

**Independent Test**: Puede verificarse aceptando una solicitud pendiente desde el rol de entrenador y comprobando que: (1) se crea la notificación de bienvenida para el alumno, (2) el alumno visualiza al entrenador y plan activo en su perfil, y (3) se habilita el acceso a la rutina si fue previamente asignada.

**Acceptance Scenarios**:

1. Dado un entrenador que acepta una solicitud pendiente, cuando confirma la aceptación (con o sin mensaje personalizado), entonces el sistema genera y entrega al alumno una notificación in-app de bienvenida y confirmación de alta en el programa.

2. Dado un alumno cuya solicitud fue aceptada, cuando consulta su perfil o panel principal (`GET /api/v1/students/me/active-plan`), entonces visualiza el entrenador asignado (nombre, foto, contacto), el plan contratado con la tarifa acordada inmutable y la fecha de inicio del servicio.

3. Dado un alumno recién aceptado cuyo entrenador ya cargó y publicó su primera rutina, cuando el alumno ingresa a su perfil o presiona la notificación de bienvenida, entonces obtiene acceso inmediato de lectura al detalle de dicha rutina.

4. Dado un alumno recién aceptado cuyo entrenador aún no ha cargado ninguna rutina, cuando consulta su plan activo, entonces el sistema le muestra el mensaje de bienvenida y el estado indicativo *"Tu entrenador está preparando tu primera rutina"*, sin arrojar errores.

5. Dado un alumno que navega a su centro de notificaciones, cuando visualiza la notificación de aceptación y hace clic en ella, entonces el sistema la marca como leída y lo redirige a la vista de su plan/rutina.


---

### Edge Cases

- ¿Qué ocurre si un alumno intenta enviar una solicitud a un entrenador que no tiene cupos disponibles? El sistema bloquea el envío e indica que el profesional no posee cupos libres.

- ¿Qué ocurre con las solicitudes pendientes cuando el cupo llega a 0? (Decisión Alternativa A): Las solicitudes pendientes recibidas previamente permanecen visibles en la bandeja del entrenador, pero el botón 'Aceptar' queda bloqueado e inhabilitado, mostrando la advertencia 'Cupos agotados; libere un cupo para poder aceptar'. El entrenador puede rechazarlas manualmente con motivo o mantenerlas a la espera de que se libere un cupo.

- ¿Qué sucede si el entrenador rechaza una solicitud o el alumno la cancela? (Revocación Inmediata de Datos de Salud): La solicitud cambia a estado 'REJECTED' o 'CANCELLED'. El permiso temporal de lectura del entrenador sobre el cuestionario de salud (US-41), molestias previas (US-42) y certificado médico (US-43) se revoca de inmediato en el backend. El entrenador conserva únicamente el registro de auditoría de la solicitud (nombre, fecha, motivo), sin acceso a los datos médicos del alumno.

- ¿Qué ocurre si un alumno intenta enviar una solicitud a un entrenador con el que ya tiene una solicitud pendiente o una suscripción activa? El sistema lo previene e informa el estado actual.

- ¿Qué ocurre si el alumno aplica filtros de búsqueda que no coinciden con ningún entrenador? El sistema muestra un mensaje indicando la ausencia de resultados y sugiere ampliar los criterios.

- ¿Qué ocurre si un alumno sin ningún vínculo de entrenamiento activo consulta su plan (`GET /api/v1/students/me/active-plan`)? El sistema responde con HTTP 200 y `has_active_plan: false`, permitiendo que el frontend renderice el estado vacío invitando a explorar entrenadores, sin incurrir en errores 404 o caídas de UI.

- ¿Qué ocurre si el entrenador acepta la solicitud sin redactar un mensaje personalizado? El sistema utiliza una plantilla por defecto: *"¡Bienvenido al programa! Tu entrenador {nombre_entrenador} ha confirmado tu solicitud para el plan {nombre_plan}. Ya pueden comenzar a entrenar."*, garantizando que el alumno siempre reciba la confirmación.

- ¿Qué ocurre si la rutina asociada es archivada o editada por el entrenador? El alumno siempre visualiza la versión vigente y activa asignada a su vínculo; si se desasigna o aún no existe, el plan activo muestra el estado indicativo "Rutina en preparación".



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al alumno buscar entrenadores aplicando filtros combinados por especialidad, precio y disponibilidad (US-44).

- **FR-002**: El sistema DEBE mostrar en los resultados del buscador un resumen del perfil de cada entrenador (foto, tarifas, especialidad y cupos) (US-44).

- **FR-003**: El sistema DEBE permitir al alumno consultar el perfil público completo del entrenador con certificaciones, metodología y tarifas (US-46).

- **FR-004**: El sistema DEBE permitir al alumno seleccionar un paquete de entrenamiento publicado (US-47).

- **FR-005**: El sistema DEBE permitir al alumno enviar una solicitud formal de entrenamiento adjuntando su perfil y objetivos (US-48).

- **FR-006**: El sistema DEBE listar al entrenador las solicitudes entrantes pendientes (`TrainingRequest` con estado `PENDING`) ordenadas por fecha descendente, exponiendo el resumen de la solicitud y otorgando permiso de lectura temporal exclusivo sobre la información básica, cuestionario de salud y apto médico del alumno mientras la solicitud esté en evaluación (US-06).

- **FR-007**: El sistema DEBE permitir al entrenador aceptar o rechazar solicitudes de alumnos (US-07). Si los cupos están agotados, la acción de aceptar se bloquea respondiendo HTTP 409 Conflict y deshabilitando el botón en la interfaz con la advertencia "Cupos agotados; libere un cupo para poder aceptar", manteniendo las solicitudes en bandeja para gestión manual y rechazo disponible (Decisión Alternativa A).

- **FR-007a**: El sistema DEBE permitir al entrenador indicar un motivo explicativo opcional al rechazar una solicitud (`POST /matchmaking/requests/{id}/reject`), actualizando el estado a `REJECTED` y conservando la fecha de resolución y el motivo (si existiera) sin alterar los cupos del entrenador (US-07, US-48).

- **FR-008**: Al aceptar una solicitud, el sistema DEBE crear un vínculo de entrenamiento activo (`TrainingRelationship`), descontar un cupo disponible (`active_students` +1), copiar la tarifa y moneda acordadas de forma inmutable, y emitir el mensaje de confirmación al alumno (US-07, US-49).

- **FR-009**: El sistema DEBE revocar de forma inmediata e irreversible el acceso del entrenador a los datos de salud del alumno (cuestionario, molestias, apto médico) en el backend si la solicitud es rechazada o cancelada, denegando accesos posteriores con HTTP 403 Forbidden (US-06, US-07, US-48, Constitución).

- **FR-010**: Al crear una solicitud, el sistema DEBE guardar en ella la tarifa mensual y la moneda vigentes del paquete seleccionado, y al aceptarla DEBE copiarlas al vínculo. Editar la tarifa o archivar el paquete después no modifica el arancel de solicitudes ya enviadas ni de vínculos existentes. Solo se pueden solicitar paquetes activos (US-47, US-48, US-07; spec 002 US-03).

- **FR-011**: Al confirmarse la aceptación de una solicitud (`POST /api/v1/matchmaking/requests/{id}/accept`), el sistema DEBE generar y persistir atómicamente una notificación interna (`Notification`) para el alumno con el título de confirmación, el mensaje de bienvenida provisto por el entrenador (o el mensaje estándar de bienvenida si no se especificó uno) y la vinculación a su nuevo plan (US-49).

- **FR-012**: El sistema DEBE proveer un endpoint protegido para el alumno autenticado (`GET /api/v1/students/me/active-plan`) que devuelva el vínculo de entrenamiento activo (`TrainingRelationship` con `status = 'ACTIVE'`), incluyendo los datos del entrenador asignado (nombre, foto, especialidad, contacto), el detalle del paquete y arancel acordado inmutable, y el enlace o indicador de su primera rutina (US-49).

- **FR-013**: El sistema DEBE proveer endpoints para que el alumno consulte sus notificaciones (`GET /api/v1/students/me/notifications`) y las marque como leídas (`PATCH /api/v1/students/me/notifications/{id}/read`) (US-49).

- **FR-014**: Si el alumno tiene una rutina asignada y publicada al ser aceptado, el sistema DEBE habilitar su acceso de lectura inmediato desde el resumen del plan activo; en caso de que aún no existan rutinas cargadas, el sistema DEBE indicar el estado "Rutina en preparación" sin producir errores en la consulta (US-49).



### Key Entities *(include if feature involves data)*

- **TrainerSearchFilter**: Criterios combinables de búsqueda: especialidad, rango de tarifa, disponibilidad horaria y modalidad.

- **TrainingRequest**: Solicitud de vinculación enviada por un alumno a un entrenador para un paquete específico, con estado (`PENDING`, `ACCEPTED`, `REJECTED`, `CANCELLED`), fecha de creación, fecha de resolución, mensaje del alumno, respuesta/motivo del entrenador y el arancel acordado (tarifa y moneda del paquete al momento de enviarla).

- **TrainingRelationship**: Vínculo activo de entrenamiento entre un alumno y un entrenador, con estado (`ACTIVE`, `TERMINATED`, `EXPIRED`), fecha de inicio, tarifa mensual y moneda acordadas inmutables heredadas de la solicitud.

- **OnboardingWelcome**: Mensaje de confirmación y bienvenida generado automáticamente al aceptar una solicitud, con instrucciones iniciales.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La actualización de resultados en el buscador ante cambios de filtros responde en menos de 1 segundo.

- **SC-002**: No es posible enviar solicitudes a entrenadores con cupos agotados bajo ninguna condición.

- **SC-003**: La aceptación de una solicitud vincula formalmente al alumno con el entrenador y habilita los flujos de planificación y seguimiento.



## Assumptions

- El alumno puede enviar solicitudes a diferentes entrenadores siempre que no tenga una relación activa incompatible.

- La vinculación inicial no requiere pago previo en la app; las cuotas se gestionan en el módulo de pagos informales.


