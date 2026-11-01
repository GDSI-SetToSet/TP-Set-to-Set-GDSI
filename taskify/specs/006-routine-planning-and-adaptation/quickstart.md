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
