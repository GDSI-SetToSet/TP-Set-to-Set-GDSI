# Feature Specification: Planificación con IA Supervisada, Variantes Seguras y Adaptaciones

**Feature Branch**: `006-routine-planning-and-adaptation`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Generación de borradores de rutinas particulares asistida por IA con revisión humana obligatoria, adaptación a restricciones articulares mediante variantes seguras, solicitudes de reemplazo inmediato de máquinas y alternancia entre versiones gimnasio y casa.

**User Stories Cubiertas**: US-13, US-14, US-53, US-54, US-55

## Clarifications

### Session 2026-10-31 (US-13)

- Q: ¿Qué información del alumno está disponible y debe consumirse para personalizar la rutina? → A: Objetivos de fitness (`fitness_goals`), motivación personal (`personal_motivation`), fecha de nacimiento/edad calculada, zonas corporales protegidas (`protected_zones`), respuestas del cuestionario de salud (`health_questionnaire`) y estado de apto médico. No se envían datos sensibles no pertinentes (teléfono, correo).
- Q: ¿Cómo se identifican y gestionan los ejercicios incompatibles? → A: Un ejercicio es incompatible si su grupo muscular o patrón coincide con una zona protegida del alumno (ej. "Hombro", "Rodilla", "Lumbar") o si contradice una contraindicación médica del cuestionario de salud. La IA debe sustituirlo por un ejercicio alternativo válido de la biblioteca del entrenador o eliminarlo si no existe alternativa disponible.
- Q: ¿Quién puede generar y aprobar una rutina particular para un alumno? → A: Exclusivamente un entrenador con un vínculo activo (`TrainingRelationship.status == "ACTIVE"`) con el alumno en cuestión (Principio III de la Constitución).
- Q: ¿La IA aprueba o activa directamente la rutina? → A: NUNCA. Por mandato constitucional (Principio II - Human-in-the-Loop), la IA genera una propuesta o borrador en estado `PENDING_REVIEW` con un resumen explicativo de las adaptaciones. El entrenador debe revisar y aprobar explícitamente (`APPROVED`) la rutina antes de que quede asignada o activa para el alumno.
- Q: ¿Se modifica la rutina genérica original? → A: No. La plantilla genérica (`RoutineTemplate`) de la biblioteca permanece 100% inalterada. La propuesta y la rutina aprobada se gestionan en una entidad de rutina particular/asignada (`AssignedRoutine`).
- Q: ¿Cómo se gestionan las fallas o respuestas incompletas del mecanismo de IA? → A: Ante una falla técnica o respuesta inválida del proveedor/adaptador de IA, el sistema no persiste rutinas corruptas, informa el error siguiendo RFC 7807 y permite al entrenador reintentar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-13: generar rutina particular con IA] (Priority: P2, Estimación: 5 SP)

Como entrenador personal,
 quiero crear una rutina específica para un alumno en particular usando IA,
 para adaptar el entrenamiento a los objetivos y limitaciones de cada alumno en particular.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Un entrenador con un alumno activo y una rutina genérica en su biblioteca solicita generar una rutina particular con IA. El sistema devuelve una propuesta adaptada a los objetivos y restricciones (ejercicios incompatibles eliminados o sustituidos, intensidades/series adaptadas) en estado "PENDING_REVIEW". La plantilla genérica original permanece intacta. El entrenador aprueba la propuesta y la rutina pasa a estar persistida y aprobada ("APPROVED") para ese alumno. Si un entrenador intenta acceder a un alumno con el que no tiene vínculo activo, el sistema rechaza la acción con HTTP 403.

**Acceptance Scenarios**:

1. **Generación de propuesta adaptada**: Dado un alumno con vínculo activo que tiene objetivos de entrenamiento y limitaciones físicas registradas, y una rutina genérica de la biblioteca del entrenador, cuando el entrenador solicita generar una rutina particular con IA, entonces el sistema genera una propuesta de rutina particular adaptando el tipo, cantidad de series/repeticiones e intensidad de los ejercicios, y presenta un resumen de adaptaciones al entrenador en estado de revisión (`PENDING_REVIEW`).

2. **Eliminación o sustitución de ejercicios incompatibles**: Dado que un ejercicio de la rutina genérica coincide con una zona protegida o restricción de salud del alumno, cuando se genera la rutina particular con IA, entonces el sistema sustituye el ejercicio por una alternativa válida de la biblioteca del entrenador o lo elimina de la rutina, documentando el motivo en el resumen de adaptación.

3. **Supervisión humana obligatoria (Human-in-the-Loop)**: Dada una propuesta de rutina generada por IA, cuando se genera inicialmente, entonces el sistema la conserva en estado `PENDING_REVIEW` y NO la activa automáticamente al alumno hasta que el entrenador revise y apruebe explícitamente la propuesta.

4. **Aprobación y persistencia de la rutina**: Dado un entrenador revisando una propuesta en `PENDING_REVIEW`, cuando presiona la acción de aprobar, entonces la rutina cambia a estado `APPROVED`, queda asignada al alumno correspondiente y vinculada al entrenador, y actualiza el vínculo activo del alumno.

5. **Inmutabilidad de la plantilla genérica original**: Dada la generación y posterior aprobación de una rutina particular con IA basada en una plantilla genérica, cuando se consulta la plantilla genérica en la biblioteca de rutinas, entonces conserva exactamente sus días, bloques, ejercicios y parámetros originales.

6. **Control de autorización y privacidad (Server-Side)**: Dado un entrenador autenticado que intenta solicitar la generación de rutina o acceder a datos de un alumno con el que NO mantiene un vínculo activo ni solicitud autorizada, entonces el sistema responde con HTTP 403 Forbidden.

7. **Manejo de errores del mecanismo de IA**: Dado un fallo en el adaptador de IA o una respuesta no estructurada, cuando se solicita la generación, entonces el sistema captura la excepción, no genera registros inconsistentes y responde con un error RFC 7807 detallado.

**Input**: User Story Map y Backlog MVP: Generación de borradores de rutinas particulares asistida por IA con revisión humana obligatoria, adaptación a restricciones articulares mediante variantes seguras, solicitudes de reemplazo inmediato de máquinas y alternancia entre versiones gimnasio y casa.

**User Stories Cubiertas**: US-13, US-14, US-53, US-54, US-55

## Clarifications

### Session 2026-10-31 (US-13)

- Q: ¿Qué información del alumno está disponible y debe consumirse para personalizar la rutina? → A: Objetivos de fitness (), motivación personal (), fecha de nacimiento/edad calculada, zonas corporales protegidas (), respuestas del cuestionario de salud () y estado de apto médico. No se envían datos sensibles no pertinentes (teléfono, correo).
- Q: ¿Cómo se identifican y gestionan los ejercicios incompatibles? → A: Un ejercicio es incompatible si su grupo muscular o patrón coincide con una zona protegida del alumno (ej. "Hombro", "Rodilla", "Lumbar") o si contradice una contraindicación médica del cuestionario de salud. La IA debe sustituirlo por un ejercicio alternativo válido de la biblioteca del entrenador o eliminarlo si no existe alternativa disponible.
- Q: ¿Quién puede generar y aprobar una rutina particular para un alumno? → A: Exclusivamente un entrenador con un vínculo activo () con el alumno en cuestión (Principio III de la Constitución).
- Q: ¿La IA aprueba o activa directamente la rutina? → A: NUNCA. Por mandato constitucional (Principio II - Human-in-the-Loop), la IA genera una propuesta o borrador en estado  con un resumen explicativo de las adaptaciones. El entrenador debe revisar y aprobar explícitamente () la rutina antes de que quede asignada o activa para el alumno.
- Q: ¿Se modifica la rutina genérica original? → A: No. La plantilla genérica () de la biblioteca permanece 100% inalterada. La propuesta y la rutina aprobada se gestionan en una entidad de rutina particular/asignada ().
- Q: ¿Cómo se gestionan las fallas o respuestas incompletas del mecanismo de IA? → A: Ante una falla técnica o respuesta inválida del proveedor/adaptador de IA, el sistema no persiste rutinas corruptas, informa el error siguiendo RFC 7807 y permite al entrenador reintentar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-13: generar rutina particular con IA] (Priority: P2, Estimación: 5 SP)

Como entrenador personal,
 quiero crear una rutina específica para un alumno en particular usando IA,
 para adaptar el entrenamiento a los objetivos y limitaciones de cada alumno en particular.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Un entrenador con un alumno activo y una rutina genérica en su biblioteca solicita generar una rutina particular con IA. El sistema devuelve una propuesta adaptada a los objetivos y restricciones (ejercicios incompatibles eliminados o sustituidos, intensidades/series adaptadas) en estado "PENDING_REVIEW". La plantilla genérica original permanece intacta. El entrenador aprueba la propuesta y la rutina pasa a estar persistida y aprobada ("APPROVED") para ese alumno. Si un entrenador intenta acceder a un alumno con el que no tiene vínculo activo, el sistema rechaza la acción con HTTP 403.

**Acceptance Scenarios**:

1. **Generación de propuesta adaptada**: Dado un alumno con vínculo activo que tiene objetivos de entrenamiento y limitaciones físicas registradas, y una rutina genérica de la biblioteca del entrenador, cuando el entrenador solicita generar una rutina particular con IA, entonces el sistema genera una propuesta de rutina particular adaptando el tipo, cantidad de series/repeticiones e intensidad de los ejercicios, y presenta un resumen de adaptaciones al entrenador en estado de revisión ().

2. **Eliminación o sustitución de ejercicios incompatibles**: Dado que un ejercicio de la rutina genérica coincide con una zona protegida o restricción de salud del alumno, cuando se genera la rutina particular con IA, entonces el sistema sustituye el ejercicio por una alternativa válida de la biblioteca del entrenador o lo elimina de la rutina, documentando el motivo en el resumen de adaptación.

3. **Supervisión humana obligatoria (Human-in-the-Loop)**: Dada una propuesta de rutina generada por IA, cuando se genera inicialmente, entonces el sistema la conserva en estado  y NO la activa automáticamente al alumno hasta que el entrenador revise y apruebe explícitamente la propuesta.

4. **Aprobación y persistencia de la rutina**: Dado un entrenador revisando una propuesta en , cuando presiona la acción de aprobar, entonces la rutina cambia a estado , queda asignada al alumno correspondiente y vinculada al entrenador, y actualiza el vínculo activo del alumno.

5. **Inmutabilidad de la plantilla genérica original**: Dada la generación y posterior aprobación de una rutina particular con IA basada en una plantilla genérica, cuando se consulta la plantilla genérica en la biblioteca de rutinas, entonces conserva exactamente sus días, bloques, ejercicios y parámetros originales.

6. **Control de autorización y privacidad (Server-Side)**: Dado un entrenador autenticado que intenta solicitar la generación de rutina o acceder a datos de un alumno con el que NO mantiene un vínculo activo ni solicitud autorizada, entonces el sistema responde con HTTP 403 Forbidden.

7. **Manejo de errores del mecanismo de IA**: Dado un fallo en el adaptador de IA o una respuesta no estructurada, cuando se solicita la generación, entonces el sistema captura la excepción, no genera registros inconsistentes y responde con un error RFC 7807 detallado.
---

### User Story 2 - [US-14: editar rutina según objetivos y limitaciones del alumno] (Priority: P2, Estimación: 4 SP)

Como entrenador personal,
 quiero poder editar las rutinas de un alumno (sea genérica o generada por IA),
 para adaptar uno o más ejercicios para respetar los objetivos y limitaciones (físicas o temporales) del alumno.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dada una rutina creada por el entrenador (genérica o IA), cuando el alumno pide un cambio o el entrenador considera necesario modificar parte de la rutina, entonces el sistema debe permitir modificar uno o más ejercicios, intensidad, duración o cualquier parámetro de la rutina.

2. Dado que la rutina creada por el entrenador está disponible "Sin materiales", cuando el entrenador intenta modificar algún ejercicio y no provee alternativa "Sin materiales", entonces el sistema no debe permitir editar el ejercicio y debe mostrar una alerta al entrenador.

3. Dado que el alumno tiene limitaciones físicas establecidas en su perfil, cuando el entrenador intenta introducir un ejercicio que va en contra de dichas limitaciones, entonces el sistema no debe permitir modificar el ejercicio y debe mostrar una alerta al entrenador.

4. Dada una rutina creada por el entrenador, cuando el alumno indica un volumen semanal de entrenamiento deseado, entonces el sistema debe poder permitir editar la intensidad de la rutina para adaptarse a la carga indicada por el alumno.


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

- **FR-003**: El sistema DEBE permitir al entrenador editar ejercicios, series, repeticiones y cargas de la rutina personalizada (US-14).

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



## Assumptions

- El modelo de IA devuelve sugerencias estructuradas basadas en las plantillas y reglas de entrenamiento cargadas.

- El entrenador posee el criterio profesional final sobre la idoneidad biomecánica del plan.


