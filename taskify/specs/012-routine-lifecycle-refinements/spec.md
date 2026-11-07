# Feature Specification: Ciclo de Vida de Rutinas (ajustes post Sprint 3)

**Feature Branch**: `refactor/sprint-3-rutinas`

**Created**: 2026-11-02

**Status**: Implemented

**Input**: Feedback de la demo del Sprint 3: faltaba eliminar rutinas, la navegación de la pantalla de IA era confusa, el seed de demo quedó obsoleto y el entrenador no conservaba las rutinas generadas con IA.

**User Stories Cubiertas**: Ajustes sobre US-13 y US-14 (spec 006) y sobre las rutinas genéricas (spec 005). Por pedido expreso, los cuatro puntos del feedback se entregan en una sola rama.

## Decisiones

Tomadas durante la implementación a partir del feedback; quedan sujetas a validación del equipo.

- Q: ¿Qué pasa si se elimina una rutina asignada a un alumno? → A: Se permite eliminarla. Cada alumno activo que la tenía asignada conserva su copia (`StudentRoutine`), que sigue viendo y que el entrenador puede editar. La rutina deja de estar en la biblioteca y ya no se puede volver a asignar.
- Q: ¿Dónde se guardan las rutinas generadas con IA? → A: En "Mis rutinas", en una sección propia "Generadas con IA". Siguen siendo `AssignedRoutine`, separadas de las genéricas: están adaptadas a un alumno concreto.
- Q: ¿Una rutina con IA se puede reutilizar con otro alumno? → A: No. Se reasigna solo al alumno para el que se generó, porque sus adaptaciones dependen de su salud y sus zonas a proteger.
- Q: ¿Se ven rutinas con IA de alumnos con vínculo terminado? → A: No. Su resumen de adaptación puede revelar datos de salud y el acceso se revoca con el vínculo (Principio III).

## User Scenarios & Testing

### User Story 1 - Eliminar rutinas (Priority: P1)

Como entrenador, quiero eliminar rutinas genéricas o generadas con IA, para mantener ordenada mi biblioteca sin dejar a mis alumnos sin entrenamiento.

**Acceptance Scenarios**:

1. Dada una rutina genérica sin alumnos, cuando el entrenador la elimina y confirma, entonces desaparece de su biblioteca.
2. Dada una rutina asignada a un alumno activo, cuando se elimina, entonces la confirmación avisa cuántos alumnos la tienen y cada alumno conserva su copia vigente, incluidas las ediciones confirmadas.
3. Dada una rutina con IA basada en una genérica, cuando se elimina la genérica, entonces la rutina con IA se conserva sin referencia a su base.
4. Dada una rutina de otro entrenador, cuando se intenta eliminarla, entonces el sistema responde 404 y no la modifica.

### User Story 2 - Volver al lugar de origen (Priority: P3)

Como entrenador, quiero que "Volver" en la pantalla de IA me lleve a donde estaba, para no perder el hilo.

**Acceptance Scenarios**:

1. Dado que entró desde el menú principal, o por enlace directo, cuando presiona volver, entonces llega al inicio.
2. Dado que entró desde "Mis rutinas", cuando presiona volver, entonces regresa a "Mis rutinas".

### User Story 3 - Demo con rutinas precargadas (Priority: P2)

Como integrante del equipo, quiero que el seed cargue ejercicios y rutinas, para no armarlos en vivo durante la demo.

**Acceptance Scenarios**:

1. Dado el seed, cuando se ejecuta, entonces algunos entrenadores tienen ejercicios y rutinas, y otros quedan vacíos para mostrar la carga manual.
2. Dado el seed, cuando se ejecuta, entonces hay un alumno con rutina genérica asignada, uno con rutina con IA aprobada y una propuesta con IA pendiente de revisión.
3. Dado el seed, cuando se ejecuta de nuevo, entonces no duplica datos ni pisa las asignaciones existentes; `--clean` elimina todo lo sembrado.

### User Story 4 - Conservar las rutinas generadas con IA (Priority: P1)

Como entrenador, quiero ver las rutinas que generé con IA, para reutilizarlas sin generarlas otra vez.

**Acceptance Scenarios**:

1. Dada una rutina generada, cuando entra a "Mis rutinas", entonces la ve distinguida como IA, con su alumno, su estado y el resumen de adaptaciones.
2. Dada una propuesta pendiente, cuando la aprueba desde "Mis rutinas", entonces queda asignada al alumno (la supervisión humana sigue siendo obligatoria).
3. Dada una rutina con IA aprobada que ya no está asignada, cuando la reasigna al mismo alumno, entonces el alumno vuelve a verla sin regenerarla.
4. Dado que ya existe una rutina generada para ese alumno y esa base, cuando abre la pantalla de generación, entonces el sistema se lo avisa y permite abrirla sin consumir otra generación.
5. Dada una propuesta sin aprobar, cuando el entrenador intenta asignarla, entonces el sistema responde 404 y el alumno no la ve.

## Functional Requirements

- **FR-001**: `DELETE /api/v1/routine-templates/{id}` y `DELETE /api/v1/routines/assigned/{id}` DEBEN eliminar una rutina propia y responder 204.
- **FR-002**: Antes de eliminar, el sistema DEBE materializar la copia `StudentRoutine` de cada vínculo activo que la tenga asignada y limpiar `initial_routine_id`.
- **FR-003**: `GET /api/v1/routines/assigned` DEBE listar las rutinas con IA del entrenador cuyos alumnos tengan vínculo activo, de la más reciente a la más antigua.
- **FR-004**: `PUT /api/v1/routine-templates/assignments/{relationship_id}` DEBE aceptar rutinas con IA aprobadas del alumno de ese vínculo y rechazar con 404 cualquier otra.
- **FR-005**: La interfaz DEBE pedir confirmación antes de eliminar.
- **FR-006**: El seed DEBE seguir siendo idempotente y sus rutinas DEBEN pasar las validaciones de `RoutineTemplateInput`.

## Success Criteria

- **SC-001**: La demo no requiere cargar ejercicios ni rutinas a mano para recorrer asignación, edición, aprobación y eliminación.
- **SC-002**: Ningún alumno pierde su rutina vigente porque el entrenador elimine la rutina de origen.
- **SC-003**: Sin cambios de esquema ni migraciones nuevas.
