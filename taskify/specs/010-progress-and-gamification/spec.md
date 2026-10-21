# Feature Specification: Evolución Física, Marcas Personales, Logros y Rachas

**Feature Branch**: `010-progress-and-gamification`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Seguimiento visual del progreso del alumno mediante gráficos de evolución de cargas, kilaje total y récords personales (PRs), junto con un sistema de motivación basado en medallas por hitos y control de racha de constancia.

**User Stories Cubiertas**: US-65, US-67, US-68

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-65: Evolución de cargas, volumen semanal y récords personales (PRs)] (Priority: P2, Estimación: 5 SP)

Como alumno,
 quiero ver la evolución de mis cargas, mi volumen semanal y mis récords personales a lo largo del tiempo,
 para comprender visualmente mi progreso y mantener la motivación.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno consultando su perfil, cuando accede a la sección de evolución, entonces el sistema muestra un gráfico de la carga por ejercicio a lo largo del tiempo.

2. Dado un alumno en la sección de evolución, cuando selecciona la vista semanal, entonces ve el kilaje total levantado por semana y la comparación de la semana actual con las anteriores.

3. Dado un alumno que no registró entrenamientos en una semana, cuando el sistema calcula el volumen, entonces esa semana se muestra en cero sin afectar el cálculo de las demás.

4. Dado un alumno consultando el gráfico, cuando aplica un filtro, entonces puede filtrar por ejercicio, grupo muscular o rango de fechas.

5. Dado un alumno consultando su historial de PRs, cuando lo visualiza, entonces el sistema lo lista cronológicamente con la fecha en que logró cada uno.


---

### User Story 2 - [US-67: Desbloqueo de logros y medallas] (Priority: P3, Estimación: 3 SP)

Como alumno,
 quiero desbloquear logros al cumplir hitos de entrenamiento y que mi entrenador me reconozca,
 para mantener la motivación y visualizar mi constancia a largo plazo.

**Why this priority**: Funcionalidad clave clasificada con prioridad Baja en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que cumple un hito del catálogo predefinido del MVP (primera sesión completada, 10 sesiones, racha de 4 semanas, primer PR, 5 PRs), cuando el sistema lo detecta, entonces le otorga el logro automáticamente.

2. Dado un alumno que desbloquea un logro, cuando finaliza la sesión correspondiente, entonces la aplicación muestra una celebración en pantalla.

3. Dado un alumno con logros desbloqueados, cuando consulta su perfil, entonces los ve en una sección dedicada con la fecha en que se obtuvo cada uno.

4. Dado un entrenador, cuando un alumno desbloquea un logro, entonces recibe una notificación y puede enviarle una felicitación que el alumno ve en su próxima sesión.


---

### User Story 3 - [US-68: Racha de constancia de entrenamiento] (Priority: P3, Estimación: 3 SP)

Como alumno,
 quiero ver mi racha activa de semanas de entrenamiento constante,
 para mantenerme motivado y no perder el hábito.

**Why this priority**: Funcionalidad clave clasificada con prioridad Baja en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno que cumple la cantidad de sesiones semanales acordadas con su entrenador, cuando termina la semana, entonces el sistema suma una semana a su racha activa.

2. Dado un alumno que no cumple las sesiones acordadas en una semana, cuando la semana termina, entonces la racha se reinicia y se le notifica con un mensaje de aliento para volver a empezar.

3. Dado un alumno o un entrenador consultando el perfil del alumno, cuando lo visualizan, entonces la racha actual y la racha máxima histórica son visibles para ambos.

4. Dado un alumno que abre la aplicación, cuando ve la pantalla de inicio, entonces la racha actual se muestra junto a la rutina del día.


---

### Edge Cases

- ¿Qué ocurre si el alumno tiene menos de dos entrenamientos registrados? El gráfico de evolución muestra un estado informativo indicando que se requieren más sesiones para trazar la tendencia.

- ¿Cómo se actualiza la racha si el alumno descansa los días previstos en su plan? La racha computa el cumplimiento de los días asignados en la semana; no penaliza los días de descanso programados.

- ¿Puede un logro ya desbloqueado perderse? No, las medallas obtenidas quedan permanentemente registradas en el historial del alumno.



## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mostrar gráficos interactivos con la evolución de cargas, tonelaje semanal y récords personales (US-65).

- **FR-002**: El sistema DEBE permitir filtrar la visualización del progreso por ejercicio específico o por grupo muscular (US-65).

- **FR-003**: El sistema DEBE desbloquear automáticamente insignias y medallas al alcanzar hitos de entrenamiento (US-67).

- **FR-004**: El sistema DEBE calcular y mostrar la racha activa de semanas de entrenamiento completadas con éxito (US-68).



### Key Entities *(include if feature involves data)*

- **ProgressChartData**: Series temporales de volumen total semanal (kg), cargas máximas por ejercicio y conteo de récords personales acumulados.

- **AchievementBadge**: Insignia o medalla desbloqueable otorgada al cumplir hitos de constancia, tonelaje o superación personal.

- **StreakCounter**: Contador de semanas o días de entrenamiento consecutivo sin interrupciones del hábito.



## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los gráficos de evolución cargan y renderizan en menos de 500 ms con datos agregados.

- **SC-002**: El desbloqueo de medallas se notifica al alumno inmediatamente al completar la sesión que cumple el hito.

- **SC-003**: El cálculo de racha refleja fielmente el cumplimiento del plan semanal sin falsos reinicios.



## Assumptions

- El sistema de gamificación está orientado a la motivación intrínseca y superación personal.

- No se contempla competencia pública ni tablas de clasificación entre diferentes alumnos en el MVP.


