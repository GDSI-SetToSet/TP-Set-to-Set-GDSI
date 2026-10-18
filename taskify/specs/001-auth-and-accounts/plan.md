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

## Incremento US-76: Recuperación de Contraseña (2026-10-18)

US-01, US-38 y US-75 ya están implementadas. Este incremento agrega la US-76 sobre esa base, siguiendo las decisiones de la sesión de clarificación del 2026-10-18 en `spec.md`.

- **Envío de correo intercambiable (FR-013)**: interfaz `EmailSender` en `backend/src/services/email_service.py` con dos implementaciones: `ConsoleEmailSender` (por defecto; registra el enlace en el log del backend) y `SmtpEmailSender` (`smtplib` de la biblioteca estándar, sin dependencias nuevas). Se selecciona con `EMAIL_BACKEND=console|smtp` y se inyecta como dependencia de FastAPI, por lo que los tests la reemplazan por un doble que captura los mensajes. El envío se ejecuta como `BackgroundTask` para que el tiempo de respuesta no dependa de si el mail existe.
- **Tokens (FR-009, FR-010)**: `secrets.token_urlsafe(32)`; se persiste solo su hash SHA-256 en `password_reset_tokens`. Al emitir uno nuevo se marcan como usados (`used_at`) los tokens vigentes previos del usuario. Validez de 60 minutos (`PASSWORD_RESET_TOKEN_MINUTES`).
- **Enlace**: `{PASSWORD_RESET_URL}?token=<token>`, con `PASSWORD_RESET_URL` configurable (por defecto `http://localhost:5173/restablecer-contrasena`).
- **Restablecimiento (FR-003, FR-011, FR-012)**: se valida primero el token (inexistente, usado, invalidado o vencido → 400 con un único mensaje que ofrece pedir otro enlace) y después la política de contraseña (400 con el mensaje de política, sin consumir el token). Si ambos son válidos, en una sola transacción: se actualiza el hash, se marca el token como usado, `failed_login_attempts = 0`, `locked_until = None` y se revocan todas las `UserSession` activas del usuario.
- **Cuentas inexistentes o inactivas**: `forgot-password` responde siempre 200 con el mismo mensaje neutral y no envía correo; `reset-password` trata los tokens de cuentas inactivas como inválidos.
- **Frontend**: páginas `ForgotPasswordPage` (`/olvide-mi-contrasena`) y `ResetPasswordPage` (`/restablecer-contrasena?token=...`), enlace "Olvidé mi contraseña" en el login y aviso de confirmación en el login después de restablecer (estado de navegación). Validación de política en el cliente reutilizando `meetsPasswordRequirements`.
- **Formato de errores**: se mantiene el formato vigente (`{"detail": ...}`) por consistencia con el resto de los endpoints; ver Complexity Tracking.

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
│   │       ├── auth.py          # Endpoints: register, login, logout, forgot-password, reset-password, me
│   │       └── deps.py          # Dependencias de inyección (get_current_user, get_db, get_email_sender)
│   ├── core/
│   │   ├── config.py        # Variables de entorno (JWT, recuperación de contraseña, correo)
│   │   ├── constants.py     # Mensajes y constantes de dominio
│   │   ├── security.py      # Hashing de passwords (Argon2), JWT y tokens de recuperación
│   │   └── database.py      # Sesión de SQLAlchemy y Engine
│   ├── models/
│   │   └── user.py          # Entidades User, UserSession, PasswordResetToken
│   ├── schemas/
│   │   └── auth.py          # Schemas Pydantic (registro, login, recuperación)
│   └── services/
│       ├── auth_service.py  # Lógica de registro, autenticación, bloqueo y recuperación
│       └── email_service.py # EmailSender: implementaciones de consola y SMTP (US-76)
└── tests/
    ├── conftest.py
    ├── test_auth_api.py           # Integración: registro, login, bloqueo y sesión
    ├── test_password_reset_api.py # Integración: recuperación de contraseña (US-76)
    └── test_email_service.py      # Implementaciones de EmailSender

frontend/
└── src/
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── RegisterPage.tsx
    │   ├── ForgotPasswordPage.tsx
    │   └── ResetPasswordPage.tsx
    ├── constants/           # Rutas, paths de la API y mensajes
    ├── services/
    │   └── api.ts           # Cliente HTTP (axios) para la API
    └── context/
        └── AuthContext.tsx  # Manejo de estado de sesión y rol de usuario
```

**Structure Decision**: Arquitectura web estándar desacoplada (`backend/` y `frontend/`) alineada con el pipeline de CI en `.github/workflows/ci.yml`. El frontend todavía no tiene runner de tests; su verificación en CI es `npm run build`. Incorporar Vitest queda fuera del alcance de este incremento.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple rechazada porque |
|---|---|---|
| Errores con formato `{"detail": ...}` en lugar de RFC 7807 (Reglas de Dominio Transversales) | Mantener un único formato en todos los endpoints de auth mientras se migra | Implementar RFC 7807 solo en los endpoints nuevos dejaría dos formatos conviviendo; la migración global se hace en un cambio separado (clarificación 2026-10-18) |
