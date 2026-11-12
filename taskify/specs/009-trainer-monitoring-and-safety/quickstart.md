# Inicio rápido: US-18 — Visualización de alumnos activos

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

## Verificaciones fuera de alcance

- Búsqueda y filtros por paquete: US-19/US-20.
- Mensajería: US-21.
- Comparaciones avanzadas y gráficos: US-24/US-30.
- Generación/revisión/ordenamiento de alertas: US-29.
- Cálculo del riesgo de abandono: US-32.
