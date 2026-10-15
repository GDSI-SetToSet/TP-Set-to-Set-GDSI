# Feature Specification: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature Branch**: `005-exercise-library-and-templates`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Gestión de la biblioteca de ejercicios del entrenador con instrucciones y notas técnicas, asociación de videos demostrativos mediante enlaces externos (YouTube, Vimeo, Drive) y creación de plantillas de rutinas genéricas reutilizables.

**User Stories Cubiertas**: US-08, US-09, US-12, US-52

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-08: gestión de biblioteca de ejercicios genéricos] (Priority: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero poder gestionar mi biblioteca personal de ejercicios de entrenamiento genéricos,
 para tener un amplio abanico de posibilidades para las rutinas de mis alumnos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Al crear un ejercicio, se debe ingresar nombre del ejercicio, breve descripción, músculo a trabajar y elementos necesarios.

2. Si no se ingresa cualquiera de los 4 datos, el sistema bloquea la creación hasta que se ingresen.

3. Al ingresar a la biblioteca de ejercicios, se debe poder listar todos los ejercicios creados y filtrar por músculo en específico.

4. Al ver un ejercicio en particular, el sistema debe mostrar su descripción, músculo entrenado y elementos necesarios


---

### User Story 2 - [US-09: gestión de rutinas genéricas] (Priority: P2, Estimación: 5 SP)

Como entrenador personal,
 quiero poder crear rutinas de entrenamiento genéricas usando mi biblioteca de ejercicios,
 para tener entrenamientos disponibles predeterminados para mis clientes.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado que el entrenador ingresa nombre de la rutina, duración de la rutina, intensidad (baja, media, alta, exigente), cantidad de ejercicios, tipo de ejercicio, cantidad de series y repeticiones por ejercicio, entonces el sistema crea la nueva rutina y queda disponible tanto para alumnos como para entrenador.

2. Dado que el entrenador entra a la biblioteca de rutinas, entonces debe poder editar los parámetros de la rutina.

3. Dado que el entrenador no ingresa alguno de los parámetros indicados para crear una rutina, entonces el sistema no permite crear la nueva rutina hasta que el entrenador no cargue esa información.

4. Si una rutina puede ser realizada fuera del gimnasio y tiene su alternativa "Sin materiales", entonces todos sus ejercicios deben tener alternativa "Sin materiales".


---

### User Story 3 - [US-12: Vincular video demostrativo a un ejercicio] (Priority: P1, Estimación: 2 SP)

Como entrenador personal,
 quiero vincular un video demostrativo a cada ejercicio de mi biblioteca,
 para que mis alumnos vean cómo se ejecuta correctamente sin que yo tenga que explicarlo cada vez.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un ejercicio de la biblioteca (US-08), cuando el entrenador pega un link de video de una plataforma soportada (YouTube, Vimeo o Google Drive), entonces el video queda asociado y se puede previsualizar en el detalle del ejercicio.

2. Dado un link inválido o de una plataforma no soportada, cuando el entrenador intenta guardarlo, entonces el sistema no lo guarda y le informa el motivo.

3. Dado un ejercicio con video, cuando el entrenador lo reemplaza o lo elimina, entonces el alumno ve la versión actualizada o deja de ver el video.

4. Dado un ejercicio con variante segura (US-53), cuando el entrenador la configura, entonces puede vincularle su propio video.


---

### User Story 4 - [US-52: Lectura de notas técnicas y claves de respiración del ejercicio] (Priority: P2, Estimación: 2 SP)

Como alumno, quiero leer las notas técnicas y las claves de respiración que el entrenador cargó para un ejercicio, para ejecutarlo con la postura y el ritmo correctos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un ejercicio con notas técnicas o claves de respiración cargadas por el entrenador, cuando el alumno lo consulta, entonces el sistema las muestra junto al video o la descripción del ejercicio.

2. Dado un ejercicio sin notas técnicas cargadas, cuando el alumno lo consulta, entonces el sistema no muestra esa sección en lugar de dejarla vacía.


---

### Edge Cases

- ¿Qué ocurre si el entrenador intenta guardar un enlace de video de una plataforma no soportada o con formato inválido? El sistema rechaza el guardado e informa las plataformas permitidas (YouTube, Vimeo, Drive).

- ¿Qué ocurre si un ejercicio no tiene video vinculado? El alumno visualiza la ficha técnica completa con grupo muscular, notas de respiración y postura sin errores de interfaz.

- ¿Qué ocurre si se elimina un ejercicio que forma parte de plantillas o rutinas en curso? El sistema realiza una baja lógica (soft delete) impidiendo nuevas selecciones pero preservando el histórico en rutinas existentes.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al entrenador crear, editar y categorizar ejercicios en su biblioteca personal (US-08).

- **FR-002**: El sistema DEBE permitir al entrenador estructurar rutinas genéricas (templates) organizadas por días, bloques, series y descansos (US-09).

- **FR-003**: El sistema DEBE permitir vincular un enlace de video demostrativo de YouTube, Vimeo o Google Drive a cada ejercicio (US-12).

- **FR-004**: El sistema DEBE validar la sintaxis y el dominio del enlace de video antes de guardarlo (US-12).

- **FR-005**: El sistema DEBE permitir al alumno leer las notas técnicas y las claves de respiración cargadas para cada ejercicio (US-52).

- **FR-006**: El sistema NO DEBE permitir la carga de archivos binarios de video al servidor propio (Constitución).



### Key Entities *(include if feature involves data)*

- **Exercise**: Definición de ejercicio: nombre, grupo muscular principal, equipamiento requerido, instrucciones de ejecución y notas de respiración.

- **ExerciseMediaLink**: Enlace validado a video externo demostrativo en plataforma soportada (YouTube, Vimeo, Google Drive).

- **RoutineTemplate**: Plantilla de rutina genérica reutilizable compuesta por días, bloques de ejercicios, series, repeticiones sugeridas y descansos.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los videos vinculados corresponden a URLs validadas de plataformas soportadas.

- **SC-002**: Las notas técnicas y claves de respiración están accesibles para el alumno con un solo toque desde la vista de rutina.

- **SC-003**: Las plantillas genéricas pueden clonarse y asignarse a alumnos particulares sin alterar la plantilla original.



## Assumptions

- Los videos alojados en plataformas externas son de acceso público o configurados como 'no listados' para permitir su reproducción embebida.

- El entrenador es el creador y curador de su biblioteca de ejercicios.


