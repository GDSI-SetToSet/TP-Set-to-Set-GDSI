# Quickstart Validation: Biblioteca de Ejercicios y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15 (actualizado 2026-10-30 tras `/speckit-clarify`)

## Prerrequisitos

- Token JWT de entrenador (`$TRAINER_TOKEN`)
- Token JWT de alumno con vínculo activo con ese entrenador (`$STUDENT_TOKEN`)

## Escenario 1: Biblioteca de Ejercicios (US-08)

```bash
# 1. Intentar crear un ejercicio sin categoría ni músculo
curl -i -X POST http://localhost:8000/api/v1/exercises \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Plancha", "description": "Isométrico de core", "equipment_needed": "Ninguno"}'

# Resultado esperado: HTTP 422 con errors[] para category y target_muscle_group.

# 2. Crear un ejercicio válido
curl -i -X POST http://localhost:8000/api/v1/exercises \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Plancha",
    "description": "Isométrico de core",
    "category": "FUERZA",
    "target_muscle_group": "Abdominales",
    "equipment_needed": "Ninguno",
    "has_no_materials_alternative": true
  }'

# Resultado esperado: HTTP 201 Created.

# 3. Filtrar por músculo
curl -i "http://localhost:8000/api/v1/exercises?muscle_group=abdominales" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 con el ejercicio creado.
```

## Escenario 2: Rutina Genérica (US-09)

```bash
# 1. Crear una rutina con un día, un bloque y un ejercicio
curl -i -X POST http://localhost:8000/api/v1/routine-templates \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Core en Casa",
    "duration_weeks": 4,
    "intensity": "MEDIA",
    "has_no_materials_alternative": true,
    "days": [{
      "name": "Día 1",
      "blocks": [{
        "name": "Principal",
        "exercises": [{"exercise_id": "<EXERCISE_ID>", "sets": 4, "reps": "30 seg", "rest_seconds": 60}]
      }]
    }]
  }'

# Resultado esperado: HTTP 201 Created con exercise_count=1.

# 2. Quitar la marca al ejercicio de la rutina
curl -i -X PUT http://localhost:8000/api/v1/exercises/<EXERCISE_ID> \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Plancha",
    "description": "Isométrico de core",
    "category": "FUERZA",
    "target_muscle_group": "Abdominales",
    "equipment_needed": "Ninguno",
    "has_no_materials_alternative": false
  }'

# Resultado esperado: HTTP 409 Conflict.

# 3. Consultar como alumno con vínculo activo
curl -i http://localhost:8000/api/v1/students/me/routine-templates \
  -H "Authorization: Bearer $STUDENT_TOKEN"

# Resultado esperado: HTTP 200 con la rutina en solo lectura.
```
