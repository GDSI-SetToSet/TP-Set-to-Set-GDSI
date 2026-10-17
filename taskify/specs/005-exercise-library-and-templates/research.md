# Technical Research: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15

## 1. Validación de URLs de Plataformas Externas Soportadas (Principio V, US-12)

- **Decisión**: Implementar validación en backend vía expresiones regulares para las tres plataformas autorizadas, normalizando las URLs para su consumo en iframes embebidos:
  - **YouTube**:
    - Patrón: `^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})`
    - Normalización a URL embebida: `https://www.youtube-nocookie.com/embed/{video_id}`
  - **Vimeo**:
    - Patrón: `^(https?://)?(www\.)?(vimeo\.com/|player\.vimeo\.com/video/)(\d+)`
    - Normalización a URL embebida: `https://player.vimeo.com/video/{video_id}`
  - **Google Drive**:
    - Patrón: `^(https?://)?drive\.google\.com/file/d/([a-zA-Z0-9_-]+)(/.*)?$`
    - Normalización a URL embebida: `https://drive.google.com/file/d/{file_id}/preview`
- **Razón**: Asegura que cualquier URL ingresada sea válida y reproducible dentro de la aplicación sin abrir ventanas externas ni descargar archivos de video al servidor, cumpliendo el Principio V.
- **Alternativas consideradas**:
  - Aceptar cualquier URL HTTP arbitraria: Riesgo de enlaces rotos, páginas maliciosas o enlaces a descargas directas no compatibles con el reproductor embebido.

## 2. Modelado de Ejercicios del Sistema vs. Ejercicios del Entrenador

- **Decisión**: Una única tabla `exercises` con columna nullable `trainer_id: UUID | None` y boolean `is_system: bool`.
  - Si `trainer_id is None` e `is_system is True`: es un ejercicio base provisto por la plataforma (visible para todos).
  - Si `trainer_id` está seteado: es un ejercicio personalizado creado por ese entrenador (visible para él y sus alumnos asignados).
- **Razón**: Permite consultas unificadas en la biblioteca con un simple filtro `WHERE is_system = TRUE OR trainer_id = :current_trainer_id`.
