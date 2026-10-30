# Quickstart Validation: Búsqueda de Entrenadores, Perfiles Públicos y Solicitudes de Alta

**Feature**: `004-discovery-and-matchmaking`
**Date**: 2026-10-24

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

## Escenario 2: Envío de Solicitud y Bandeja de Entrada (US-48, US-06)

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

# 2. Entrenador consulta bandeja de solicitudes pendientes
curl -i -X GET "http://localhost:8000/api/v1/matchmaking/requests?status=PENDING" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 OK listando las solicitudes pendientes del entrenador.

# 3. Entrenador consulta detalle de solicitud y datos de salud del alumno
curl -i -X GET "http://localhost:8000/api/v1/matchmaking/requests/<REQUEST_ID>" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

curl -i -X GET "http://localhost:8000/api/v1/students/<STUDENT_PROFILE_ID>/goals" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

curl -i -X GET "http://localhost:8000/api/v1/students/<STUDENT_PROFILE_ID>/health-questionnaire" \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 OK con resumen del alumno, can_be_accepted y datos de salud autorizados.
```

## Escenario 3: Aceptación, Rechazo y Control de Cupos (US-07 Alternativa A)

```bash
# 1. Entrenador con cupo lleno (active_students >= max_students) intenta aceptar
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests/<REQUEST_ID>/accept \
  -H "Authorization: Bearer $FULL_TRAINER_TOKEN"

# Resultado esperado: HTTP 409 Conflict RFC 7807 ("Cupos agotados; libere un cupo para poder aceptar.") sin modificar el cupo.

# 2. Entrenador con cupo disponible acepta la solicitud
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests/<REQUEST_ID>/accept \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"welcome_message": "¡Bienvenido/a al equipo! Preparando tu evaluación inicial."}'

# Resultado esperado: HTTP 200 OK con objeto TrainingRelationship (status="ACTIVE", agreed_monthly_price y agreed_currency copiados).
# El conteo de active_students se incrementa en 1 y el entrenador mantiene acceso a objetivos y datos de salud.

# 3. Entrenador rechaza otra solicitud con motivo opcional
curl -i -X POST http://localhost:8000/api/v1/matchmaking/requests/<OTHER_REQUEST_ID>/reject \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rejection_reason": "Actualmente no realizo preparación específica en esta disciplina."}'

# Resultado esperado: HTTP 200 OK con TrainingRequestResponse (status="REJECTED", rejection_reason y resolved_at registrados).
# No se consume cupo y el acceso del entrenador a los datos de salud del alumno rechazado queda revocado inmediatamente (HTTP 403 Forbidden).
```
