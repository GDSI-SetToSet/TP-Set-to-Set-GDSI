# Set to Set

**Plataforma de gestión y seguimiento del entrenamiento físico**

## Descripción

Set to Set es una plataforma que busca conectar a entrenadores personales con personas que desean entrenar, facilitando la planificación de rutinas, el seguimiento del progreso físico y la comunicación entre ambas partes.

El proyecto propone centralizar en un mismo lugar las herramientas necesarias para organizar el entrenamiento, registrar resultados y gestionar la relación entre entrenadores y alumnos.

## Integrantes

- Arroquy Facundo 109743 faarroquy@fi.uba.ar
- Gualdi Martina 110513 martugualdi@gmail.com
- Franco Agustín Finocchi Martín 110715 ffinocchi@fi.uba.ar
- Bruno Pezman 110457 bpezman@fi.uba.ar
- Axel Zielonka 110310 azielonka@fi.uba.ar

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
- **Entrenador (`002` / `004`):** `/entrenador/inicio`, `/entrenador/perfil`, `/entrenador/paquetes`, `/entrenador/solicitudes`, `/entrenador/solicitudes/:requestId`
- **Alumno (`003` / `004`):** `/alumno/inicio`, `/alumno/perfil`, `/alumno/salud`, `/alumno/zonas-a-proteger`, `/alumno/apto-medico`, `/alumno/buscar-entrenadores`, `/entrenadores/:trainerId`, `/entrenadores/:trainerId/solicitar`, `/alumno/mis-solicitudes`, `/alumno/mis-entrenamientos`

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
