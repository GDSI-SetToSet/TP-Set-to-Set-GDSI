---
description: "Task list for 001-auth-and-accounts — incremento US-76 (Recuperación de contraseña)"
---

# Tasks: Autenticación, Gestión de Cuentas y Recuperación

**Input**: Design documents from `taskify/specs/001-auth-and-accounts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/auth-api.yaml, quickstart.md

**Tests**: Obligatorios para el backend (Constitución, Principio VI: pruebas automatizadas y cobertura ≥ 90% en CI). El frontend se verifica con `npm run build` y recorrido manual (no tiene runner de tests; ver plan.md).

**Organization**: Las User Stories 1, 2 y 3 (US-01, US-38, US-75) ya están implementadas en `develop` (PR #1) y no tienen tareas en este archivo. Este archivo cubre la User Story 4 (US-76).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US4 = User Story 4 de spec.md, US-76 del backlog)
- Rutas relativas a la raíz del repositorio (`backend/src/`, `backend/tests/`, `frontend/src/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuración necesaria para la recuperación de contraseña

- [x] T001 Agregar `PASSWORD_RESET_TOKEN_MINUTES = 60`, `PASSWORD_RESET_URL` (por defecto `http://localhost:5173/restablecer-contrasena`), `EMAIL_BACKEND` (`console` | `smtp`, por defecto `console`), `EMAIL_FROM` y `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` en `backend/src/core/config.py`, fallando al iniciar si `EMAIL_BACKEND=smtp` y falta `SMTP_HOST`, y documentarlas en `backend/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entidad, utilidades criptográficas y canal de correo que necesita la US-76

**⚠️ CRITICAL**: La Phase 3 no puede empezar hasta completar esta fase

- [x] T002 Agregar la entidad `PasswordResetToken` (`id`, `user_id` FK con cascada, `token_hash` String(64) único, `expires_at`, `used_at`, `created_at`) y la relación `User.reset_tokens` en `backend/src/models/user.py`; exportarla en `backend/src/models/__init__.py` y registrarla en los imports de `backend/src/main.py` y `backend/tests/conftest.py`
- [x] T003 [P] Agregar `generate_reset_token() -> tuple[str, str]` (token plano con `secrets.token_urlsafe(32)` y su hash SHA-256) y `hash_reset_token(token: str) -> str` en `backend/src/core/security.py`
- [x] T004 [P] Crear `backend/src/services/email_service.py` con el protocolo `EmailSender.send(to, subject, body)`, `ConsoleEmailSender` (registra destinatario, asunto y cuerpo con `logging`), `SmtpEmailSender` (`smtplib` + `EmailMessage`, STARTTLS y login opcionales) y `build_email_sender()` que elige la implementación según `EMAIL_BACKEND`
- [x] T005 [P] Tests de `ConsoleEmailSender` (usando `caplog`), `SmtpEmailSender` (con `smtplib.SMTP` reemplazado por un doble) y `build_email_sender()` en `backend/tests/test_email_service.py`

**Checkpoint**: Modelo, tokens y canal de correo listos

---

## Phase 3: User Story 4 - Recuperación de contraseña (US-76) (Priority: P2)

**Goal**: Un usuario registrado puede pedir un enlace por mail y definir una contraseña nueva con él, en un enlace de un solo uso, de 1 hora, que invalida los anteriores, desbloquea la cuenta y cierra todas las sesiones.

**Independent Test**: Pedir la recuperación desde "Olvidé mi contraseña", abrir el enlace registrado en el log del backend, definir una contraseña nueva y comprobar que el login funciona con la nueva y no con la anterior (quickstart.md, Escenario 3).

### Tests for User Story 4 ⚠️

> **NOTE: Escribir estos tests PRIMERO y comprobar que fallan antes de implementar**

- [x] T006 [US4] Tests de integración en `backend/tests/test_password_reset_api.py`, reemplazando la dependencia `get_email_sender` por un doble que captura los mensajes, para: mail registrado recibe enlace con token (escenario 1); mail no registrado o cuenta inactiva recibe el mismo mensaje y no se envía correo (escenario 2, edge case); mail normalizado; token vencido y token ya usado rechazados (escenario 3); contraseña que no cumple la política rechazada sin consumir el token (escenario 4); solo el último token emitido es válido (escenario 5); restablecimiento desbloquea la cuenta y reinicia intentos (escenario 6); contraseña nueva funciona y la anterior no (escenario 7); sesiones previas revocadas con `/auth/me` devolviendo 401 (escenario 8); token inexistente rechazado; en la base solo se guarda el hash del token

### Implementation for User Story 4

- [x] T007 [P] [US4] Agregar `PASSWORD_RESET_REQUESTED_MESSAGE`, `PASSWORD_RESET_SUCCESS_MESSAGE`, `INVALID_RESET_TOKEN_MESSAGE` y el asunto y cuerpo del correo en `backend/src/core/constants.py`
- [x] T008 [P] [US4] Agregar `ForgotPasswordRequest` (`email`), `ResetPasswordRequest` (`token`, `new_password`) y `MessageResponse` (`message`) en `backend/src/schemas/auth.py`
- [x] T009 [US4] Implementar `request_password_reset(db, email) -> tuple[str, str] | None` en `backend/src/services/auth_service.py`: normaliza el mail, devuelve `None` si la cuenta no existe o está inactiva, marca `used_at` en los tokens vigentes del usuario, persiste el hash del nuevo token con vencimiento a 60 minutos y devuelve el mail y el enlace (depende de T002, T003, T007)
- [x] T010 [US4] Implementar `reset_password(db, token, new_password) -> None` en `backend/src/services/auth_service.py`: valida el token (existente, sin usar, vigente, usuario activo) o lanza `AuthError` 400 con `INVALID_RESET_TOKEN_MESSAGE`; valida la política o lanza `AuthError` 400 con `PASSWORD_REQUIREMENTS_MESSAGE` sin consumir el token; y en una transacción actualiza el hash, marca el token como usado, reinicia `failed_login_attempts` y `locked_until` y revoca todas las `UserSession` activas (depende de T009)
- [x] T011 [US4] Agregar la dependencia `get_email_sender` en `backend/src/api/v1/deps.py` y los endpoints `POST /forgot-password` (siempre 200 con mensaje neutral; envío por `BackgroundTasks`) y `POST /reset-password` (200 con `PASSWORD_RESET_SUCCESS_MESSAGE`) en `backend/src/api/v1/auth.py`, según `contracts/auth-api.yaml` (depende de T004, T008, T010)
- [x] T012 [P] [US4] Agregar las rutas `forgotPassword: '/olvide-mi-contrasena'` y `resetPassword: '/restablecer-contrasena'` en `frontend/src/constants/routes.ts` y los paths `forgotPassword` / `resetPassword` de la API y sus mensajes en `frontend/src/constants/auth.ts`
- [x] T013 [P] [US4] Crear `frontend/src/pages/ForgotPasswordPage.tsx` con `AuthLayout`: campo email, envío a `/api/v1/auth/forgot-password`, mensaje neutral de confirmación y enlace de vuelta al login (depende de T012)
- [x] T014 [P] [US4] Crear `frontend/src/pages/ResetPasswordPage.tsx` con `AuthLayout`: lee `token` de la query, contraseña nueva y confirmación con `PasswordInput`, valida con `meetsPasswordRequirements`, envía a `/api/v1/auth/reset-password`, muestra el error con enlace para pedir uno nuevo y, si sale bien, navega al login con estado `{ passwordReset: true }`; sin token muestra el error de enlace inválido (depende de T012)
- [x] T015 [US4] Registrar las rutas nuevas en `frontend/src/App.tsx`, agregar el enlace "Olvidé mi contraseña" y el aviso de confirmación post-restablecimiento en `frontend/src/pages/LoginPage.tsx`, y los estilos necesarios en `frontend/src/styles/auth.css` (depende de T013, T014)

**Checkpoint**: La US-76 funciona de punta a punta y es verificable de forma independiente

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T016 [P] Documentar en `README.md` las variables de correo y cómo obtener el enlace de recuperación en desarrollo (log del backend)
- [x] T017 Ejecutar `ruff check backend`, `PYTHONPATH=. pytest backend/tests --cov=backend/src --cov-fail-under=90` y `npm run build` en `frontend/` sin errores
- [ ] T018 Recorrer manualmente `quickstart.md` (Escenario 3 y validación en el frontend) contra los escenarios de aceptación de la User Story 4

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T005)** → **US4 (T006–T015)** → **Polish (T016–T018)**
- Backend US4: T006 (tests, fallan) → T007, T008 en paralelo → T009 → T010 → T011
- Frontend US4: T012 → T013, T014 en paralelo → T015. Puede avanzar en paralelo con el backend contra `contracts/auth-api.yaml`.

## Parallel Example: User Story 4

```text
T007 constants.py  |  T008 schemas/auth.py  |  T012 constantes del frontend
T013 ForgotPasswordPage.tsx  |  T014 ResetPasswordPage.tsx
```

## Implementation Strategy

1. Phase 1 y 2: configuración, modelo y canal de correo.
2. Phase 3 backend con tests primero; verificar con quickstart.md vía curl.
3. Phase 3 frontend.
4. Phase 4 y PR de la User Story 4 hacia `develop` (Principio VII).
