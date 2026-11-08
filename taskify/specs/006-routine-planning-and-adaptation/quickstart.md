# Quickstart Validation: Generación de Rutina Particular con IA (US-13)

**Feature**: `006-routine-planning-and-adaptation` (US-13)
**Date**: 2026-10-31

## Prerrequisitos

- Token JWT de entrenador (`$TRAINER_TOKEN`)
- Token JWT de alumno con vínculo activo con ese entrenador (`$STUDENT_TOKEN`)
- ID de alumno con vínculo activo (`$STUDENT_ID`)
- ID de rutina genérica en biblioteca del entrenador (`$TEMPLATE_ID`)

## Escenario 1: Generación de Propuesta con IA y Revisión Humana

```bash
# 1. Listar alumnos activos del entrenador
curl -i http://localhost:8000/api/v1/trainers/me/active-students \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 con lista conteniendo $STUDENT_ID.

# 2. Solicitar propuesta de rutina adaptada por IA
curl -i -X POST http://localhost:8000/api/v1/routines/generate-ai \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "'"$STUDENT_ID"'",
    "template_id": "'"$TEMPLATE_ID"'"
  }'

# Resultado esperado: HTTP 201 Created con:
# - status: "PENDING_REVIEW"
# - adaptation_summary: texto con resumen de adaptaciones y ejercicios sustituidos/eliminados
# - days, blocks, exercises adaptados

# 3. Intentar consultar la rutina como alumno antes de aprobación
curl -i http://localhost:8000/api/v1/students/me/assigned-routine \
  -H "Authorization: Bearer $STUDENT_TOKEN"

# Resultado esperado: HTTP 200 con null (la rutina no está activa al alumno todavía).

# 4. Aprobar explícitamente la rutina como entrenador (Human-in-the-Loop)
curl -i -X POST http://localhost:8000/api/v1/routines/assigned/<ROUTINE_ID>/approve \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 OK con:
# - status: "APPROVED"
# - approved_at: timestamp ISO 8601

# 5. Consultar ahora como alumno
curl -i http://localhost:8000/api/v1/students/me/assigned-routine \
  -H "Authorization: Bearer $STUDENT_TOKEN"

# Resultado esperado: HTTP 200 con la rutina aprobada y visible.

# 6. Verificar que la plantilla genérica original permanece intacta
curl -i http://localhost:8000/api/v1/routine-templates/$TEMPLATE_ID \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 con los ejercicios, días y parámetros originales inalterados.
```

## Escenario 2: Restricción de Privacidad y Vínculo No Autorizado

```bash
# Entrenador B sin vínculo con el alumno intenta generar rutina
curl -i -X POST http://localhost:8000/api/v1/routines/generate-ai \
  -H "Authorization: Bearer $TRAINER_B_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "'"$STUDENT_ID"'",
    "template_id": "'"$TRAINER_B_TEMPLATE_ID"'"
  }'

# Resultado esperado: HTTP 403 Forbidden RFC 7807.
```

---

# Quickstart: validar US-14

**Prerequisitos**: `pip install -r backend/requirements.txt`; entrenador y alumno con vínculo ACTIVE, rutina genérica asignada.

```bash
pytest backend/tests -k student_routine --cov=backend/src --cov-fail-under=90
ruff check backend && (cd frontend && npm run build)
```

**Escenarios manuales** (ver [contrato](./contracts/student-routine-edit-api.yaml)):
1. Editar ejercicio/series/intensidad → guardar borrador → el alumno sigue viendo la versión vigente → confirmar → el alumno ve la nueva.
2. Agregar ejercicio contraindicado para una zona protegida → `422` con alerta; no se guarda.
3. Rutina "Sin materiales": editar sin alternativa → borrador se guarda, confirmar devuelve `422`.
4. Registrar volumen semanal deseado y ajustar intensidad.
5. Dos pestañas editando → la segunda recibe `409`.
6. Tras confirmar existe una entrada en el registro de cambios (autor, fecha, diferencias).

# Quickstart: validar US-53

**Prerequisitos**: entrenador con vínculo ACTIVE a un alumno con zona protegida (p. ej. "Knee"); ejercicio de la biblioteca con `contraindicated_zones` = ["knee"] incluido en la rutina vigente del alumno; ver [contrato](./contracts/safe-variants-api.yaml).

```bash
pytest backend/tests -k safe_variant --cov=backend/src --cov-fail-under=90
ruff check backend && (cd frontend && npm run build)
```

**Escenarios manuales**:
1. Sin variante: el alumno consulta el ejercicio → `BLOCKED`, `can_skip: true`; el entrenador recibe **una** notificación; consultar de nuevo no genera otra.
2. El entrenador vincula una variante que cubre "knee" → el caso pasa a `RESOLVED`; el alumno consulta → `VARIANT` con video/explicación.
3. Alumno con dos zonas (rodilla y hombro) y una variante que cubre solo una → `BLOCKED` (nueva notificación solo si el caso estaba `RESOLVED`).
4. Quitar la zona protegida del alumno o la variante → la siguiente consulta refleja el cambio sin reiniciar la sesión.
5. Alumno consulta un ejercicio que no está en su rutina → `404`; sin vínculo activo → `403`.
6. En US-14, agregar un ejercicio contraindicado ofrece la variante resuelta en `safe_variant` (ya no `null`).

# Quickstart: validar US-54

**Prerequisitos**: entrenador con vínculo ACTIVE; alumno con rutina vigente que incluye un ejercicio de máquina (p. ej. "prensa", grupo "cuádriceps"); biblioteca con otro ejercicio del mismo grupo; ver [contrato](./contracts/exercise-alternatives-api.yaml) y [modelo](./data-model.md).

```bash
pytest backend/tests -k exercise_alternative --cov=backend/src --cov-fail-under=90
ruff check backend && (cd frontend && npm run build)
```

**Escenarios manuales**:
1. El alumno pulsa "sustituir" → ve solo ejercicios del mismo grupo muscular de la biblioteca de su entrenador (esc. 1 y 2).
2. Alumno con zona protegida "knee": las alternativas con "knee" en `contraindicated_zones` no aparecen (esc. 2).
3. Elegir una alternativa → `ExerciseReplacementLog` guardado; la rutina vigente no cambia; al día siguiente vuelve el original (esc. 3).
4. Cambiar de alternativa varias veces → una sola fila, con la última (esc. 3).
5. Cambiar la modalidad a Casa/Viaje → las mismas alternativas (esc. 3).
6. Ejercicio sin ninguna alternativa → lista vacía, `can_skip: true`; saltear registra `replacement_exercise_id` nulo (esc. 4).
7. Ejercicio fuera de su rutina → `404`; sin vínculo activo → `403`; alternativa fuera de la lista → `422`.
8. Medir la consulta con una biblioteca de ~300 ejercicios: < 2 s (SC-003).
