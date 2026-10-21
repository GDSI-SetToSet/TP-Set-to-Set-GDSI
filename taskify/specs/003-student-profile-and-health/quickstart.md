# Quickstart Validation: Perfil del Alumno, Cuestionario de Salud y Apto Médico

**Feature**: `003-student-profile-and-health`
**Date**: 2026-10-15

## Prerrequisitos

- Token JWT de alumno (`$STUDENT_TOKEN`)
- Token JWT de entrenador asignado (`$TRAINER_TOKEN`)
- Token JWT de entrenador sin relación (`$UNAUTHORIZED_TRAINER_TOKEN`)

## Escenario 1: Completar Perfil y Cuestionario PAR-Q (US-39, US-40, US-41)

```bash
# 1. Completar perfil del alumno
curl -i -X PUT http://localhost:8000/api/v1/students/me/profile \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Valeria",
    "last_name": "Gómez",
    "contact_phone": "+5491144445555",
    "birth_date": "1994-05-12",
    "fitness_goals": ["movilidad_rehabilitacion", "fuerza"],
    "personal_motivation": "Recuperar movilidad tras esguince de tobillo"
  }'

# Resultado esperado: HTTP 200 OK con status="PUBLISHED".
# Variantes: fitness_goals=[] -> 422 (perfil no publicado); objetivo fuera del catálogo -> 422;
# contact_phone "+54 9 11 4444-5555" (con espacios) -> 422.
# Visibilidad: GET /api/v1/students/<STUDENT_ID>/goals con $TRAINER_TOKEN -> 403 hasta la spec 004 (stub de acceso), 200 después; con $UNAUTHORIZED_TRAINER_TOKEN -> 403.

# 2. Completar cuestionario médico obligatorio
curl -i -X POST http://localhost:8000/api/v1/students/me/health-questionnaire \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "has_heart_condition": false,
    "has_chest_pain_activity": false,
    "has_dizziness_or_balance_loss": false,
    "has_bone_joint_problem": true,
    "takes_prescription_meds": false,
    "other_medical_conditions": "Tendinitis rotuliana leve en pierna izquierda"
  }'

# Resultado esperado: HTTP 201 Created con status="CURRENT" y has_risk_answers=true (hay un "Sí").
# Variantes:
#  - omitir cualquiera de las 5 preguntas -> 422 (no se asume "No").
#  - reenviar con otras respuestas -> 201; GET /students/me/health-questionnaire devuelve solo la nueva versión.
#  - GET /api/v1/students/me/profile -> health_questionnaire_completed=true (false antes del primer envío).
#  - GET /api/v1/students/<STUDENT_ID>/health-questionnaire con $UNAUTHORIZED_TRAINER_TOKEN -> 403; con $TRAINER_TOKEN -> 403 hasta la spec 004 (stub de acceso), 200 después.
#  - La validación require_health_questionnaire (consumida por las specs 004 y 006) responde 403 mientras el indicador sea false.
```

## Escenario 2: Carga y Consulta Protegida de Apto Médico (US-43, Principio III)

```bash
# 1. Subir certificado médico en PDF
curl -i -X POST http://localhost:8000/api/v1/students/me/medical-clearance \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -F "file=@tests/fixtures/apto_medico_valido.pdf;type=application/pdf" \
  -F "issue_date=2026-10-01"

# Resultado esperado: HTTP 201 Created con status="CURRENT".

# 2. Intento de descarga por entrenador NO autorizado (sin vínculo activo)
curl -i -X GET http://localhost:8000/api/v1/students/<STUDENT_ID>/medical-clearance/download \
  -H "Authorization: Bearer $UNAUTHORIZED_TRAINER_TOKEN"

# Resultado esperado: HTTP 403 Forbidden (Validación estricta del lado del servidor).

# 3. Descarga por entrenador con vínculo activo o por el propio alumno
curl -i -X GET http://localhost:8000/api/v1/students/<STUDENT_ID>/medical-clearance/download \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Resultado esperado: HTTP 200 OK con cabeceras Content-Type: application/pdf y stream del archivo.
```
