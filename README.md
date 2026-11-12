# Set to Set

**Plataforma de gestión y seguimiento del entrenamiento físico**

## Ruta de sesión de rutina

Los alumnos acceden a una sesión activa mediante `/alumno/rutinas/sesion`.

## Descripción

Set to Set es una plataforma que busca conectar a entrenadores personales con personas que desean entrenar, facilitando la planificación de rutinas, el seguimiento del progreso físico y la comunicación entre ambas partes.

El proyecto propone centralizar en un mismo lugar las herramientas necesarias para organizar el entrenamiento, registrar resultados y gestionar la relación entre entrenadores y alumnos.

## Integrantes

- Arroquy Facundo 109743 faarroquy@fi.uba.ar
- Gualdi Martina 110513 martugualdi@gmail.com
- Franco Agustín Finocchi Martín 110715 ffinocchi@fi.uba.ar
- Bruno Pezman 110457 bpezman@fi.uba.ar
- Axel Zielonka 110310 azielonka@fi.uba.ar
- Delfina Videla 111620 dpvidela@fi.uba.ar

## Metodología de desarrollo

El proyecto utiliza **Spec-Driven Development (SDD)** como enfoque de trabajo. Las funcionalidades se describen mediante especificaciones antes de planificar e implementar sus soluciones técnicas.

El objetivo es mantener la trazabilidad entre las necesidades del producto, las historias de usuario, las tareas de desarrollo y los cambios incorporados al repositorio.

### Flujo de trabajo

1. **Constitución del proyecto:** definición de principios, restricciones y criterios generales de desarrollo.
2. **Especificación:** descripción de las funcionalidades y sus criterios de aceptación.
3. **Clarificación:** resolución de dudas y detección de requisitos ambiguos.
4. **Planificación técnica:** definición de la solución y sus decisiones técnicas.
5. **Descomposición en tareas:** división del trabajo en unidades implementables.
6. **Implementación incremental:** desarrollo de funcionalidades mediante ramas independientes.
7. **Revisión e integración:** evaluación de los cambios mediante Pull Requests y controles de calidad.

### Herramientas de trabajo

- **Git y GitHub:** control de versiones, colaboración y revisión de cambios.
- **Google Antigravity:** asistencia durante las tareas de especificación y desarrollo.
- **Spec Kit:** soporte para organizar el flujo de trabajo basado en especificaciones.

## Organización del repositorio

La estructura del repositorio se irá consolidando a medida que avance el proyecto. Se busca mantener separados los artefactos de especificación, la planificación técnica, las tareas y el código fuente.

Los archivos de configuración y las especificaciones compartidas forman parte de los artefactos del proyecto y deben mantenerse versionados cuando corresponda.

## Módulos y rutas implementadas (Sprints 1 y 2)

### Rutas del Frontend (`frontend/src/constants/routes.ts` y `frontend/src/App.tsx`)

- **Autenticación (`001`):** `/login`, `/registro`, `/olvide-mi-contrasena`, `/restablecer-contrasena`, `/inicio`
- **Entrenador (`002` / `004` / `005` / `006` / `009`):** `/entrenador/inicio`, `/entrenador/perfil`, `/entrenador/paquetes`, `/entrenador/ejercicios`, `/entrenador/rutinas`, `/entrenador/rutinas/generar-ia`, `/entrenador/alumnos`, `/entrenador/alumnos/:studentId/rutina`, `/entrenador/rutinas-del-dia`, `/entrenador/solicitudes`, `/entrenador/solicitudes/:requestId`
- **Alumno (`003` / `004` / `005`):** `/alumno/inicio`, `/alumno/perfil`, `/alumno/salud`, `/alumno/zonas-a-proteger`, `/alumno/apto-medico`, `/alumno/buscar-entrenadores`, `/entrenadores/:trainerId`, `/entrenadores/:trainerId/solicitar`, `/alumno/mis-solicitudes`, `/alumno/mis-entrenamientos`, `/alumno/rutinas`

### Endpoints principales de la API (`backend/src/api/v1/`)

- **Autenticación (`/api/v1/auth`):** `POST /register`, `POST /login`, `POST /logout`, `GET /me`, `POST /forgot-password`, `POST /reset-password`
- **Perfil, paquetes y cupos de entrenador (`/api/v1/trainers`):**
  - `GET /me/profile`, `PUT /me/profile`, `GET /{trainer_id}/profile`
  - `POST /me/plans`, `GET /me/plans`, `PUT /me/plans/{plan_id}`, `POST /me/plans/{plan_id}/archive`, `GET /{trainer_id}/plans`
  - `PATCH /me/quota`
  - `GET /search`, `GET /{trainer_id}/public`
  - `GET /me/notifications`, `PATCH /me/notifications/{notification_id}/read`
- **Perfil y salud del alumno (`/api/v1/students`):**
  - `GET /me/profile`, `PUT /me/profile`, `GET /{student_id}/goals`
  - `POST /me/health-questionnaire`, `GET /me/health-questionnaire`, `GET /{student_id}/health-questionnaire`
  - `GET /me/protected-zones`, `PUT /me/protected-zones`
  - `POST /me/medical-clearance`, `GET /me/medical-clearance`, `GET /{student_id}/medical-clearance/download`
  - `GET /me/active-plan`, `GET /me/active-plans`
  - `GET /me/notifications`, `PATCH /me/notifications/{notification_id}/read`
- **Biblioteca de ejercicios (`/api/v1/exercises`):** `GET /`, `POST /`, `GET /{exercise_id}`, `PUT /{exercise_id}`, `DELETE /{exercise_id}`
- **Rutinas genéricas (`/api/v1/routine-templates`):** `GET /`, `POST /`, `GET /{template_id}`, `PUT /{template_id}`, `GET /assignments`, `PUT /assignments/{relationship_id}`
- **Rutinas para alumnos (`/api/v1/students/me/routine-templates`):** `GET /`, `GET /assigned`, `GET /{template_id}`
- **Solicitudes y vinculación (`/api/v1/matchmaking`):**
  - `POST /requests`, `GET /requests/mine`, `GET /requests`, `GET /requests/{request_id}`
  - `POST /requests/{request_id}/accept`, `POST /requests/{request_id}/reject`

## Desarrollo local: cómo levantar la aplicación

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn backend.src.main:app --reload
```

La API queda disponible en `http://localhost:8000`. La documentación interactiva está en `http://localhost:8000/docs`. 

Para producción, configurar `APP_ENV=production` y `JWT_SECRET` con un valor aleatorio de al menos 32 caracteres. La API no inicia en producción si falta el secreto o es demasiado corto.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrí `http://localhost:5173`. Se puede crear una cuenta como alumno o entrenador; el registro inicia la sesión y muestra la pantalla correspondiente al rol. Las rutas internas requieren una sesión válida.

### Recuperación de contraseña

Por defecto (`EMAIL_BACKEND=console`) el backend no envía correos: el enlace de recuperación se escribe en el log de `uvicorn`. Para enviarlo por correo, configurar en `backend/.env` `EMAIL_BACKEND=smtp` junto con `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` y `EMAIL_FROM`. `PASSWORD_RESET_URL` define la pantalla del frontend a la que apunta el enlace.

### Pruebas

Desde la raíz del repositorio (con .venv activado):

```bash
PYTHONPATH=. pytest backend/tests --cov=backend/src --cov-report=term-missing
```

### Datos de demostración (Seed para demo académica)

El repositorio incluye un script idempotente para inicializar datos ficticios de prueba (alumnos, entrenadores con paquetes publicados, cuestionarios de salud, solicitudes, vínculos activos, ejercicios, rutinas e historial de entrenamiento) que permiten recorrer de punta a punta descubrimiento, solicitudes, asignación, seguimiento, reportes de molestias, devoluciones de esfuerzo, récords personales y rutinas sin cargarlo en vivo:

- **Lucas Benítez:** ejercicios y dos rutinas genéricas.
- **Mariana Vega:** ejercicios, tres rutinas genéricas (incluida una en casa con videos de YouTube) y a Martín Herrera con una rutina con IA aprobada.
- **Gonzalo Morales:** ejercicios, dos rutinas genéricas, a Tomás Castro con una rutina asignada y una propuesta con IA pendiente de revisión.
- **Valentina Rossi:** vínculo activo con Lucas, sesiones históricas, un reporte de dolor de rodilla con una variante segura ya cargada y récord de sentadilla.
- **Camila Torres:** vínculo activo con Camila Navarro para mostrar el estado inicial de carga de una rutina.
- **Ignacio Rossi y Camila Navarro:** sin ejercicios ni rutinas, para mostrar la carga manual.
- La biblioteca incluye 46 ejercicios variados, alternativas para sustituir ejercicios, variantes seguras precargadas y ejercicios con videos de YouTube.

Para sembrar o actualizar los datos de demostración:

```bash
python backend/scripts/seed_demo.py
```

Para limpiar exclusivamente los datos de demostración sin tocar otros registros:

```bash
python backend/scripts/seed_demo.py --clean
```

Para reiniciar los datos de demostración (limpieza y re-sembrado en un paso):

```bash
python backend/scripts/seed_demo.py --reset
```

> **Credenciales locales:** En desarrollo, todas las cuentas de prueba comparten `DemoPassword123!` y pertenecen al dominio `@demo.settoset.com` (ej. `lucas.benitez@demo.settoset.com`, `mateo.gomez@demo.settoset.com`). En producción se usa el valor protegido de `DEMO_SEED_PASSWORD`.

#### Ejecución contra producción

Para sembrar datos ficticios en PostgreSQL de producción, ejecutá el script desde el contenedor o entorno que ya tenga configurado el `DATABASE_URL` de producción. Antes, cargá estas variables desde el gestor de secretos del entorno:

- `APP_ENV=production`.
- `DEMO_SEED_PASSWORD`: contraseña de las cuentas demo, de al menos 12 caracteres, con mayúscula, minúscula y número.
- `DATABASE_URL`: conexión PostgreSQL de producción.

Aplicá primero las migraciones de la versión mediante el proceso normal de despliegue. Luego ejecutá:

```bash
python backend/scripts/seed_demo.py --production-demo --confirm-production-demo
```

Este modo verifica que la base sea PostgreSQL y que tenga las tablas actuales; no crea tablas ni aplica migraciones. Sólo agrega o actualiza registros con cuentas `@demo.settoset.com`, no permite `--clean` ni `--reset`, y establece la contraseña de todas esas cuentas desde `DEMO_SEED_PASSWORD`. Conservá esa contraseña en el gestor de secretos y compartila sólo con quienes necesiten entrar a la demo.

### Generación de rutinas particulares con IA — Google Gemini (US-13)

La historia US-13 permite que un entrenador genere una propuesta de rutina particular (`PENDING_REVIEW`) adaptada a los objetivos y restricciones de un alumno con vínculo activo, reutilizando la interfaz `AIRoutineAdapter` con soporte para **Google Gemini API** (`gemini`) y para el **adaptador heurístico local** (`heuristic`).

#### 1. Cómo obtener una API Key gratuita en Google AI Studio

1. Ingresar a [Google AI Studio](https://aistudio.google.com/apikey) con una cuenta de Google.
2. Hacer clic en **Create API key** (no requiere tarjeta de crédito para utilizar el Free Tier).
3. Copiar la clave generada. **Nunca** subirla a Git ni compartirla en archivos versionados.
   - *Nota de privacidad del Free Tier:* Usar exclusivamente perfiles ficticios de prueba durante el MVP.

#### 2. Configuración de variables de entorno

En `backend/.env` (o en `.env` en la raíz del proyecto, ambos excluidos por `.gitignore`), configurar:

```env
# Proveedor de IA: gemini | heuristic
AI_PROVIDER=gemini
GEMINI_API_KEY=tu_clave_de_google_ai_studio_aqui
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=30
```

- **`AI_PROVIDER`**: selecciona el adaptador activo (`gemini` para Google Gemini API o `heuristic` para el motor determinista local). Si no se especifica en el entorno, el sistema utiliza `heuristic` por defecto para no consumir cuota en ejecuciones de CI/tests.
- **`GEMINI_API_KEY`**: clave obtenida en Google AI Studio.
- **`GEMINI_MODEL`**: modelo disponible en el Free Tier de Gemini API con soporte de salida estructurada JSON Schema (por defecto `gemini-3.5-flash-lite`).
- **`GEMINI_TIMEOUT_SECONDS`**: tiempo máximo de espera por solicitud en segundos (por defecto `30`).

#### 3. Cómo ejecutar y probar la integración localmente con perfiles ficticios

1. Sembrar los perfiles ficticios de demostración (`python backend/scripts/seed_demo.py`).
2. Levantar el backend (`uvicorn backend.src.main:app --reload`) y el frontend (`cd frontend && npm run dev`).
3. Iniciar sesión como entrenador de demostración con vínculo activo (por ejemplo, `mariana.vega@demo.settoset.com` o `gonzalo.morales@demo.settoset.com` con contraseña `DemoPassword123!`), crear al menos una rutina genérica en `/entrenador/rutinas` y dirigirse a `/entrenador/rutinas/generar-ia`.
4. Seleccionar el alumno activo ficticio y la rutina base, y presionar **Generar propuesta de rutina con IA**.
5. Revisar el resumen de adaptaciones (`KEEP`, `REPLACE`, `REMOVE`) y aprobar explícitamente la rutina para asignarla al alumno sin modificar la plantilla genérica original.
6. Opcionalmente, para verificar la conexión con Gemini desde consola sin levantar el frontend, ejecutar la prueba manual de humo (separada de la suite de `pytest`):

```bash
python backend/scripts/smoke_test_gemini_us13.py
```

#### 4. Qué hacer cuando se agota la cuota gratuita (`429`) o falla el proveedor

- Si se alcanza el límite de solicitudes por minuto/día del Free Tier (`HTTP 429`) o si `GEMINI_API_KEY` no está configurada (`HTTP 503`), el sistema **no oculta el error ni cambia silenciosamente** de proveedor: informa el motivo en pantalla.
- El entrenador puede:
  1. Esperar unos instantes y presionar **Reintentar con proveedor configurado**.
  2. Presionar **Usar adaptador heurístico explícitamente** en la interfaz para generar la propuesta con el motor biomecánico local, o cambiar `AI_PROVIDER=heuristic` en `.env`.
