# Feature Specification: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Feature Branch**: `002-trainer-profile-and-plans`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Permite al entrenador configurar su perfil profesional visible, publicar planes o paquetes de entrenamiento con tarifas mensuales y administrar su capacidad operativa mediante cupos máximos.

**User Stories Cubiertas**: US-02, US-03, US-04

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-02: Carga y edición de datos de perfil del entrenador] (Priority: P1, Estimación: 4 SP)

Como entrenador con cuenta registrada,
 quiero cargar mis datos de contacto, biografía, certificaciones y especialidad,
 para que los alumnos puedan ver mi forma de entrenar y conectar con los que tengan objetivos similares a los míos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

**Acceptance Scenarios**:

1. Dado un entrenador con perfil completo (contacto y especialidad cargados), cuando el perfil queda guardado, entonces el perfil pasa a estado PUBLISHED y es visible para cualquier usuario que consulte al entrenador.

2. Dado un entrenador recién registrado sin contacto ni especialidad cargados, cuando consulta su propio perfil, entonces el perfil permanece en estado DRAFT, no aparece en las búsquedas ni en el perfil público, y el sistema muestra un aviso con los campos obligatorios pendientes (contacto y especialidad). El resto de la aplicación sigue disponible.

3. Dado un entrenador con perfil PUBLISHED, cuando edita datos del perfil y guarda, entonces el sistema persiste los cambios y el perfil público y la vista de edición muestran de inmediato los valores guardados.

4. Dado un entrenador que edita su perfil, cuando deja vacío el contacto o la especialidad y presiona "Guardar", entonces el sistema no guarda los cambios, resalta el campo vacío en rojo con el mensaje "Este campo es obligatorio" y el perfil conserva los últimos valores válidos y su estado.

5. Dado un entrenador que ingresa un teléfono/WhatsApp con caracteres no numéricos o con menos de 8 o más de 15 dígitos, cuando presiona "Guardar", entonces el sistema no guarda los cambios y resalta el campo con el mensaje "Ingresá un teléfono válido de 8 a 15 dígitos (puede iniciar con +)".


---

### User Story 2 - [US-03: Publicar y editar paquetes y tarifas] (Priority: P1, Estimación: 4 SP)

Como entrenador,
 quiero publicar mis paquetes de entrenamiento mensuales junto con sus tarifas,
 para que los alumnos puedan conocer la información de mis entrenamientos de antemano.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con perfil PUBLISHED, cuando publica un paquete con título y tarifa válidos, entonces el paquete queda visible en su perfil público para cualquier usuario.

2. Dado un entrenador que completa el título y una tarifa válida sin indicar moneda, cuando publica el paquete, entonces el sistema guarda el paquete con moneda ARS (pesos argentinos).

3. Dado un entrenador que ingresa una tarifa menor a 0 o mayor a 1.000.000, cuando presiona "Guardar", entonces el sistema resalta el campo en rojo con el mensaje "La tarifa debe estar entre $0 y $1.000.000", deshabilita el botón "Guardar" y no persiste el paquete.

4. Dado un entrenador que deja vacíos el título o la tarifa, cuando intenta publicar el paquete, entonces el sistema no crea el paquete y resalta cada campo faltante con el mensaje "Este campo es obligatorio".

5. Dado un paquete publicado con alumnos con vínculo activo, cuando el entrenador edita su tarifa o lo archiva, entonces el cambio aplica solo a solicitudes futuras y el arancel acordado de los vínculos activos no se modifica.


---

### User Story 3 - [US-04: gestión de cupos disponibles] (Priority: P1, Estimación: 4 SP)

Como entrenador,
 quiero registrar el tope de cupos por mes de alumnos que puedo tomar,
 para establecer un límite de clientes y poder brindar la mejor atención personalizada a cada uno de ellos

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con cupos configurados, cuando guarda el tope de cupos, entonces la cantidad de cupos disponibles queda visible en su perfil público para cualquier usuario.

2. Dado un entrenador que no indica el tope de cupos, cuando guarda su configuración, entonces el sistema asigna 0 cupos y marca el perfil como "Sin cupos disponibles".

3. Dado un entrenador que ingresa un tope menor a 0 o mayor a 100, cuando presiona "Guardar", entonces el sistema resalta el campo en rojo con el mensaje "Los cupos deben estar entre 0 y 100", deshabilita el botón "Guardar" y no modifica el tope vigente.

4. Dado un entrenador cuyos alumnos activos igualan el tope de cupos, cuando un alumno intenta enviar una solicitud, entonces el sistema la rechaza, deshabilita el botón de solicitud y el perfil muestra la etiqueta "Sin cupos disponibles".

5. Dado un entrenador sin cupos disponibles, cuando un alumno cancela o finaliza su membresía, entonces el sistema libera un cupo automáticamente, quita la etiqueta "Sin cupos disponibles" y vuelve a habilitar el envío de solicitudes.


---

### Edge Cases

- ¿Qué ocurre si el entrenador alcanza el tope de cupos configurado? El sistema deshabilita automáticamente la posibilidad de que nuevos alumnos envíen solicitudes y muestra la etiqueta 'Sin cupos disponibles'.

- ¿Qué ocurre con las solicitudes pendientes si el cupo se agota? (Decisión Alternativa A): Las solicitudes pendientes recibidas previamente permanecen en la bandeja del entrenador, pero el botón 'Aceptar' queda bloqueado e inhabilitado con la advertencia 'Cupos agotados; libere un cupo para poder aceptar'. El entrenador puede rechazarlas manualmente con motivo o esperar a liberar un cupo.

- ¿Qué ocurre si el entrenador intenta publicar un paquete sin definir tarifa o sin título? El sistema bloquea la publicación y resalta cada campo requerido faltante con el mensaje "Este campo es obligatorio".

- ¿Qué ocurre si se edita la tarifa de un paquete o se lo archiva mientras hay alumnos con vínculo activo? El cambio aplica solo a futuras solicitudes; el arancel acordado de los vínculos activos no cambia (no retroactividad).

- ¿Qué ocurre con un perfil sin contacto o sin especialidad? Permanece en estado DRAFT: no es visible en búsquedas ni como perfil público hasta completar ambos campos; no hay modal bloqueante.

- ¿Qué ocurre si el entrenador reduce el cupo máximo por debajo de la cantidad de alumnos activos actuales? El sistema permite la configuración advirtiendo que no se aceptarán nuevas solicitudes hasta que el cupo ocupado descienda por debajo del nuevo límite.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al entrenador cargar y editar su biografía, especialidades, certificaciones y datos de contacto (US-02).

- **FR-002**: El sistema DEBE mantener el perfil en estado DRAFT (no visible en búsquedas ni como perfil público) hasta que estén cargados el contacto y la especialidad, y pasarlo a PUBLISHED al completarlos. El contacto debe cumplir el formato de teléfono/WhatsApp definido en la Constitución (US-02).

- **FR-003**: El sistema DEBE permitir al entrenador crear, editar y archivar paquetes de entrenamiento mensuales indicando título, descripción y tarifa (US-03). La edición de la tarifa o el archivado de un paquete aplica solo a solicitudes futuras y no modifica el arancel acordado de alumnos con vínculos activos.

- **FR-004**: El sistema DEBE permitir configurar un tope máximo de cupos de alumnos para el entrenador (US-04).

- **FR-005**: El sistema DEBE pausar automáticamente la recepción de solicitudes públicas al alcanzar el tope de cupos disponible (US-04).

- **FR-006**: Si los cupos están agotados, el sistema DEBE bloquear la aceptación de solicitudes pendientes en bandeja, manteniéndolas disponibles para rechazo manual o aceptación diferida tras liberar cupo (US-04, US-07, Decisión Alternativa A).

- **FR-007**: El sistema DEBE reflejar en tiempo real la disponibilidad de cupos en el perfil público del entrenador (US-04).



### Key Entities *(include if feature involves data)*

- **TrainerProfile**: Información pública y profesional del entrenador: datos de contacto, biografía, especialidad principal, certificaciones, fotos y disponibilidad horaria, y un estado de publicación (DRAFT mientras falten contacto o especialidad; PUBLISHED al completarlos).

- **TrainingPackage**: Paquete o plan de servicio ofrecido por el entrenador, con título, descripción, servicios incluidos y tarifa mensual en moneda local (ARS por defecto).

- **TrainerQuota**: Configuración de capacidad del entrenador que define cupos totales, cupos ocupados y bandera automática de disponibilidad.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La actualización de tarifas y paquetes se refleja de forma inmediata en el catálogo público sin inconsistencias.

- **SC-002**: El bloqueo de solicitudes al agotarse los cupos ocurre de forma automática y estricta en el 100% de los casos.

- **SC-003**: Ningún perfil sin contacto y especialidad válidos aparece en búsquedas ni como perfil público (permanece en DRAFT).



## Assumptions

- Las tarifas publicadas son informativas de cobro mensual en moneda local y se abonan fuera de la plataforma.

- El entrenador es responsable de mantener actualizadas sus certificaciones y biografía.


