# Feature Specification: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature Branch**: `005-exercise-library-and-templates`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Gestión de la biblioteca de ejercicios del entrenador con instrucciones y notas técnicas, asociación de videos demostrativos mediante enlaces externos (YouTube, Vimeo, Drive) y creación de plantillas de rutinas genéricas reutilizables.

**User Stories Cubiertas**: US-08, US-09, US-12, US-52

## Clarifications

### Session 2026-10-30

- Q: ¿Cómo se estructura una rutina genérica? → A: Rutina → días → bloques → ejercicios, con series, repeticiones y descanso por ejercicio.
- Q: ¿Qué significa "tipo de ejercicio" en la creación de una rutina? → A: Es una categoría obligatoria del ejercicio, elegida de una lista cerrada: Fuerza, Cardio, Movilidad, Flexibilidad o Equilibrio. Se carga en la biblioteca (US-08) y la rutina la muestra por cada ejercicio.
- Q: ¿Para qué alumnos "queda disponible" una rutina? → A: Para los alumnos con vínculo de entrenamiento activo con el entrenador, en modo solo lectura; pierden el acceso al finalizar el vínculo.
- Q: ¿Cómo se determina que un ejercicio tiene alternativa "Sin materiales"? → A: Con una marca en el ejercicio que administra el entrenador. El contenido y el video de esa alternativa pertenecen a US-11, fuera del alcance de esta spec.
- Q: ¿La biblioteca incluye ejercicios precargados del sistema? → A: No. Cada entrenador ve y gestiona únicamente sus propios ejercicios.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-08: gestión de biblioteca de ejercicios genéricos] (Priority: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero poder gestionar mi biblioteca personal de ejercicios de entrenamiento genéricos,
 para tener un amplio abanico de posibilidades para las rutinas de mis alumnos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Un entrenador autenticado crea ejercicios, los lista, los filtra por músculo, consulta su detalle, los edita y los da de baja; otro entrenador no puede ver ni modificar esos ejercicios.

**Acceptance Scenarios**:

1. Dado que el entrenador completa nombre, descripción, categoría, músculo a trabajar y elementos necesarios, cuando guarda el ejercicio, entonces el ejercicio queda registrado en su biblioteca.

2. Dado que el entrenador omite alguno de esos 5 datos, cuando intenta guardar el ejercicio, entonces el sistema bloquea la creación e indica qué datos faltan.

3. Dado que el entrenador ingresa a la biblioteca de ejercicios, cuando elige un músculo en el filtro, entonces el sistema lista sus ejercicios creados limitados a ese músculo; sin filtro lista todos.

4. Dado un ejercicio de la biblioteca, cuando el entrenador lo abre, entonces el sistema muestra su descripción, categoría, músculo entrenado, elementos necesarios y si tiene alternativa "Sin materiales".

5. Dado un ejercicio de la biblioteca, cuando el entrenador edita sus datos y guarda, entonces el sistema muestra los datos actualizados.

6. Dado un ejercicio de la biblioteca, cuando el entrenador lo elimina y confirma la acción, entonces el ejercicio deja de aparecer en su biblioteca.

7. Dado un ejercicio de otro entrenador, cuando el entrenador intenta consultarlo, editarlo o eliminarlo, entonces el sistema responde que el ejercicio no existe.


---

### User Story 2 - [US-09: gestión de rutinas genéricas] (Priority: P2, Estimación: 5 SP)

Como entrenador personal,
 quiero poder crear rutinas de entrenamiento genéricas usando mi biblioteca de ejercicios,
 para tener entrenamientos disponibles predeterminados para mis clientes.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Un entrenador con ejercicios en su biblioteca crea una rutina con días y bloques, la edita y la consulta; un alumno con vínculo activo la ve en solo lectura y un alumno sin vínculo no accede.

**Acceptance Scenarios**:

1. Dado que el entrenador ingresa nombre de la rutina, duración en semanas, intensidad (baja, media, alta, exigente) y al menos un día con un bloque y un ejercicio de su biblioteca, con cantidad de series, repeticiones y descanso por ejercicio, cuando guarda, entonces el sistema crea la rutina, informa la cantidad de ejercicios y el tipo de cada uno, y la deja disponible para el entrenador y sus alumnos con vínculo activo.

2. Dado que el entrenador entra a la biblioteca de rutinas, cuando edita los parámetros de una rutina y guarda, entonces el sistema muestra la rutina actualizada.

3. Dado que el entrenador no ingresa alguno de los parámetros indicados, cuando intenta guardar, entonces el sistema no permite crear la rutina hasta que cargue esa información.

4. Dado que el entrenador marca una rutina como apta "Sin materiales", cuando alguno de sus ejercicios no tiene alternativa "Sin materiales", entonces el sistema no permite guardarla e indica los ejercicios que la incumplen.

5. Dado un ejercicio incluido en una rutina apta "Sin materiales", cuando el entrenador intenta quitarle la marca de alternativa "Sin materiales", entonces el sistema rechaza el cambio e informa el conflicto.

6. Dado un alumno con vínculo activo con el entrenador, cuando consulta sus rutinas, entonces ve en solo lectura las rutinas del entrenador con sus días, bloques, ejercicios y parámetros.

7. Dado un alumno sin vínculo activo con el entrenador, cuando intenta consultar una rutina de ese entrenador, entonces el sistema responde que la rutina no existe.


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

- ¿Qué ocurre si se edita una rutina que conserva un ejercicio dado de baja? El sistema permite mantenerlo en esa rutina, pero rechaza agregarlo a otra o agregarlo de nuevo.

- ¿Qué ocurre si un alumno con vínculo activo consulta a un entrenador sin rutinas? El sistema muestra un estado vacío sin errores de interfaz.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al entrenador crear, editar, categorizar, listar, filtrar por músculo y dar de baja ejercicios en su biblioteca personal (US-08).

- **FR-002**: El sistema DEBE permitir al entrenador crear, editar y consultar rutinas genéricas (templates) organizadas por días, bloques y ejercicios, con series, repeticiones y descanso por ejercicio (US-09).

- **FR-003**: El sistema DEBE permitir vincular un enlace de video demostrativo de YouTube, Vimeo o Google Drive a cada ejercicio (US-12).

- **FR-004**: El sistema DEBE validar la sintaxis y el dominio del enlace de video antes de guardarlo (US-12).

- **FR-005**: El sistema DEBE permitir al alumno leer las notas técnicas y las claves de respiración cargadas para cada ejercicio (US-52).

- **FR-006**: El sistema NO DEBE permitir la carga de archivos binarios de video al servidor propio (Constitución).

- **FR-007**: El sistema DEBE exigir que todos los ejercicios de una rutina apta "Sin materiales" tengan la marca de alternativa "Sin materiales", tanto al guardar la rutina como al editar el ejercicio (US-09).

- **FR-008**: El sistema DEBE validar en el servidor que cada entrenador acceda solo a sus ejercicios y rutinas, y que cada alumno acceda solo a las rutinas de entrenadores con quienes tiene un vínculo activo (US-08, US-09).



### Key Entities *(include if feature involves data)*

- **Exercise**: Definición de ejercicio perteneciente a un entrenador: nombre, descripción, categoría, grupo muscular principal, equipamiento requerido, marca de alternativa "Sin materiales", instrucciones de ejecución y notas de respiración.

- **ExerciseMediaLink**: Enlace validado a video externo demostrativo en plataforma soportada (YouTube, Vimeo, Google Drive).

- **RoutineTemplate**: Plantilla de rutina genérica reutilizable con nombre, duración, intensidad y aptitud "Sin materiales", compuesta por días.

- **RoutineTemplateDay**: Día nombrado y ordenado de una rutina, compuesto por bloques.

- **RoutineTemplateBlock**: Bloque nombrado y ordenado de un día, compuesto por ejercicios.

- **RoutineTemplateExercise**: Ejercicio de la biblioteca dentro de un bloque, con series, repeticiones y descanso.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los videos vinculados corresponden a URLs validadas de plataformas soportadas.

- **SC-002**: Las notas técnicas y claves de respiración están accesibles para el alumno con un solo toque desde la vista de rutina.

- **SC-003**: Las plantillas genéricas pueden clonarse y asignarse a alumnos particulares sin alterar la plantilla original. La clonación y la asignación se verifican con la spec 006.

- **SC-004**: El 100% de las rutinas aptas "Sin materiales" guardadas contienen solo ejercicios con esa marca.



## Assumptions

- Los videos alojados en plataformas externas son de acceso público o configurados como 'no listados' para permitir su reproducción embebida.

- El entrenador es el creador y curador de su biblioteca de ejercicios.

- La eliminación de rutinas no forma parte de los criterios de aceptación de US-09 y queda fuera de alcance.

- La marca de alternativa "Sin materiales" es declarativa hasta que US-11 incorpore el contenido y el video de la alternativa.
