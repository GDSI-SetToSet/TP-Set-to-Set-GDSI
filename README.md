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

## Desarrollo local: autenticación

La primera funcionalidad implementada cubre el registro de entrenadores y alumnos, el inicio y cierre de sesión y la protección de la pantalla interna.

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn backend.src.main:app --reload
```

La API queda disponible en `http://localhost:8000`. La documentación interactiva está en `http://localhost:8000/docs`. Para producción, configurá `APP_ENV=production` y `JWT_SECRET` con un valor aleatorio de al menos 32 caracteres. La API no inicia en producción si falta el secreto o es demasiado corto.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrí `http://localhost:5173`. Se puede crear una cuenta como alumno o entrenador; el registro inicia la sesión y muestra la pantalla correspondiente al rol. Las rutas internas requieren una sesión válida.

### Pruebas

Desde la raíz del repositorio:

```bash
PYTHONPATH=. pytest backend/tests --cov=backend/src --cov-report=term-missing
```

