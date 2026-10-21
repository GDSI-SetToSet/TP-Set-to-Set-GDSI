# Feature Specification: Control de Membresías, Pagos Informales y Gestión de Bajas

**Feature Branch**: `011-memberships-and-informal-payments`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Administración del ciclo de vida de membresías y suscripciones mediante registro de cobros informales fuera de la app (efectivo, transferencia), auditoría inmutable con corrección por anulación y reemisión, alertas de vencimiento y gestión de bajas con revocación de accesos.

**User Stories Cubiertas**: US-34, US-35, US-71

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-34: Registrar pagos y controlar el estado de las suscripciones] (Priority: P1, Estimación: 4 SP)

Como entrenador personal,
 quiero registrar los pagos de mis alumnos y ver el estado de cada suscripción,
 para controlar en un solo lugar quién está al día y dejar trazabilidad de cada cobro.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando consulta la sección "Suscripciones", entonces ve el listado de alumnos con paquete contratado, fecha de vencimiento y estado ("Al día", "Por vencer" a 5 días o menos, "Vencida").

2. Dado un entrenador que registra un pago, cuando ingresa fecha, monto, medio (efectivo, transferencia u otro) y período abonado, entonces el sistema extiende el vencimiento de la suscripción y guarda el registro.

3. Dado un entrenador que intenta registrar un pago sin fecha o sin monto, cuando confirma, entonces el sistema no lo registra y le indica los datos faltantes.

4. Dado un alumno que informó un pago (US-71), cuando el entrenador lo revisa, entonces puede confirmarlo (se extiende el vencimiento) o rechazarlo indicando un motivo.

5. Dado un alumno en particular, cuando el entrenador consulta su historial de pagos, entonces ve todos los pagos registrados con fecha, monto, medio y usuario que lo cargó o confirmó. Los registros no pueden eliminarse, solo anularse con un motivo.


---

### User Story 2 - [US-35: dar de baja alumno] (Priority: P1, Estimación: 3 SP)

Como entrenador personal,
 quiero dar de baja una suscripción de un alumno,
 para liberar un cupo por falta de pago del alumno o por razones personales

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un entrenador con alumnos activos, cuando consulta un alumno en particular, entonces debe poder dar de baja la suscripción del alumno.

2. Dado un entrenador que quiere dar de baja a un alumno, cuando indica la razón de la baja, entonces se da de baja la suscripción, el alumno deja de aparecer como activo, deja de generar vencimientos y se libera un cupo.

3. Dado un entrenador que quiere dar de baja a un alumno, cuando no indica la razón de la baja, entonces el sistema no da de baja al alumno y le pide al entrenador una razón para la baja.


---

### User Story 3 - [US-71: Ver vencimiento de la suscripción e informar pago] (Priority: P2, Estimación: 3 SP)

Como alumno,
 quiero ver la fecha de vencimiento de mi suscripción e informar cuando realizo un pago,
 para mantenerme al día y que mi entrenador tenga registrado mi pago.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno con una suscripción vigente, cuando consulta su perfil, entonces el sistema muestra el paquete contratado y la fecha de vencimiento.

2. Dado un alumno a 5 días o menos del vencimiento, cuando abre la aplicación, entonces recibe una alerta de vencimiento próximo y la fecha se destaca visualmente.

3. Dado un alumno que pagó por fuera de la app (efectivo o transferencia), cuando informa el pago con fecha, monto, medio y comprobante opcional, entonces queda "Pendiente de confirmación" hasta que el entrenador lo confirme (US-34).

4. Dado un alumno con la suscripción vencida, cuando consulta su perfil, entonces ve el estado "Vencida" y el entrenador recibe la misma alerta en su panel.

5. Dado un alumno, cuando consulta su historial, entonces ve los pagos confirmados y su estado.


---

### Edge Cases

- ¿Qué ocurre si el entrenador se equivoca al registrar un monto o período? El registro original NO se borra (`NO DELETE`); se anula justificando el motivo y se genera un nuevo registro que referencia al identificador original anulado.

- ¿Qué ocurre cuando la suscripción de un alumno vence sin haberse informado un nuevo pago? (Decisión Alternativa A): El estado pasa a 'VENCIDA'. Se alerta al alumno y al entrenador. El alumno mantiene acceso en modo solo lectura a su historial de entrenamientos pasados, registros previos y métricas, pero se bloquea el acceso a la 'Rutina del día' y la ejecución de nuevas sesiones hasta que se confirme la renovación.

- ¿Qué ocurre cuando el entrenador da de baja a un alumno (US-35)? La suscripción se cancela, el cupo del entrenador se libera de inmediato y se revoca el acceso a datos médicos futuros.

- ¿Cómo informa el alumno un pago realizado por transferencia? El alumno carga fecha, monto, medio y comprobante opcional; el pago queda en 'PENDIENTE_CONFIRMACION' hasta que el entrenador lo valide.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al entrenador registrar cobros manuales indicando fecha, monto, medio (efectivo/transferencia) y período (US-34).

- **FR-002**: Al registrar o confirmar un pago, el sistema DEBE extender automáticamente la fecha de vencimiento de la suscripción (US-34).

- **FR-003**: El sistema DEBE garantizar la inmutabilidad de los pagos, prohibiendo la eliminación física de registros de la base de datos (US-34, Constitución).

- **FR-004**: El sistema DEBE permitir anular un pago justificando el motivo y emitir un nuevo registro correctivo referenciado (US-34, Constitución).

- **FR-005**: El sistema DEBE permitir al entrenador dar de baja a un alumno, liberando un cupo y revocando permisos de salud (US-35).

- **FR-006**: El sistema DEBE mostrar al alumno la fecha de vencimiento y estado de su suscripción ('Al día', 'Por vencer', 'Vencida'). Ante estado 'Vencida', el sistema DEBE permitir consultar el historial en modo solo lectura y bloquear el acceso a nuevas rutinas y registros de entrenamiento (US-71, Decisión Alternativa A).

- **FR-007**: El sistema DEBE destacar visualmente una alerta si el vencimiento opera en 5 días o menos (US-71).

- **FR-008**: El sistema DEBE permitir al alumno informar un pago externo con fecha, monto, medio y comprobante opcional para validación del entrenador (US-71).

- **FR-009**: El sistema NO DEBE integrar pasarelas de pago automatizadas en el MVP (Constitución).



### Key Entities *(include if feature involves data)*

- **MembershipSubscription**: Suscripción activa del alumno con fecha de inicio, fecha de vencimiento, paquete contratado y estado ('AL_DIA', 'POR_VENCER', 'VENCIDA', 'CANCELADA').

- **InformalPaymentRecord**: Registro inmutable de pago: fecha, monto, medio de pago ('EFECTIVO', 'TRANSFERENCIA', 'OTRO'), período abonado, estado ('PENDIENTE_CONFIRMACION', 'CONFIRMADO', 'ANULADO') y comprobante adjunto opcional.

- **PaymentCorrectionAudit**: Vínculo de auditoría que asocia un registro de pago anulado con el nuevo registro emitido, registrando motivo obligatorio, usuario y fecha.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los pagos registrados quedan asentados con trazabilidad inmutable y usuario responsable.

- **SC-002**: Las bajas de alumnos liberan el cupo del entrenador de forma inmediata y verificable.

- **SC-003**: Las alertas de suscripciones por vencer se activan con exactitud al ingresar en la ventana de 5 días previos.



## Assumptions

- El dinero se transfiere directamente entre alumno y entrenador por fuera de la aplicación (banco, billetera virtual o efectivo).

- La plataforma actúa como libro contable y gestor de vigencias de acceso.


