# Technical Research: Autenticación, Gestión de Cuentas y Recuperación

**Feature**: `001-auth-and-accounts`
**Date**: 2026-10-15

## 1. Algoritmo de Hashing de Contraseñas

- **Decisión**: Utilizar `Argon2id` (vía `passlib[argon2]` o `argon2-cffi`) con fallback transparente a `bcrypt` para entornos restrictivos.
- **Razón**: `Argon2id` es el estándar actual recomendado por OWASP y ganador de la Password Hashing Competition; ofrece resistencia superior contra ataques por hardware dedicado (GPU/ASIC) mediante parametrización de memoria, iteraciones y paralelismo.
- **Alternativas consideradas**:
  - `bcrypt`: Tradicional y robusto, pero limitado a 72 bytes de longitud máxima en contraseñas y menos configurable frente a avances en hardware.
  - `PBKDF2-HMAC-SHA256`: Estándar pero más susceptible a aceleración por GPU.

## 2. Estrategia de Tokens de Sesión y Autenticación

- **Decisión**: JWT (JSON Web Tokens) firmados con algoritmo asimétrico `RS256` o simétrico `HS256` (con clave de al menos 256 bits). El token incluye `sub` (user_id), `role` (`TRAINER` | `STUDENT`), `exp` (tiempo de expiración: 60 minutos en acceso y soporte para refresh token o persistencia en cliente).
- **Razón**: Permite la validación de solicitudes en microservicios o endpoints desacoplados sin consultar obligatoriamente la base de datos en cada verificación de permisos básica, aunque el estado de bloqueo (`locked_until`) se verifica en el backend.
- **Alternativas consideradas**:
  - Sesiones opacas en base de datos/Redis: Mayor control de revocación inmediata, pero introduce dependencia de almacenamiento compartido en cada petición HTTP.

## 3. Mecanismo de Bloqueo por Fuerza Bruta (5 intentos fallidos / 15 minutos)

- **Decisión**: Seguimiento híbrido persistente en la entidad `User` (`failed_login_attempts: int`, `locked_until: datetime | None`). Al superar 5 intentos fallidos consecutivos:
  - Se fija `locked_until = now() + 15 minutes`.
  - Se rechaza cualquier nuevo intento durante esa ventana retornando código HTTP `423 Locked` o `401 Unauthorized` con el detalle del tiempo restante.
  - Al autenticar exitosamente, se resetea `failed_login_attempts = 0` y `locked_until = None`.
- **Razón**: Satisface estrictamente la US-75 sin requerir infraestructura externa de caché (como Redis) obligatoria en el MVP inicial, garantizando consistencia en transacciones de base de datos.
- **Alternativas consideradas**:
  - Redis token-bucket / rate-limiter: Excelente para alta concurrencia, pero agrega dependencia de servicio en el MVP.

## 4. Restablecimiento Seguro de Contraseña (US-76)

- **Decisión**: Generación de tokens criptográficos aleatorios de alta entropía (`secrets.token_urlsafe(32)`). Se almacena el hash del token en la tabla `password_reset_tokens` junto con su `user_id`, `expires_at` (`now() + 1 hour`) y `used_at`.
- **Razón**: Almacenar el hash previene que una brecha en la base de datos comprometa tokens de recuperación activos. El token original solo se envía al correo del usuario y expira de forma irrevocable al ser consumido o al cumplirse 1 hora.
- **Mitigación de Enumeración**: Si el correo no existe en la base de datos al solicitar `POST /auth/forgot-password`, la API responderá con el mismo mensaje de éxito (`200 OK`, "Si el correo está registrado, recibirás un enlace de recuperación"), impidiendo a atacantes comprobar la existencia de cuentas. El envío del correo se hace en segundo plano (`BackgroundTasks`) para que el tiempo de respuesta tampoco dependa de la existencia de la cuenta.

## 5. Canal de Envío de Correo (US-76, FR-013)

- **Decisión**: Interfaz `EmailSender` con `ConsoleEmailSender` (registra el mensaje con `logging`) y `SmtpEmailSender` (`smtplib` + `email.message.EmailMessage`, STARTTLS opcional). Selección por variable de entorno `EMAIL_BACKEND` (`console` por defecto) e inyección como dependencia de FastAPI.
- **Razón**: Permite desarrollar y probar sin servidor de correo, cumple el desacople de infraestructura exigido por la Constitución y no agrega dependencias.
- **Alternativas consideradas**:
  - Proveedor transaccional (SendGrid, Mailgun, Resend): requiere cuenta y SDK; puede incorporarse después como otra implementación de `EmailSender`.
  - Solo SMTP: obliga a cada integrante a configurar un servidor de correo para desarrollar.

## 6. Revocación de Sesiones al Restablecer (FR-012)

- **Decisión**: Al restablecer la contraseña se marca `revoked_at = now()` en todas las `UserSession` del usuario que no estén revocadas. Como `get_current_session` ya rechaza sesiones revocadas, los JWT emitidos antes dejan de funcionar en la siguiente petición.
- **Razón**: Reutiliza el mecanismo de revocación del logout; no requiere listas negras ni cambiar el formato del JWT.
