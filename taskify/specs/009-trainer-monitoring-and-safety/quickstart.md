# Inicio rápido: US-18 y US-19 — Alumnos activos y búsqueda

## Prerrequisitos

Desde la raíz del repositorio:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/test_trainer_student_api.py backend/tests/test_ai_routine_api.py
cd frontend && npm run build
```

Usar dos entrenadores, al menos dos alumnos y al menos un vínculo activo y uno terminado. Asignar a un alumno activo un paquete contratado, una zona protegida, una rutina asignada, una sesión completada, un RPE y registros de entrenamiento.

## Escenario 1 — Listar alumnos activos

1. Iniciar sesión como entrenador.
2. Abrir `/entrenador/alumnos`.
3. Confirmar que se muestra cada alumno `ACTIVE` perteneciente a ese entrenador.
4. Confirmar que no aparecen un alumno perteneciente a otro entrenador ni un vínculo `TERMINATED`.

Resultado esperado: el listado existente de “Mis alumnos” permanece disponible y las acciones de asignación de rutinas/progreso continúan funcionando.

## Escenario 2 — Estado vacío

1. Iniciar sesión como entrenador sin vínculos activos.
2. Abrir `/entrenador/alumnos`.

Resultado esperado: la página muestra el mensaje de estado vacío existente y no muestra alumnos no relacionados.

## Escenario 3 — Detalle del alumno

1. Iniciar sesión como el entrenador propietario del vínculo.
2. Abrir `/entrenador/alumnos`.
3. Seleccionar un alumno activo.
4. Verificar los datos del perfil, el paquete contratado y el precio acordado, los objetivos, las zonas protegidas, la rutina vigente y las métricas compactas.
5. Verificar que las acciones existentes de progreso, sesiones, registro de esfuerzo y reportes de dolor continúan disponibles.

Resultado esperado: todos los datos del detalle pertenecen al vínculo activo seleccionado y ninguna rutina en borrador se muestra como vigente.

## Escenario 4 — Autorización

1. Iniciar sesión como otro entrenador.
2. Solicitar el endpoint de detalle usando el ID del alumno del primer entrenador.
3. Terminar el vínculo y repetir la solicitud como el entrenador original.

Resultado esperado: ambas solicitudes son rechazadas según la convención existente de errores de la API; no se divulgan datos de perfil, salud, rutina ni métricas.

## Escenario 5 — Buscar por nombre y apellido

1. Iniciar sesión como un entrenador con al menos dos alumnos activos.
2. Abrir `/entrenador/alumnos`.
3. Buscar por nombre, por apellido y por nombre completo.
4. Repetir una búsqueda usando mayúsculas/minúsculas y omitiendo acentos.

Resultado esperado: solo se muestran los alumnos activos coincidentes.

## Escenario 6 — Búsqueda sin coincidencias y campo vacío

1. Buscar un nombre inexistente.
2. Confirmar que se muestra `No se encontraron alumnos`.
3. Vaciar el campo de búsqueda.

Resultado esperado: no se muestra ningún alumno para la búsqueda inexistente y vuelven a mostrarse todos los alumnos activos al vaciar el campo.

## Verificaciones fuera de alcance

- Filtros por paquete: US-20.
- Mensajería: US-21.
- Comparaciones avanzadas: US-24 compara planificado, realizado y sesión previa en "Rutinas del día"; el gráfico de evolución es US-30).
- Generación/revisión/ordenamiento de alertas: US-29.
- Cálculo del riesgo de abandono: US-32.

## Escenario 7 — Progreso del alumno (US-30)

Prerrequisitos: entrenador con un alumno activo con rutina y varias semanas de sesiones finalizadas (el seed demo carga a Tomás y Valentina).

1. Abrir el detalle del alumno desde `/entrenador/alumnos` con "Ver detalle del alumno".
2. Ver "Progreso de {alumno}", el rango de fechas junto al período y los cuatro indicadores (Progreso, Adherencia, Esfuerzo, Para revisar), cada uno con color y texto.
3. En "¿Está progresando?": la tabla ordena Bajó, Estancado y Progresando; tocar una fila abre su gráfico con el peso objetivo punteado, los récords destacados, el tooltip y la semana en curso hueca con "en curso".
4. En "¿Está entrenando lo que le programé?": barras de sesiones programadas y realizadas por semana, semanas sin sesiones resaltadas y los ejercicios más salteados.
5. En "¿Cómo le está costando?": el mensaje, el gráfico de RPE con la banda 6–8 y huecos en las sesiones sin reporte.
6. En "¿Qué tengo que ajustar?": la lista de puntos a revisar (o "Nada para ajustar por ahora") y las series semanales por grupo muscular contra las programadas.
7. Cambiar Período, Agrupar y Grupo muscular, y confirmar que todo se actualiza; un grupo sin ejercicios muestra "No hay ejercicios de {grupo} en este período".
8. Un alumno sin sesiones muestra "{nombre} todavía no registró entrenamientos".

Resultado esperado: solo cuentan sesiones finalizadas y la semana en curso no altera estados ni porcentajes. Contrato: `contracts/trainer-student-detail-api.yaml` (`/evolution`). Verificación automática: `pytest backend/tests/test_us30_training_evolution_api.py` y `npm test` / `npm run build` en `frontend`.

## Verificaciones fuera de alcance

- Filtros por paquete: US-20.
- Mensajería: US-21.
- Comparaciones avanzadas: US-24 compara planificado, realizado y sesión previa en "Rutinas del día"; el gráfico de evolución es US-30).
- Generación/revisión/ordenamiento de alertas: US-29.
- Cálculo del riesgo de abandono: US-32.

## Escenario 7 — Evolución de entrenamientos (US-30)

Prerrequisitos: entrenador con un alumno activo con al menos 3 sesiones finalizadas en semanas distintas.

1. Abrir el detalle del alumno en `/entrenador/alumnos`.
2. Ver "Progreso de {alumno}" con 12 semanas por defecto, el rango de fechas junto al selector y los indicadores arriba (volumen de la última semana completa, variación, días desde la última sesión y constancia).
3. Alternar la agrupación entre entrenamiento, semana y grupo muscular.
4. Cambiar el período a 4 semanas y a todo el historial.
5. Elegir un ejercicio y confirmar que el gráfico principal pasa a peso máximo.
6. Con un alumno de una sola sesión, ver el valor como indicador; sin sesiones en el período, "Sin entrenamientos en este período"; sin ninguna sesión, "Este alumno todavía no registró entrenamientos".
7. Pasar el mouse por un punto para ver el tooltip ("14–20 sep · 1020 kg"); la semana en curso va punteada, con punto hueco y "en curso". Por grupo muscular se ven barras.

Resultado esperado: solo cuentan sesiones finalizadas; no hay sesiones en curso ni abandonadas. Contrato: `contracts/trainer-student-detail-api.yaml` (`/evolution`). Verificación automática: `pytest backend/tests/test_us30_training_evolution_api.py` y `npm run build` en `frontend`.
