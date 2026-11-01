# Feature Specification: Planificación con IA Supervisada, Variantes Seguras y Adaptaciones

**Feature Branch**: `006-routine-planning-and-adaptation`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Generación de borradores de rutinas particulares asistida por IA con revisión humana obligatoria, adaptación a restricciones articulares mediante variantes seguras, solicitudes de reemplazo inmediato de máquinas y alternancia entre versiones gimnasio y casa.

**User Stories Cubiertas**: US-13, US-14, US-53, US-54, US-55

## Clarifications

### Session 2026-11-01

- Q: Cuando el entrenador edita una rutina ya activa y asignada, ¿los cambios se aplican de inmediato o quedan en borrador hasta confirmarlos? → A: Quedan en borrador y el entrenador los confirma para publicarlos; el alumno sigue viendo la versión vigente hasta entonces.
- Q: Si el entrenador intenta agregar un ejercicio que choca con una limitación física del alumno, ¿puede forzar la edición? → A: No; el bloqueo es absoluto y solo se ofrece la variante segura.
- Q: ¿La alternativa "Sin materiales" se exige en cada guardado de borrador o al confirmar? → A: Solo al confirmar y publicar la rutina.
- Q: ¿Qué se considera ejercicio editado para exigir la alternativa "Sin materiales"? → A: Los ejercicios agregados o reemplazados respecto de la versión vigente.
- Q: ¿Se conserva historial de versiones restaurable o solo un registro de cambios? → A: Solo la versión actual más un registro de cambios (autor, fecha, qué cambió); sin restauración.
- Q: ¿Cómo informa el alumno su volumen semanal deseado? → A: Se lo comunica al entrenador, que lo registra.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-13: generar rutina particular con IA] (Priority: P2, Estimación: 5 SP)

Como entrenador personal,
 quiero crear una rutina específica para un alumno en particular usando IA,
 para adaptar el entrenamiento a los objetivos y limitaciones de cada alumno en particular.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno con objetivos y limitaciones de entrenamiento, y una rutina genérica de la biblioteca de rutinas, cuando el entrenador quiere crear una rutina particular para ese alumno, entonces el sistema edita la rutina con inteligencia artificial, modificando el tipo, cantidad o intensidad de los ejercicios, adaptandola a las necesidades del alumno.

2. Dado que un ejercicio de la rutina genérica no aplica a los objetivos y limitaciones del alumno, cuando se crea la rutina, entonces el sistema debe editar o eliminar el ejercicio para cumplir con las restricciones del alumno.


---

### User Story 2 - [US-14: editar rutina según objetivos y limitaciones del alumno] (Priority: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero poder editar las rutinas de un alumno (sea genérica o generada por IA),
 para adaptar uno o más ejercicios para respetar los objetivos y limitaciones (físicas o temporales) del alumno.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dada una rutina creada por el entrenador (genérica o IA), cuando el alumno pide un cambio o el entrenador considera necesario modificar parte de la rutina, entonces el sistema debe permitir modificar uno o más ejercicios, intensidad, duración o cualquier parámetro de la rutina.

2. Dado que la rutina está disponible "Sin materiales", cuando el entrenador intenta confirmar una edición que agrega o reemplaza un ejercicio sin alternativa "Sin materiales", entonces el sistema no permite confirmar y muestra una alerta al entrenador; el borrador puede guardarse incompleto.

3. Dado que el alumno tiene limitaciones físicas establecidas en su perfil, cuando el entrenador intenta introducir un ejercicio que va en contra de dichas limitaciones, entonces el sistema no debe permitir modificar el ejercicio (sin opción de forzarlo), debe mostrar una alerta al entrenador y ofrecer la variante segura si está configurada (US-53).

4. Dada una rutina creada por el entrenador, cuando el alumno indica un volumen semanal de entrenamiento deseado, entonces el sistema debe poder permitir editar la intensidad de la rutina para adaptarse a la carga indicada por el alumno.

5. Dada una rutina activa asignada al alumno, cuando el entrenador la edita, entonces los cambios quedan en borrador y el alumno sigue viendo la versión vigente hasta que el entrenador los confirme.


---

### User Story 3 - [US-53: Variantes seguras para restricciones articulares o físicas] (Priority: P1, Estimación: 4 SP)

Como alumno con restricciones físicas o articulares, quiero ver variantes seguras de un ejercicio, para entrenar sin agravar mi lesión o condición.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno con restricciones físicas cargadas en su perfil, cuando consulta un ejercicio de riesgo para esa zona, entonces el sistema le muestra la variante segura configurada por el entrenador.

2. Dado un ejercicio sin variante segura cargada para una restricción del alumno, cuando el alumno lo consulta, entonces el sistema notifica al entrenador para que revise el caso.

3. Dado un alumno consultando una variante segura, cuando la visualiza, entonces el sistema muestra su video o explicación asociada


---

### User Story 4 - [US-54: Solicitud de alternativa o reemplazo de ejercicio] (Priority: P2, Estimación: 3 SP)

Como alumno, quiero solicitar una alternativa para un ejercicio específico de mi rutina, para continuar entrenando el mismo grupo muscular si una máquina o elemento está ocupado o no disponible.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno viendo su rutina, cuando presiona el botón de sustituir un ejercicio, entonces el sistema le muestra las alternativas cargadas.

2. Dado un alumno solicitando una alternativa, cuando el sistema muestra sugerencias, entonces únicamente propone ejercicios que trabajen el mismo grupo muscular.

3. Dado un ejercicio sin alternativas cargadas por el entrenador, cuando el alumno solicita un reemplazo, entonces puede saltear el ejercicio y el pedido queda registrado en la sesión para que el entrenador cargue una alternativa al revisarla (US-26).


---

### User Story 5 - [US-55: Alternancia de rutina entre gimnasio y casa] (Priority: P2, Estimación: 3 SP)

Como alumno, quiero alternar la modalidad de mi rutina entre versión de gimnasio y versión de casa o viaje, para no interrumpir mi plan cuando no dispongo de las máquinas habituales.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno en la pantalla principal de su rutina, cuando utiliza el selector rápido, entonces puede alternar entre ""Gimnasio"" y ""Casa/Viaje"".

2. Dado un ejercicio sin alternativa ""Sin materiales"" cargada, cuando el alumno intenta seleccionar la versión de casa, entonces el sistema no se lo permite y le avisa.

3. Dado un alumno que registra series y cargas en cualquiera de las dos modalidades, cuando consulta su historial, entonces los registros se consolidan en el mismo historial general.


---

### Edge Cases

- ¿Puede una rutina generada por IA publicarse directamente al alumno sin intervención del entrenador? NO. Por principio constitucional (Human-in-the-Loop), la rutina permanece en borrador y requiere revisión, ajuste y aprobación manual obligatoria.

- ¿Qué ocurre si un ejercicio sugerido coincide con una zona a proteger declarada por el alumno? El sistema DEBE alertar al entrenador y presentar la variante segura correspondiente.

- ¿Qué ocurre si el alumno está en el gimnasio y una máquina está ocupada? El alumno puede solicitar un reemplazo directo y el sistema le ofrece una alternativa para el mismo grupo muscular y patrón de movimiento.

- ¿Cómo se maneja el cambio de entrenamiento de gimnasio a casa? El alumno activa la modalidad casa/viaje y la rutina adapta los ejercicios a peso corporal o mancuernas sin reiniciar la semana.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir generar un borrador de rutina asistido por IA considerando perfil, cuestionario de salud y objetivos del alumno (US-13).

- **FR-002**: El sistema DEBE exigir la revisión y aprobación manual del entrenador antes de activar cualquier rutina generada por IA (US-13, Constitución).

- **FR-003**: El sistema DEBE permitir al entrenador editar ejercicios, series, repeticiones y cargas de la rutina personalizada, manteniendo los cambios en borrador hasta que el entrenador los confirme; el alumno ve la versión vigente hasta entonces (US-14).

- **FR-003b**: El sistema DEBE bloquear de forma absoluta (sin posibilidad de forzar) la introducción de ejercicios contrarios a las limitaciones físicas del alumno, ofreciendo la variante segura si está configurada (US-14).

- **FR-003c**: El sistema DEBE exigir la alternativa "Sin materiales" de cada ejercicio agregado o reemplazado respecto de la versión vigente en una rutina disponible como "Sin materiales", al confirmar la edición y no en cada guardado de borrador; los ejercicios que solo cambian series, repeticiones, carga o intensidad no requieren nueva alternativa (US-14).

- **FR-003d**: El sistema DEBE registrar cada edición confirmada de una rutina (autor, fecha y qué cambió) conservando solo la versión actual, sin función de restaurar versiones anteriores (US-14).

- **FR-003e**: El sistema DEBE permitir al entrenador registrar el volumen semanal deseado que el alumno le comunica y usarlo para ajustar la intensidad de la rutina (US-14).

- **FR-004**: El sistema DEBE presentar variantes seguras para alumnos con restricciones físicas o articulares cargadas en su perfil (US-53).

- **FR-005**: El sistema DEBE permitir al alumno solicitar un reemplazo de ejercicio si un elemento o máquina no está disponible (US-54).

- **FR-006**: El sistema DEBE permitir al alumno alternar la rutina entre versión gimnasio y versión casa/viaje manteniendo el plan semanal (US-55).



### Key Entities *(include if feature involves data)*

- **AIRoutineDraft**: Borrador de rutina generado por IA a partir del perfil, objetivos y restricciones del alumno, en estado 'PENDING_REVIEW' hasta aprobación del entrenador.

- **AssignedRoutine**: Rutina formalmente aprobada y asignada al alumno por el entrenador, con vigencia y programación de sesiones.

- **ExerciseSafeVariant**: Variante biomecánicamente segura de un ejercicio, asociada a restricciones físicas específicas del alumno.

- **EquipmentAlternative**: Reemplazo de ejercicio para el mismo grupo muscular en caso de máquina ocupada o cambio de entorno (gimnasio vs casa).



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cero rutinas activadas automáticamente por IA sin aprobación humana registrada en auditoría.

- **SC-002**: El 100% de los ejercicios con contraindicaciones médicas detectadas sugieren variantes seguras al entrenador.

- **SC-003**: La solicitud de alternativa de ejercicio por máquina ocupada devuelve opciones válidas en menos de 2 segundos.

- **SC-004**: El 100% de los intentos de agregar un ejercicio contrario a una limitación física del alumno son bloqueados (US-14).

- **SC-005**: El 100% de las ediciones confirmadas quedan registradas con autor, fecha y diferencias (US-14).

- **SC-006**: Guardar o confirmar una edición responde en menos de 1 segundo para rutinas de hasta 7 días × 10 bloques × 30 ejercicios (US-14).

- **SC-007**: El alumno nunca ve contenido en borrador antes de la confirmación (US-14).



## Assumptions

- El modelo de IA devuelve sugerencias estructuradas basadas en las plantillas y reglas de entrenamiento cargadas.

- El entrenador posee el criterio profesional final sobre la idoneidad biomecánica del plan.
