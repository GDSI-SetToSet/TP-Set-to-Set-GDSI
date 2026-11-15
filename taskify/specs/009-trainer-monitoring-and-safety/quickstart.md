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

- Mensajería: US-21.
- Comparaciones avanzadas y gráficos históricos de cargas: US-30 (US-24 compara planificado, realizado y sesión previa en "Rutinas del día").

---

# Inicio rápido: US-29 — Alertas de seguridad por dolor, molestia repetida o esfuerzo excesivo

## Escenario 7 — Alerta inmediata por dolor (CA-1)

1. Iniciar sesión como alumno activo y comenzar una sesión (`POST /api/v1/students/me/routine-templates/assigned/workout-sessions`).
2. Registrar un reporte de mapa corporal con `PAIN` en una zona (por ejemplo `Shoulder`) durante un ejercicio (`IN_EXERCISE`) y/o al finalizar la sesión (`POST_SESSION`).
3. Consultar `GET /api/v1/trainers/me/notifications` y `GET /api/v1/trainers/me/safety-alerts?status=PENDING` como entrenador propietario del vínculo activo.

Resultado esperado: se persiste `SafetyAlert` (`alert_type=PAIN`, `status=PENDING`) con alumno, zona, ejercicio (si aplica) y sesión, además de preservarse la notificación `PAIN_ALERT` de US-61.

## Escenario 8 — Molestia repetida en 2 sesiones consecutivas e interrupción de secuencia (CA-2)

1. **Dos reportes en la misma sesión**: En la Sesión 1 del alumno (iniciada y con actividad), reportar `DISCOMFORT` en `Knee`. Confirmar que **no** genera alerta `REPEATED_DISCOMFORT`. Registrar un segundo reporte `DISCOMFORT` en `Knee` dentro de la misma Sesión 1 y confirmar que ambos cuentan como una sola sesión y tampoco generan alerta.
2. **Dos sesiones consecutivas**: En la Sesión 2 (siguiente sesión participante cronológica del mismo vínculo), reportar `DISCOMFORT` en `Knee`. Confirmar que se genera `SafetyAlert` (`alert_type=REPEATED_DISCOMFORT`) y notificación `REPEATED_DISCOMFORT_ALERT`.
3. **Sesión intermedia iniciada, con actividad, finalizada y sin molestia**: En Sesión A reportar `DISCOMFORT` en `Shoulder`; registrar Sesión B (iniciada, con `WorkoutSetLog` o reporte `NORMAL`, finalizada y sin `DISCOMFORT` en `Shoulder`); en Sesión C reportar `DISCOMFORT` en `Shoulder`. Confirmar que Sesión B interrumpe la secuencia y **no** se genera alerta entre A y C.
4. **Sesión intermedia iniciada, con actividad, sin finalizar y sin molestia**: En Sesión D reportar `DISCOMFORT` en `Back`; iniciar Sesión E y registrar un `WorkoutSetLog` (sin `DISCOMFORT` en `Back` y dejándola sin finalizar, `finished_at=None`); luego iniciar Sesión F y reportar `DISCOMFORT` en `Back`. Confirmar que Sesión E cuenta pese a no estar finalizada, interrumpe la secuencia y **no** se genera alerta entre D y F.
5. **Sesión creada nunca iniciada y sesión sin actividad registrada**: En Sesión G reportar `DISCOMFORT` en `Ankle`; crear una sesión intermedia nunca iniciada (`started_at=None`) y otra sesión sin `WorkoutSetLog` ni `BodyMapPainReport`; luego iniciar Sesión H y reportar `DISCOMFORT` en `Ankle`. Confirmar que ninguna de esas sesiones vacías/no iniciadas interrumpe la secuencia y que Sesión H **sí** genera `REPEATED_DISCOMFORT` respecto de G. Verificar también que un reporte histórico `POST_SESSION` con `session_id=None` no participa de la secuencia entre sesiones.

## Escenario 9 — Esfuerzo excesivo por RPE 9 o 10 sin duplicados (CA-3)

1. Finalizar una sesión con `rpe = 9` (o registrar `rpe = 10` de manera diferida mediante `PATCH /api/v1/students/me/routine-templates/assigned/workout-sessions/{session_id}/rpe`).
2. Verificar que se crea una única `SafetyAlert` (`alert_type=EXCESSIVE_EFFORT`, `rpe=9|10`) y su notificación `EXCESSIVE_EFFORT_ALERT`.
3. Reenviar idempotente del mismo RPE y confirmar que no se crean alertas duplicadas.

## Escenario 10 — Priorización sobre riesgo de abandono y revisión con acción tomada (CA-4)

1. Configurar un alumno activo A con riesgo de abandono (US-32) sin alertas de seguridad, un alumno activo B con al menos una `SafetyAlert` `PENDING`, y un alumno activo C sin alertas ni riesgo.
2. Consultar `/entrenador/alumnos` y `GET /api/v1/trainers/me/students`. Confirmar el orden: B primero y destacado (US-29), luego A con `"Riesgo de abandono"` (US-32) y luego C.
3. Hacer clic en la notificación en `NotificationBell` (marcando `Notification.is_read = true`) y verificar que B sigue destacado hasta que se llame a `PATCH /api/v1/trainers/me/safety-alerts/{alert_id}/review` con `action_taken` (`ADJUSTED_ROUTINE`, `CONTACTED_STUDENT` o `NO_ACTION`) y `trainer_note` opcional.
4. Una vez revisadas todas las alertas de B, confirmar que A vuelve a encabezar el listado por US-32.

## Escenario 11 — Aviso en la próxima sesión del alumno exclusivo para dolor (CA-5)

1. Revisar como entrenador una alerta `PAIN` (con nota y otra sin nota), una alerta `REPEATED_DISCOMFORT` y una alerta `EXCESSIVE_EFFORT`.
2. Abrir como alumno `/alumno/rutinas/sesion` (`sessionMode`) para iniciar su próxima sesión.
3. Confirmar que únicamente la alerta `PAIN` revisada se muestra en el banner de sesión (junto con la acción y la nota si fue cargada) y se marca como vista (`POST /api/v1/students/me/safety-alerts/{alert_id}/seen`).
4. Abrir una segunda sesión posterior y confirmar que el aviso ya consumido no vuelve a mostrarse, y que nunca se emitieron avisos por `REPEATED_DISCOMFORT` ni `EXCESSIVE_EFFORT`.

## Verificaciones de ejecución automatizada de US-29

```bash
PYTHONPATH=. pytest backend/tests/test_us29_safety_alerts_api.py backend/tests/test_us61_body_map_pain_report_api.py backend/tests/test_us60_rpe_api.py backend/tests/test_us32_abandonment_risk_api.py backend/tests/test_trainer_student_api.py backend/tests/test_database_migrations.py
ruff check backend
cd frontend && npm test && npm run build
```
