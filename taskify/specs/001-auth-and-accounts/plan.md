# Implementation Plan: Autenticación, Gestión de Cuentas y Recuperación

**Branch**: `001-auth-and-accounts` | **Date**: 2026-10-15 | **Spec**: [specs/001-auth-and-accounts/spec.md](file:///mnt/r/Proyectos/GDSI/TP-Set-to-Set-GDSI/taskify/specs/001-auth-and-accounts/spec.md)

**Input**: Feature specification from `/specs/001-auth-and-accounts/spec.md` (US-01, US-38, US-75, US-76)

## Summary

Implementar el sistema central de autenticación y gestión de cuentas para la plataforma Set to Set, soportando registro diferenciado para entrenadores y alumnos, inicio/cierre de sesión seguro basado en JWT, mitigación de fuerza bruta con bloqueo temporal de 15 minutos tras 5 intentos fallidos, y restablecimiento seguro de contraseñas con tokens de un solo uso y validez de 1 hora, asegurando respuestas agnósticas para mitigar ataques de enumeración de usuarios.

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript & Node.js 20 (Frontend)

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0, PyJWT, passlib[argon2] / bcrypt, python-multipart
- Frontend: React 18, React Router v6, Axios, Lucide React, Tailwind CSS

**Storage**: PostgreSQL 16 (referencia / producción) / SQLite (tests y CI con Pytest), SQLAlchemy ORM

**Testing**: Pytest con `pytest-cov` (cobertura mínima $\ge 90\%$) y `pytest-asyncio` en Backend; Jest / Vitest y React Testing Library en Frontend

**Target Platform**: Linux Server / Contenedores Docker (Backend API) / Navegador Web moderno responsive (Frontend SPA)

**Project Type**: Aplicación web dividida en `backend/` y `frontend/`

**Performance Goals**:
- Tiempo de respuesta p95 en endpoint de login < 250ms (considerando costo de cómputo del hashing de contraseña)
- Validación de token JWT en memoria/cache < 10ms

**Constraints**:
- Bloqueo de cuenta obligatorio por 15 minutos al registrar 5 intentos consecutivos fallidos (US-75)
- Token de recuperación con vida útil de exactamente 60 minutos y uso único (US-76)
- Respuestas de error neutrales sin filtrar si un correo existe o no en la plataforma (Principio VI y US-75/76)
- Contraseña con política mínima: 8 caracteres, al menos una mayúscula, una minúscula y un número (US-01, US-38)

**Scale/Scope**: Módulo transversal de autenticación para todos los usuarios (entrenadores y alumnos) del MVP.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Justificación / Mecanismo |
|---|---|---|
| I. Enfoque en el Usuario y Accesibilidad | PASSED | Formularios accesibles con labels explícitos, manejo de contrastes, mensajes de error claros y no técnicos. |
| II. IA Asistiva | N/A | Este módulo no interactúa con generación por IA. |
| III. Privacidad y Datos de Salud | PASSED | Control de autorización en backend; credenciales hasheadas con algoritmo seguro; tokens opacos/firmados. |
| IV. Pagos Informales | N/A | No involucra transacciones ni cobros. |
| V. Gestión de Medios | N/A | No gestiona medios externos ni videos. |
| VI. Calidad y Verificación Continua | PASSED | Pruebas unitarias de hashing y servicios, pruebas de integración de endpoints auth, cobertura requerida $\ge 90\%$. |

## Project Structure

### Documentation (this feature)

```text
specs/001-auth-and-accounts/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de alternativas técnicas (Phase 0)
├── data-model.md        # Definición de entidades, restricciones y estados (Phase 1)
├── quickstart.md        # Guía de verificación y ejecución (Phase 1)
└── contracts/
    └── auth-api.yaml    # Especificación OpenAPI 3.0 de endpoints de autenticación
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py          # Endpoints: register, login, logout, password-reset, me
│   │       └── deps.py          # Dependencias de inyección (get_current_user, get_db)
│   ├── core/
│   │   ├── config.py        # Configuración de variables de entorno (JWT_SECRET, ALGORITHM)
│   │   ├── security.py      # Hashing de passwords (Argon2/Bcrypt) y creación de JWT
│   │   └── database.py      # Sesión de SQLAlchemy y Engine
│   ├── models/
│   │   └── user.py          # Entidades User, PasswordResetToken
│   ├── schemas/
│   │   └── auth.py          # Schemas Pydantic (UserCreate, UserLogin, Token, PasswordReset)
│   └── services/
│       └── auth_service.py  # Lógica de registro, autenticación, rate-limiting y tokens
└── tests/
    ├── unit/
    │   └── test_security.py # Tests de hashing, validación de contraseñas y JWT
    └── integration/
        └── test_auth_api.py # Tests de integración de flujos de autenticación y bloqueo

frontend/
├── src/
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── ForgotPasswordPage.tsx
│   │   └── ResetPasswordPage.tsx
│   ├── services/
│   │   └── authService.ts   # Cliente HTTP para endpoints de autenticación
│   └── context/
│       └── AuthContext.tsx  # Manejo de estado de sesión y rol de usuario
└── tests/
    └── auth/
        └── login.test.tsx
```

**Structure Decision**: Arquitectura web estándar desacoplada (`backend/` y `frontend/`) alineada con el pipeline de CI en `.github/workflows/ci.yml`.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Ninguna | N/A | N/A |
