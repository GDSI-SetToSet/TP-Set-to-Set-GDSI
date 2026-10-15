# Quickstart Validation: Autenticación, Gestión de Cuentas y Recuperación

**Feature**: `001-auth-and-accounts`
**Date**: 2026-10-15

Esta guía documenta los escenarios de validación ejecutables para verificar la funcionalidad del módulo de autenticación.

## Prerrequisitos

- Python 3.12 y entorno virtual activo (`venv`)
- Dependencias instaladas: `pip install -r backend/requirements.txt`
- Base de datos de pruebas inicializada (SQLite en memoria o local)

## Escenario 1: Registro Exitoso y Redirección por Rol (US-01, US-38)

```bash
# 1. Registrar un nuevo entrenador
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "coach@settoset.com",
    "password": "StrongPassword123",
    "role": "TRAINER"
  }'

# Resultado esperado: HTTP 201 Created con el objeto UserResponse (role: TRAINER).

# 2. Registrar un nuevo alumno
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@settoset.com",
    "password": "StrongPassword123",
    "role": "STUDENT"
  }'

# Resultado esperado: HTTP 201 Created con el objeto UserResponse (role: STUDENT).
```

## Escenario 2: Login y Bloqueo por Fuerza Bruta (US-75)

```bash
# 1. Ejecutar 5 intentos con credenciales erróneas
for i in {1..5}; do
  curl -s -o /dev/null -w "Intento $i: HTTP %{http_code}\n" -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "student@settoset.com", "password": "WrongPassword"}'
done

# Resultado esperado: Los primeros 4 intentos devuelven HTTP 401 Unauthorized ("Mail o contraseña incorrectos").
# El intento 5 activa el bloqueo temporal.

# 2. Verificar que el intento 6 devuelva bloqueo temporal
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "student@settoset.com", "password": "StrongPassword123"}'

# Resultado esperado: HTTP 423 Locked con mensaje indicando bloqueo temporal de 15 minutos.
```

## Escenario 3: Recuperación de Contraseña y Expiración (US-76)

```bash
# 1. Solicitar recuperación
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "coach@settoset.com"}'

# Resultado esperado: HTTP 200 OK con mensaje neutral.

# 2. Restablecer contraseña con el token emitido
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<TOKEN_OBTENIDO>",
    "new_password": "NewSecurePassword2026"
  }'

# Resultado esperado: HTTP 200 OK. La cuenta queda desbloqueada y lista para login con la nueva contraseña.
```
