# Feature Specification: Autenticación, Gestión de Cuentas y Recuperación

**Feature Branch**: `001-auth-and-accounts`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Gestión del ciclo de vida de autenticación para entrenadores y alumnos, incluyendo registro diferenciado por rol, inicio y cierre de sesión seguro, protección contra ataques de fuerza bruta y restablecimiento de contraseña.

**User Stories Cubiertas**: US-01, US-38, US-75, US-76

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-01: Registro del entrenador con mail y contraseña] (Priority: P1, Estimación: 3 SP)

Como entrenador,
 quiero crear mi cuenta ingresando mail y contraseña,
 para empezar a configurar mi cuenta y conectar con alumnos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado que el entrenador ingresa un mail válido y una contraseña que cumple la política, cuando se registra, entonces la cuenta se crea exitosamente y puede comenzar a usar la aplicación.

2. Dado que el entrenador ingresa un mail inválido, cuando intenta registrarse, entonces la cuenta no se crea y el sistema indica que el mail es inválido para que ingrese otro.

3. Dado que el entrenador ingresa un mail válido pero ya está en uso, cuando intenta registrarse, entonces la cuenta no se crea y el sistema indica que el mail ya está en uso para que ingrese otro.

4. Dado que la contraseña no tiene al menos 8 caracteres, mayúsculas, minúsculas y un número, cuando el entrenador intenta registrarse, entonces la cuenta no se crea y el sistema indica los requisitos que la contraseña no cumple.

5. Dado que el entrenador ingresa un mail que solo difiere de otro ya registrado en mayúsculas o espacios al inicio o al final, cuando intenta registrarse, entonces la cuenta no se crea porque el mail se normaliza antes de verificar su unicidad.


---

### User Story 2 - [US-38: Registro del alumno con mail y contraseña] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero crear mi cuenta ingresando mail y contraseña, para empezar a configurar mi perfil y buscar un entrenador

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado que el alumno ingresa un mail válido, cuando se registra, entonces la cuenta se crea exitosamente y puede comenzar a usar la aplicación.

2. Dado que el alumno ingresa un mail inválido, cuando intenta registrarse, entonces la cuenta no se crea y el sistema indica que el mail es inválido para que ingrese otro.

3. Dado que el alumno ingresa un mail válido pero ya está en uso, cuando intenta registrarse, entonces la cuenta no se crea y el sistema indica que el mail ya está en uso para que ingrese otro.

4. Dado que la contraseña no tiene al menos 8 caracteres, mayúsculas, minúsculas y un número, cuando el alumno intenta registrarse, entonces la cuenta no se crea y el sistema indica los requisitos que la contraseña no cumple.


---

### User Story 3 - [US-75: Inicio y cierre de sesión (entrenador y alumno)] (Priority: P1, Estimación: 3 SP)

Como entrenador o alumno registrado,
 quiero iniciar sesión con mi mail y contraseña y poder cerrarla,
 para acceder de forma segura a mi cuenta y a mis datos desde cualquier dispositivo.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un usuario registrado, cuando ingresa mail y contraseña correctos, entonces accede a la aplicación y el sistema lo redirige según su rol (panel del entrenador o inicio del alumno).

2. Dado un usuario que ingresa un mail o una contraseña incorrectos, cuando intenta iniciar sesión, entonces el sistema muestra un mensaje genérico ("Mail o contraseña incorrectos") sin indicar cuál de los dos falló.

3. Dado un usuario con 5 intentos fallidos consecutivos, cuando intenta nuevamente, entonces el sistema bloquea el acceso a esa cuenta durante 15 minutos y se lo informa.

4. Dado un usuario con sesión iniciada, cuando cierra y vuelve a abrir la aplicación, entonces la sesión se mantiene activa hasta que la cierre manualmente.

5. Dado un usuario con sesión iniciada, cuando presiona "Cerrar sesión", entonces vuelve a la pantalla de inicio y debe ingresar sus credenciales para volver a entrar.

6. Dado un usuario sin sesión iniciada, cuando intenta acceder a cualquier pantalla interna, entonces el sistema lo redirige al inicio de sesión.


---

### User Story 4 - [US-76: Recuperación de contraseña] (Priority: P2, Estimación: 2 SP)

Como entrenador o alumno registrado,
 quiero restablecer mi contraseña si la olvido,
 para no perder el acceso a mi cuenta ni a mi historial de entrenamientos.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un usuario en la pantalla de inicio de sesión, cuando selecciona "Olvidé mi contraseña" e ingresa su mail, entonces el sistema le envía un enlace para restablecerla.

2. Dado un mail que no está registrado, cuando se solicita la recuperación, entonces el sistema muestra el mismo mensaje de confirmación que para un mail registrado (no revela si la cuenta existe).

3. Dado un enlace de recuperación, cuando pasó más de 1 hora o ya fue utilizado, entonces el sistema no permite usarlo y ofrece solicitar uno nuevo.

5. Dado un usuario que solicitó varios enlaces de recuperación seguidos, cuando usa un enlace que no es el último emitido, entonces el sistema lo rechaza por invalidado y ofrece solicitar uno nuevo; solo el último enlace emitido es válido.

6. Dado un usuario con la cuenta bloqueada por 5 intentos fallidos, cuando restablece su contraseña con un enlace válido, entonces el bloqueo se remueve de inmediato, el contador de intentos fallidos vuelve a cero y puede iniciar sesión con la nueva contraseña sin esperar los 15 minutos.

4. Dado un usuario que define una nueva contraseña, cuando no cumple la política de US-01/US-38 (8 caracteres, mayúscula, minúscula y número), entonces el sistema no la guarda y le pide intentarlo nuevamente.


---

### Edge Cases

- ¿Qué ocurre si un usuario intenta iniciar sesión más de 5 veces con credenciales incorrectas? El sistema bloquea temporalmente el acceso a la cuenta durante 15 minutos e informa al usuario sin revelar si la contraseña o el email fueron la causa.

- ¿Cómo maneja el sistema la solicitud de recuperación para un email no registrado? Para mitigar ataques de enumeración de usuarios, el sistema muestra el mismo mensaje genérico de confirmación que para un email registrado, sin enviar ningún correo externo.

- ¿Qué sucede si un token de recuperación supera 1 hora o ya fue utilizado? El sistema invalida la operación y redirige al usuario con opción a solicitar un nuevo enlace.

- ¿Qué ocurre si un usuario registrado intenta registrarse nuevamente con el mismo email? El sistema no permite duplicados y notifica que el email ya está en uso. La comparación se hace sobre el email normalizado (sin espacios en los extremos y en minúsculas), según la Constitución.

- ¿Qué ocurre si se solicitan múltiples enlaces de recuperación seguidos? Cada nuevo enlace invalida todos los anteriores del mismo usuario; solo el último emitido puede usarse.

- ¿Qué ocurre si un usuario bloqueado por intentos fallidos restablece su contraseña con éxito? El restablecimiento remueve inmediatamente el bloqueo temporal de 15 minutos y reinicia el contador de intentos fallidos.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir el registro de entrenadores ingresando email válido y contraseña conforme a la política de seguridad (US-01). El email se normaliza antes de verificar su unicidad (Constitución, Reglas de Dominio Transversales).

- **FR-002**: El sistema DEBE permitir el registro de alumnos ingresando email válido y contraseña conforme a la política de seguridad (US-38). El email se normaliza antes de verificar su unicidad (Constitución, Reglas de Dominio Transversales).

- **FR-003**: El sistema DEBE exigir una política de contraseñas de al menos 8 caracteres, conteniendo al menos una mayúscula, una minúscula y un número (US-01, US-38, US-76).

- **FR-004**: El sistema DEBE permitir iniciar sesión validando credenciales y redirigiendo al panel correspondiente según el rol del usuario (US-75).

- **FR-005**: El sistema DEBE responder con mensajes agnósticos ante credenciales incorrectas ('Mail o contraseña incorrectos') (US-75).

- **FR-006**: El sistema DEBE bloquear temporalmente la cuenta por 15 minutos tras 5 intentos fallidos consecutivos (US-75).

- **FR-007**: El sistema DEBE permitir el cierre de sesión voluntario, invalidando la sesión activa y requiriendo nuevas credenciales para reingresar (US-75).

- **FR-008**: El sistema DEBE restringir el acceso a pantallas internas a usuarios sin sesión activa, redirigiéndolos al inicio de sesión (US-75).

- **FR-009**: El sistema DEBE permitir solicitar el restablecimiento de contraseña mediante envío de enlace temporal al email del usuario (US-76).

- **FR-010**: El sistema DEBE limitar la validez de los enlaces de recuperación a un máximo de 1 hora y a un único uso, e invalidar los enlaces previos de un usuario cada vez que se emite uno nuevo (US-76).

- **FR-011**: El sistema DEBE remover el bloqueo temporal de la cuenta y reiniciar el contador de intentos fallidos al completarse un restablecimiento de contraseña exitoso (US-76, US-75).



### Key Entities *(include if feature involves data)*

- **UserAccount**: Entidad raíz del usuario que almacena email único normalizado, contraseña protegida de forma irreversible, rol del sistema ('TRAINER' o 'STUDENT'), estado de la cuenta ('ACTIVE', 'BLOCKED', 'SUSPENDED') y marcas de auditoría.

- **UserSession**: Representa la sesión activa de un usuario autenticado, gestionando tokens seguros de acceso, expiración y revocación manual al cerrar sesión.

- **PasswordResetToken**: Token efímero de un solo uso para recuperación de credenciales, con vigencia estricta de 1 hora; queda invalidado al emitirse uno más reciente para el mismo usuario.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los intentos de registro con emails duplicados o contraseñas débiles son rechazados con mensajes claros antes de persistir.

- **SC-002**: El bloqueo de cuenta por fuerza bruta se activa de forma determinista exactamente al quinto intento fallido consecutivo.

- **SC-003**: Los tokens de recuperación de contraseña quedan inutilizables inmediatamente después de su primer uso, al expirar los 60 minutos o al emitirse un token más reciente para el mismo usuario.

- **SC-004**: Usuarios no autenticados son interceptados y redirigidos al login en el 100% de los endpoints protegidos.



## Assumptions

- Los usuarios disponen de acceso a una casilla de correo electrónico válida para recibir enlaces de recuperación.

- La persistencia de sesión mantiene al usuario conectado entre aperturas de la app hasta que este seleccione explícitamente cerrar sesión.

- No se requiere autenticación federada (OAuth/Google/Apple) en el alcance del MVP.


