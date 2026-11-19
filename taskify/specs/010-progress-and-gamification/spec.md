# Feature Specification: Evolución Física, Marcas Personales, Logros y Rachas

**Feature Branch**: `010-progress-and-gamification`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User Story Map y Backlog MVP: Seguimiento visual del progreso del alumno mediante gráficos de evolución de cargas, kilaje total y récords personales (PRs), junto con un sistema de motivación basado en medallas por hitos y control de racha de constancia.

**User Stories Cubiertas**: US-65, US-67, US-68

## Clarifications

### Session 2026-11-15

- Q: ¿Cómo se define un récord personal (PR) de un ejercicio? → A: Mayor peso (kg) registrado en cualquier serie de trabajo completada del ejercicio, sin importar las repeticiones.
- Q: ¿Qué series se suman en el volumen semanal? → A: Solo series de trabajo completadas con peso: Σ(kg × reps); calentamiento y ejercicios sin peso quedan excluidos.
- Q: ¿Qué rango de fechas se muestra por defecto en el gráfico de evolución? → A: Últimas 12 semanas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [US-65: Evolución de cargas, constancia y récords personales (PRs)] (Priority: P2, Estimación: 5 SP)

Como alumno,
 quiero ver si estoy mejorando en cada ejercicio, si estoy siendo constante, qué récords logré y qué me toca en la próxima sesión,
 para comprender mi progreso, mantener la motivación y saber qué esperar de mi próximo entrenamiento.

**Why this priority**: Funcionalidad clave clasificada con prioridad Media en el Backlog-US-MVP para garantizar el flujo operativo del usuario.

**Independent Test**: Puede verificarse ejecutando los escenarios de aceptación correspondientes y comprobando los cambios de estado en la interfaz y persistencia.

**Acceptance Scenarios**:

1. Dado un alumno consultando su perfil, cuando accede a la sección de evolución, entonces ve cada uno de sus ejercicios con una frase que describe su progreso (más peso, más repeticiones con el mismo peso o sin cambios) y puede elegir un ejercicio para ver el gráfico de su carga a lo largo del tiempo, con sus récords destacados y el peso objetivo programado.

2. Dado un alumno en la sección de evolución, cuando consulta su constancia, entonces ve las sesiones realizadas frente a las acordadas por semana. La semana en curso se muestra como "en curso" y no se compara con las anteriores.

3. Dado un alumno que no registró entrenamientos en una semana, cuando consulta su constancia, entonces esa semana se muestra sin sesiones realizadas, sin mensajes de alerta y sin afectar el cálculo de las demás.

4. Dado un alumno consultando su evolución, cuando aplica un filtro, entonces puede filtrar por grupo muscular y elegir el período (4 semanas, 12 semanas o todo el historial).

5. Dado un alumno consultando su historial de PRs, cuando lo visualiza, entonces el sistema lista cronológicamente las marcas que superaron una marca anterior del mismo ejercicio, con la fecha y la marca superada. La primera carga de un ejercicio no se considera récord.

6. Dado un alumno con una próxima sesión programada, cuando consulta su evolución, entonces ve, para cada ejercicio de esa sesión, lo que hizo la última vez y lo que le programó el entrenador, incluidos los ajustes y la devolución del entrenador si existen.

7. Dado un alumno sin sesiones, con una sola sesión o sin rutina asignada, cuando consulta su evolución, entonces se informa cada caso con un mensaje específico en lugar de gráficos vacíos, y en ningún caso se muestran porcentajes negativos ni las palabras "estancado" o "bajó".


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

- **FR-001**: El sistema DEBE mostrar al alumno su progreso por ejercicio, su constancia semanal, sus récords y su próxima sesión, en lenguaje simple y sin diagnosticar: nunca usa "estancado", "bajó", RPE, 1RM, volumen ni porcentajes negativos (US-65).

- **FR-001a**: Un récord personal (PR) es una serie (la mejor del día de un ejercicio) que supera la mejor marca anterior del ejercicio: más peso, o el mismo peso con más repeticiones. La primera carga de un ejercicio no es récord. Siempre se muestra la marca superada (US-65).

- **FR-001b**: El progreso por ejercicio reutiliza el cálculo de la vista del entrenador (US-30) y lo expresa como `message_key`: `weight_increased`, `reps_increased`, `no_change`, `below_best`, `bodyweight_reps_increased` o `few_data`. La semana en curso no entra en ningún cálculo (US-65).

- **FR-001c**: Sin filtros, el período por defecto es de 12 semanas; también se puede elegir 4 semanas o todo el historial (US-65).

- **FR-001d**: La constancia compara sesiones realizadas (finalizadas) con las acordadas (días de la rutina vigente) por semana calendario; una semana está cumplida si realizadas ≥ acordadas. La racha son las semanas cumplidas consecutivas hasta la última semana completa (US-65).

- **FR-001e**: La próxima sesión es el día siguiente, en ciclo, al último finalizado en la rutina vigente. Muestra la última mejor serie y la carga programada por el entrenador; la app no calcula ni sugiere cargas (US-65).

- **FR-002**: El sistema DEBE permitir filtrar la evolución por grupo muscular (US-65).

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


