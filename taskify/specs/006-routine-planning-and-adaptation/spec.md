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

### Session 2026-11-01

- Q: Cuando el entrenador edita una rutina ya activa y asignada, ¿los cambios se aplican de inmediato o quedan en borrador hasta confirmarlos? → A: Quedan en borrador y el entrenador los confirma para publicarlos; el alumno sigue viendo la versión vigente hasta entonces.
- Q: Si el entrenador intenta agregar un ejercicio que choca con una limitación física del alumno, ¿puede forzar la edición? → A: No; el bloqueo es absoluto y solo se ofrece la variante segura.
- Q: ¿La alternativa "Sin materiales" se exige en cada guardado de borrador o al confirmar? → A: Solo al confirmar y publicar la rutina.
- Q: ¿Qué se considera ejercicio editado para exigir la alternativa "Sin materiales"? → A: Los ejercicios agregados o reemplazados respecto de la versión vigente.
- Q: ¿Se conserva historial de versiones restaurable o solo un registro de cambios? → A: Solo la versión actual más un registro de cambios (autor, fecha, qué cambió); sin restauración.
- Q: ¿Cómo informa el alumno su volumen semanal deseado? → A: Se lo comunica al entrenador, que lo registra.

### Session 2026-11-07

- Q: ¿Cómo determina el sistema que un ejercicio es "de riesgo" para la restricción de un alumno? → A: Cada ejercicio de la biblioteca lleva etiquetas de zonas de riesgo; las restricciones del perfil del alumno usan las mismas zonas y el sistema las cruza automáticamente.
- Q: Cuando un ejercicio es de riesgo y no tiene variante segura cargada, ¿qué puede hacer el alumno con él? → A: Se bloquea el ejercicio original, se muestra un aviso de que no hay variante segura y el alumno puede saltearlo; el entrenador es notificado.
- Q: Si el alumno tiene varias restricciones y un ejercicio de riesgo, ¿qué variante ve? → A: Una única variante configurada por el entrenador que cubra todas las zonas de riesgo del alumno; si ninguna las cubre todas, se trata como "sin variante segura".
- Q: ¿Cómo se notifica al entrenador la falta de variante y qué pasa con consultas repetidas? → A: Una notificación in-app por combinación alumno + ejercicio; las consultas repetidas no generan otra mientras el caso siga pendiente, y se cierra cuando el entrenador carga la variante.
- Q: ¿Qué pasa si cambian las restricciones del alumno o la variante mientras el alumno la ve? → A: La variante se resuelve en cada consulta con los datos vigentes; los cambios aplican de inmediato, incluso a sesiones ya iniciadas.

### Session 2026-11-08 (US-54)

- Q: Cuando el alumno elige una alternativa para un ejercicio, ¿el reemplazo vale solo para la sesión en curso o cambia su rutina de forma permanente? → A: Solo la sesión en curso; la rutina asignada no cambia y el próximo entrenamiento vuelve al ejercicio original.
- Q: Si el alumno tiene una restricción física, ¿las alternativas ofrecidas deben excluir ejercicios de riesgo para sus zonas protegidas? → A: Sí; solo se ofrecen alternativas sin zonas de riesgo en común con las restricciones del alumno (o su variante segura si el entrenador la cargó); si no queda ninguna, aplica el caso "sin alternativas".
- Q: Cuando el alumno elige una alternativa, ¿se registra el pedido para el entrenador? → A: Sí; se registra para la sesión del día (alumno, rutina, día y fecha; ejercicio original y alternativa elegida), visible al revisarla (US-26), sin notificación.
- Q: ¿Hay un límite de reemplazos del mismo ejercicio por sesión? → A: Sin límite; el alumno puede cambiar de alternativa las veces que quiera y queda registrada solo la última elegida.
- Q: En modalidad "Casa/Viaje", ¿las alternativas deben ser ejercicios sin máquinas? → A: No; el alumno puede estar de viaje con acceso a un gimnasio, por lo que las alternativas se ofrecen igual que en la modalidad por defecto, independientemente de la modalidad activa.

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

1. Dado un alumno con restricciones físicas cargadas en su perfil, cuando consulta un ejercicio de riesgo para esa zona, entonces el sistema le muestra la variante segura configurada por el entrenador. La variante mostrada debe cubrir todas las zonas de riesgo del alumno para ese ejercicio; si ninguna variante las cubre todas, aplica el escenario 2.

2. Dado un ejercicio sin variante segura cargada para una restricción del alumno, cuando el alumno lo consulta, entonces el sistema bloquea el ejercicio original, le informa que no hay variante segura disponible, le permite saltearlo y notifica al entrenador para que revise el caso. La notificación es in-app, única por combinación alumno + ejercicio mientras el caso esté pendiente, y se cierra cuando el entrenador carga la variante.

3. Dado un alumno consultando una variante segura, cuando la visualiza, entonces el sistema muestra su video o explicación asociada


---

### User Story 4 - [US-54: Solicitud de alternativa o reemplazo de ejercicio] (Priority: P2, Estimación: 3 SP)

Como alumno, quiero solicitar una alternativa para un ejercicio específico de mi rutina, para continuar entrenando el mismo grupo muscular si una máquina o elemento está ocupado o no disponible.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno viendo su rutina, cuando presiona el botón de sustituir un ejercicio, entonces el sistema le muestra las alternativas disponibles en la biblioteca de su entrenador.

2. Dado un alumno solicitando una alternativa, cuando el sistema muestra sugerencias, entonces únicamente propone ejercicios de la biblioteca del entrenador (no dados de baja y distintos del original) con el mismo grupo muscular objetivo y, si el alumno tiene restricciones físicas, excluye los ejercicios de riesgo para sus zonas (FR-004); si el entrenador cargó una variante segura de la alternativa, se muestra esa variante. Si no queda ninguna alternativa válida, aplica el escenario 4.

3. Dado un alumno que elige una alternativa, cuando la confirma, entonces el reemplazo aplica solo a la sesión en curso: la rutina asignada no se modifica, los registros de series quedan asociados al ejercicio realmente realizado y el próximo entrenamiento vuelve al ejercicio original. El reemplazo queda registrado para la sesión del día (alumno, rutina, día y fecha; ejercicio original y alternativa elegida) y es visible para el entrenador al revisarla (US-26), sin notificación. No hay límite de cambios por ejercicio y sesión: queda registrada solo la última alternativa elegida. Las alternativas ofrecidas no dependen de la modalidad activa (Gimnasio o Casa/Viaje).

4. Dado un ejercicio sin ninguna alternativa disponible en la biblioteca del entrenador, cuando el alumno solicita un reemplazo, entonces puede saltear el ejercicio y el pedido queda registrado para la sesión del día para que el entrenador cargue una alternativa al revisarla (US-26).


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

- ¿Qué ocurre si el alumno está en el gimnasio y una máquina está ocupada? El alumno puede solicitar un reemplazo directo y el sistema le ofrece una alternativa para el mismo grupo muscular.

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

- **FR-004**: El sistema DEBE presentar variantes seguras para alumnos con restricciones físicas o articulares cargadas en su perfil (US-53). Un ejercicio es "de riesgo" cuando comparte al menos una zona de riesgo (etiqueta del ejercicio en la biblioteca) con una restricción del perfil del alumno; el cruce es automático y usa un catálogo único de zonas para ejercicios y restricciones.

- **FR-005**: El sistema DEBE permitir al alumno solicitar un reemplazo de ejercicio si un elemento o máquina no está disponible (US-54). El reemplazo aplica únicamente a la sesión en curso y no modifica la rutina asignada. Las alternativas ofrecidas a un alumno con restricciones físicas no pueden ser ejercicios de riesgo para sus zonas.

- **FR-006**: El sistema DEBE permitir al alumno alternar la rutina entre versión gimnasio y versión casa/viaje manteniendo el plan semanal (US-55).



### Key Entities *(include if feature involves data)*

- **AIRoutineDraft**: Borrador de rutina generado por IA a partir del perfil, objetivos y restricciones del alumno, en estado 'PENDING_REVIEW' hasta aprobación del entrenador.

- **AssignedRoutine**: Rutina formalmente aprobada y asignada al alumno por el entrenador, con vigencia y programación de sesiones.

- **ExerciseSafeVariant**: Variante biomecánicamente segura de un ejercicio, asociada a restricciones físicas específicas del alumno. Se vincula a un ejercicio y a una o más zonas de riesgo del catálogo común; el ejercicio de la biblioteca porta etiquetas de zonas de riesgo.

- **EquipmentAlternative**: Vista calculada (no persistida) de los ejercicios de la biblioteca del entrenador que trabajan el mismo grupo muscular objetivo que el original y no son de riesgo para el alumno.

- **ExerciseReplacementLog**: Registro por alumno, rutina, día y fecha de sesión del ejercicio original y de la alternativa elegida (o del salto); una sola entrada por ejercicio original, que conserva la última elección.



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

- La variante segura (US-53) se resuelve en cada consulta con las restricciones y variantes vigentes; los cambios del entrenador aplican de inmediato, incluso a sesiones ya iniciadas.

- El modelo de IA devuelve sugerencias estructuradas basadas en las plantillas y reglas de entrenamiento cargadas.

- El entrenador posee el criterio profesional final sobre la idoneidad biomecánica del plan.
