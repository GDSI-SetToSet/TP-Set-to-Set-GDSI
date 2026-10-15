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

1. Al cargar los datos, quedan visibles para cualquier usuario que entre a ver el perfil del entrenador

2. Si no se cargan los datos de contacto y especialidad, el sistema no permite seguir con el uso normal de la aplicación hasta que no se carguen.

3. Al editar los datos del perfil y guardar los cambios, la aplicación debe mostrar los datos actualizados y no los viejos.

4. Si al editar los datos queda en blanco algún dato obligatorio (contacto o especialidad), entonces el sistema no permite seguir con el uso normal de la aplicación hasta que se vuelvan a cargar.


---

### User Story 2 - [US-03: Publicar y editar paquetes y tarifas] (Priority: P1, Estimación: 4 SP)

Como entrenador,
 quiero publicar mis paquetes de entrenamiento mensuales junto con sus tarifas,
 para que los alumnos puedan conocer la información de mis entrenamientos de antemano.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Al publicar el paquete, ésta queda visible para todos los usuarios de la aplicación que quieran verla.

2. Si al publicar la tarifa no se indica moneda, entonces el sistema debe elegir pesos argentinos por defecto.

3. Si un entrenador elige una tarifa fuera del rango permitido (0 a 1.000.000), entonces el sistema no permite cargar la tarifa y el entrenador debe intentar de vuelta

4. Si un entrenador no indica el valor de la tarifa del paquete, entonces el sistema no permite crear el paquete hasta que el entrenador indique el valor mensual


---

### User Story 3 - [US-04: gestión de cupos disponibles] (Priority: P1, Estimación: 4 SP)

Como entrenador,
 quiero registrar el tope de cupos por mes de alumnos que puedo tomar,
 para establecer un límite de clientes y poder brindar la mejor atención personalizada a cada uno de ellos

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Al publicar los cupos disponibles, éstos quedan visibles para la consulta de cualquier usuario de la aplicación.

2. Si no se indican cupos disponibles, entonces el sistema asigna el valor de cupos a 0 por defecto.

3. Si un entrenador ingresa un número de cupos fuera del rango permitido (0 a 100), entonces el sisema no permite cargar los cupos y el entrenador debe intentar de vuelta.

4. Al alcanzar el tope de alumnos, el sistema bloquea automáticamente nuevas solicitudes y marca el perfil como 'Sin cupos disponibles'.

5. Si un alumno cancela o finaliza su membresía, se libera un cupo automáticamente y se reanudan las contrataciones.


---

### Edge Cases

- ¿Qué ocurre si el entrenador alcanza el tope de cupos configurado? El sistema deshabilita automáticamente la posibilidad de que nuevos alumnos envíen solicitudes y muestra la etiqueta 'Sin cupos disponibles'.

- ¿Qué ocurre con las solicitudes pendientes si el cupo se agota? (Decisión Alternativa A): Las solicitudes pendientes recibidas previamente permanecen en la bandeja del entrenador, pero el botón 'Aceptar' queda bloqueado e inhabilitado con la advertencia 'Cupos agotados; libere un cupo para poder aceptar'. El entrenador puede rechazarlas manualmente con motivo o esperar a liberar un cupo.

- ¿Qué ocurre si el entrenador intenta publicar un paquete sin definir tarifa o sin título? El sistema bloquea la publicación e indica los campos requeridos faltantes.

- ¿Qué ocurre si el entrenador reduce el cupo máximo por debajo de la cantidad de alumnos activos actuales? El sistema permite la configuración advirtiendo que no se aceptarán nuevas solicitudes hasta que el cupo ocupado descienda por debajo del nuevo límite.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al entrenador cargar y editar su biografía, especialidades, certificaciones y datos de contacto (US-02).

- **FR-002**: El sistema DEBE requerir obligatoriamente datos de contacto y especialidad antes de permitir hacer público el perfil (US-02).

- **FR-003**: El sistema DEBE permitir al entrenador crear, editar y archivar paquetes de entrenamiento mensuales indicando título, descripción y tarifa (US-03).

- **FR-004**: El sistema DEBE permitir configurar un tope máximo de cupos de alumnos para el entrenador (US-04).

- **FR-005**: El sistema DEBE pausar automáticamente la recepción de solicitudes públicas al alcanzar el tope de cupos disponible (US-04).

- **FR-006**: Si los cupos están agotados, el sistema DEBE bloquear la aceptación de solicitudes pendientes en bandeja, manteniéndolas disponibles para rechazo manual o aceptación diferida tras liberar cupo (US-04, US-07, Decisión Alternativa A).

- **FR-007**: El sistema DEBE reflejar en tiempo real la disponibilidad de cupos en el perfil público del entrenador (US-04).



### Key Entities *(include if feature involves data)*

- **TrainerProfile**: Información pública y profesional del entrenador: datos de contacto, biografía, especialidad principal, certificaciones, fotos y disponibilidad horaria.

- **TrainingPackage**: Paquete o plan de servicio ofrecido por el entrenador, con título, descripción, servicios incluidos y tarifa mensual en moneda local.

- **TrainerQuota**: Configuración de capacidad del entrenador que define cupos totales, cupos ocupados y bandera automática de disponibilidad.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La actualización de tarifas y paquetes se refleja de forma inmediata en el catálogo público sin inconsistencias.

- **SC-002**: El bloqueo de solicitudes al agotarse los cupos ocurre de forma automática y estricta en el 100% de los casos.

- **SC-003**: El perfil del entrenador valida la completitud de campos requeridos antes de pasar a estado publicado.



## Assumptions

- Las tarifas publicadas son informativas de cobro mensual en moneda local y se abonan fuera de la plataforma.

- El entrenador es responsable de mantener actualizadas sus certificaciones y biografía.


