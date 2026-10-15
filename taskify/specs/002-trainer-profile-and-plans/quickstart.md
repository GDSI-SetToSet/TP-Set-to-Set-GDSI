# Quickstart Validation: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Feature**: `002-trainer-profile-and-plans`
**Date**: 2026-10-15

## Prerrequisitos

- Token JWT de usuario autenticado con rol `TRAINER` (`$TRAINER_TOKEN`).

## Escenario 1: Configuración de Perfil Obligatorio (US-02)

```bash
# 1. Intentar actualizar perfil sin teléfono de contacto
curl -i -X PUT http://localhost:8000/api/v1/trainers/me/profile \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Lucas Entrenador",
    "contact_phone": "",
    "specialty": "Fuerza e Hipertrofia"
  }'

# Resultado esperado: HTTP 422 Unprocessable Entity (el contacto es obligatorio).

# 2. Actualizar perfil con todos los campos válidos
curl -i -X PUT http://localhost:8000/api/v1/trainers/me/profile \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Lucas Entrenador",
    "contact_phone": "+54 9 11 5555-1234",
    "specialty": "Fuerza e Hipertrofia",
    "bio": "Profesor de Educación Física con 10 años de experiencia.",
    "certifications": "Lic. en Alto Rendimiento Deportivo"
  }'

# Resultado esperado: HTTP 200 OK con el perfil persistido.
```

## Escenario 2: Publicar Paquetes y Validación de Tarifas (US-03)

```bash
# 1. Intentar crear paquete con tarifa fuera de rango (> 1.000.000)
curl -i -X POST http://localhost:8000/api/v1/trainers/me/plans \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Plan Premium Excesivo",
    "monthly_price": 1500000.00
  }'

# Resultado esperado: HTTP 400 Bad Request / 422 Unprocessable Entity (máximo 1.000.000 ARS).

# 2. Crear paquete válido sin indicar moneda (toma ARS por defecto)
curl -i -X POST http://localhost:8000/api/v1/trainers/me/plans \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Plan Fuerza 3 Días",
    "description": "Rutina personalizada + seguimiento semanal de cargas",
    "monthly_price": 28000.00
  }'

# Resultado esperado: HTTP 201 Created con currency="ARS".
```

## Escenario 3: Ajuste de Cupos Máximos (US-04)

```bash
# 1. Configurar cupos en 20 alumnos
curl -i -X PATCH http://localhost:8000/api/v1/trainers/me/quota \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_students": 20}'

# Resultado esperado: HTTP 200 OK con max_students: 20 y cálculo de available_slots.
```
