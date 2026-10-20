# Feature Specification: Perfil del Alumno, Cuestionario de Salud y Apto Médico

**Feature Branch**: `003-student-profile-and-health`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Gestión del perfil del alumno, incluyendo antecedentes deportivos, motivaciones, cuestionario clínico inicial, reporte de zonas a proteger y almacenamiento protegido del certificado de apto médico con control estricto de privacidad del lado del servidor.

**User Stories Cubiertas**: US-39, US-40, US-41, US-42, US-43

## Clarifications

### Session 2026-10-20

- Q: ¿El nombre del alumno se guarda como dos campos o como un único "nombre completo"? → A: Dos campos obligatorios, nombre (`first_name`) y apellido (`last_name`); el código existente basado en `full_name` se migra/ajusta.
- Q: ¿Qué formato de teléfono acepta el sistema? → A: "+" opcional al inicio y 10 a 15 dígitos, sin espacios ni guiones.
- Q: ¿Qué completa el alumno para finalizar el onboarding inicial? → A: Datos personales obligatorios (nombre, apellido, fecha de nacimiento, teléfono) + al menos un objetivo; recién entonces el perfil pasa a `PUBLISHED`. La motivación personal es opcional y el cuestionario de salud (US-41) es un paso independiente.
- Q: ¿Cuál es el catálogo de objetivos y se admiten objetivos libres? → A: Catálogo cerrado de 6 (fuerza, hipertrofia, resistencia, pérdida de peso, salud general, movilidad/rehabilitación), selección múltiple, sin objetivos libres.
- Q: ¿Quiénes pueden ver objetivos y motivación del alumno? → A: Solo el propio alumno y los entrenadores con solicitud pendiente o relación activa con él; el acceso se revoca al cerrarse la relación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-39: Carga y edición de datos de perfil del alumno] (Priority: Alta, Estimación: 3 SP)

Como alumno,
quiero poder cargar y editar mis datos personales y de contacto,
para completar mi perfil y que los entrenadores puedan conocerme.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para permitir la correcta identificación y contacto del alumno en el sistema.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y la correcta persistencia de los datos.

**Acceptance Scenarios**:

1. Dado que el alumno se encuentra en la vista de edición de perfil.
   Cuando completa los campos obligatorios (nombre, apellido, fecha de nacimiento y teléfono) con formatos válidos (teléfono: "+" opcional y 10 a 15 dígitos, sin espacios ni guiones) y presiona "Guardar".
   Entonces el sistema actualiza la información, muestra un banner verde con el texto "Perfil guardado exitosamente" y redirige al usuario a la vista principal de búsqueda de entrenadores.

2. Dado que el alumno intenta guardar los datos de su perfil.
   Cuando deja un campo obligatorio vacío (ej. nombre).
   Entonces el sistema deshabilita el botón "Guardar" y resalta el campo faltante en rojo con el texto "Este campo es obligatorio".

3. Dado que el alumno ingresa su teléfono de contacto.
   Cuando ingresa un valor que contiene caracteres no numéricos o tiene una longitud fuera del rango de 10 a 15 dígitos y presiona "Guardar".
   Entonces el sistema bloquea la acción y muestra debajo del campo el mensaje "El teléfono debe contener al menos 10 caracteres numéricos".

4. Dado que un alumno con perfil ya completo ingresa a modificar sus datos.
   Cuando edita un campo opcional (ej. foto de perfil o biografía) y presiona "Guardar".
   Entonces el sistema actualiza únicamente esa información, mantiene el estado activo de la cuenta y refleja los nuevos datos de forma inmediata en su perfil visible.


---

### User Story 2 - [US-40: Carga de objetivos de entrenamiento y motivaciones personales] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero indicar mis objetivos de entrenamiento (fuerza, resistencia, pérdida de peso, salud, etc.) y mis motivaciones personales, para que el sistema y los entrenadores puedan ofrecerme rutinas y planes alineados a mis metas.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno completando su perfil, cuando selecciona uno o más objetivos de la lista predefinida, entonces el sistema los guarda correctamente.

2. Dado un alumno que no seleccionó ningún objetivo, cuando intenta finalizar el onboarding inicial (datos personales obligatorios + al menos un objetivo; la motivación personal es opcional), entonces el sistema no le permite continuar y el perfil no pasa a `PUBLISHED`.

3. Dado un alumno con objetivos cargados, cuando un entrenador con solicitud pendiente o relación activa con él evalúa la solicitud o crea una rutina, entonces puede visualizar sus objetivos y motivación; un entrenador sin relación no tiene acceso, y el acceso se revoca al cerrarse la relación.

4. Dado un alumno con objetivos ya cargados, cuando los modifica desde su perfil, entonces los cambios quedan reflejados de inmediato.


---

### User Story 3 - [US-41: Cuestionario inicial de salud y objetivos] (Priority: P1, Estimación: 3 SP)

Como alumno, quiero completar un cuestionario inicial indicando mi historial de salud y mis objetivos de entrenamiento, para que el entrenador diseñe una rutina segura y adaptada a mi situación.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno completando su onboarding, cuando llena el cuestionario inicial de salud y objetivos, entonces el sistema guarda las respuestas en su perfil.

2. Dado un alumno que no completó el cuestionario, cuando intenta enviar una solicitud a un entrenador o acceder a una rutina asignada, entonces el sistema no se lo permite.

3. Dado un alumno con el cuestionario completo, cuando el entrenador evalúa su solicitud o crea una rutina, entonces puede visualizar las respuestas.

4. Dado un alumno cuya situación de salud u objetivos cambió, cuando actualiza el cuestionario, entonces el sistema guarda la nueva información.


---

### User Story 4 - [US-42: Indicar molestias previas o zonas a proteger] (Priority: P1, Estimación: 4 SP)

Como alumno, quiero indicar lesiones previas y zonas de mi cuerpo que debo proteger, para que el entrenador y el asistente de IA eviten asignarme ejercicios contraindicados.

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1.Dado un alumno en su perfil, cuando indica una lesión previa o zona a proteger, entonces el sistema la guarda como restricción física.

2. Dado un alumno con restricciones cargadas, cuando el entrenador intenta asignar manualmente un ejercicio contraindicado, entonces el sistema muestra una advertencia.

3. Dado un alumno con restricciones cargadas, cuando el asistente de IA genera una rutina, entonces excluye automáticamente los ejercicios de riesgo para esas zonas.

4. Dado un alumno cuyas restricciones cambiaron, cuando las actualiza, entonces el sistema reemplaza la información anterior.


---

### User Story 5 - [US-43: Carga de apto médico o certificado físico] (Priority: P1, Estimación: 4 SP)

Como alumno, quiero adjuntar mi certificado de apto médico en formato PDF o imagen, para cumplir con los requisitos de seguridad antes de comenzar a entrenar con un profesional

**Why this priority**: Funcionalidad clave clasificada con prioridad Alta en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que sube un archivo PDF o imagen de su apto médico junto con la fecha de emisión, cuando completa la carga, entonces el certificado queda asociado a su perfil.

2. Dado un alumno que intenta subir un archivo que no es PDF ni imagen, cuando lo carga, entonces el sistema rechaza la carga y solicita un formato válido.

3. Dado un certificado próximo a vencer (30 días de anticipación) o ya vencido, cuando el sistema realiza la verificación periódica, entonces alerta al alumno y al entrenador.

4. Dado un alumno sin certificado vigente cargado, cuando intenta iniciar una rutina activa, entonces el sistema no se lo permite.


---

### Edge Cases

- ¿Qué ocurre si un usuario no autorizado intenta acceder al archivo del apto médico mediante URL directa? El backend deniega el acceso (403 Forbidden / 401 Unauthorized), ya que el archivo reside en almacenamiento protegido y exige validación de sesión y vínculo activo.

- ¿Qué sucede si el alumno sube un nuevo certificado médico teniendo uno previo? (Decisión Alternativa A): El sistema no sobreescribe el anterior; almacena el nuevo certificado en el historial de documentos médicos del alumno, actualiza la fecha de vigencia marcándolo como el activo ('CURRENT') y archiva el anterior para consulta histórica del entrenador.

- ¿Qué sucede si un alumno intenta subir un archivo de apto médico en un formato no soportado (distinto de PDF, PNG, JPG)? El sistema rechaza la carga e indica los formatos permitidos.

- ¿Cómo se maneja si el alumno actualiza sus zonas a proteger luego de tener una rutina asignada? El sistema notifica al entrenador asignado para que revise la rutina vigente.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al alumno cargar y editar sus datos personales y de perfil (US-39), con nombre y apellido como campos obligatorios separados.

- **FR-002**: El sistema DEBE permitir al alumno registrar objetivos de entrenamiento y motivaciones (US-40), eligiendo una o más opciones del catálogo cerrado: fuerza, hipertrofia, resistencia, pérdida de peso, salud general y movilidad/rehabilitación; no se admiten objetivos libres (el texto libre va en la motivación personal).

- **FR-002b**: El sistema DEBE restringir objetivos y motivación personal al alumno y a los entrenadores con solicitud pendiente o relación activa, validado en el backend (US-40).

- **FR-003**: El sistema DEBE proveer un cuestionario inicial de salud obligatorio para relevar patologías y antecedentes médicos (US-41).

- **FR-004**: El sistema DEBE permitir indicar molestias articulares previas o zonas corporales a proteger (US-42).

- **FR-005**: El sistema DEBE permitir al alumno adjuntar su certificado de apto médico en formato PDF o imagen, conservando el historial cronológico de certificados y manteniendo el más reciente como el activo/vigente (US-43, Decisión Alternativa A).

- **FR-006**: El sistema DEBE restringir el acceso a los datos de salud y apto médico exclusivamente al alumno y a su entrenador asignado con autorización validada en el backend (US-43, Constitución).

- **FR-007**: El sistema DEBE revocar inmediatamente el acceso del entrenador a los datos de salud del alumno si se da de baja la relación (US-35, Constitución).



### Key Entities *(include if feature involves data)*

- **StudentProfile**: Perfil personal y deportivo del alumno: nombre y apellido (campos separados), edad, nivel de experiencia y datos de contacto.

- **HealthQuestionnaire**: Cuestionario clínico inicial con antecedentes cardiovasculares, patologías diagnosticadas y objetivos de salud.

- **ProtectedZone**: Zonas corporales o articulaciones señaladas por el alumno con molestias previas o limitaciones que requieren variantes seguras.

- **MedicalClearance**: Documento adjunto (PDF o imagen) de apto físico/médico, con fecha de emisión, fecha de vencimiento, estado de verificación, marca de vigencia ('CURRENT', 'ARCHIVED') y control de acceso restringido con auditoría histórica.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cero fugas de información médica en endpoints públicos o hacia entrenadores sin relación activa confirmada.

- **SC-002**: El 100% de los archivos de apto médico subidos son validados en formato y tamaño antes de persistirse.

- **SC-003**: Los datos de zonas a proteger quedan disponibles inmediatamente para el módulo de planificación de rutinas.



## Assumptions

- El alumno es responsable de la veracidad de los datos médicos declarados.

- El apto médico no requiere validación automática por OCR, sino revisión visual humana por parte del entrenador.


