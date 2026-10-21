# Quickstart Validation: Búsqueda de Entrenadores, Perfiles Públicos y Solicitudes de Alta

**Feature**: `004-discovery-and-matchmaking`
**Date**: 2026-10-15

## Prerrequisitos

- Entrenador registrado con plan activo y cupos configurados (`$TRAINER_TOKEN`)
- Alumno registrado con perfil y cuestionario médico completo (`$STUDENT_TOKEN`)

## Escenario 1: Búsqueda y Filtros de Entrenadores (US-44, US-46)

```bash
# 1. Búsqueda por especialidad y precio máximo
curl -i -X GET "http://localhost:8000/api/v1/trainers?specialty=Fuerza&max_price=35000&only_available=true"

# Resultado esperado: HTTP 200 OK con array de entrenadores que cumplen los criterios y tienen cupo libre.

# 2. Consultar perfil público del entrenador
curl -i -X GET "http://localhost:8000/api/v1/trainers/<TRAINER_ID>/public"

# Resultado esperado: HTTP 200 OK con biografía, certificaciones, planes y disponibilidad.
```

## Escenario 2: Envío de Solicitud y Bloqueo de Cupo (US-48, US-06, US-07 Alternativa A)

```bash
# 1. Alumno envía solicitud de contratación de un plan
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trainer_id": "<TRAINER_ID>",
    "plan_id": "<PLAN_ID>",
    "student_message": "Hola, busco mejorar mi sentadilla y corregir postura."
  }'

# Resultado esperado: HTTP 201 Created con status="PENDING".

# 2. Entrenador consulta bandeja de solicitudes
curl -i -X GET "http://localhost:8000/api/v1/matchmaking/requests?status=PENDING" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 OK listando la solicitud recibida.

# 3. Entrenador con cupo lleno (active_students == max_students) intenta aceptar
# (Simulado con entrenador a cupo tope)
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests/<REQUEST_ID>/accept \
  -H "Authorization: Bearer $FULL_TRAINER_TOKEN"

# Resultado esperado: HTTP 409 Conflict con mensaje descriptivo de cupos agotados (Alternativa A).

# 4. Entrenador con cupo disponible acepta la solicitud
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests/<REQUEST_ID>/accept \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"welcome_message": "¡Bienvenido/a al equipo! Preparando tu evaluación inicial."}'

# Resultado esperado: HTTP 200 OK con objeto TrainingRelationship (status="ACTIVE").
```
