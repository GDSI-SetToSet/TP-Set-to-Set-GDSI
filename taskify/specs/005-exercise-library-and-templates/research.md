# Technical Research: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15 (actualizado 2026-10-30 tras `/speckit-clarify`)

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

## 2. Propiedad de los Ejercicios

- **Decisión**: Tabla `exercises` con `trainer_id` obligatorio. Toda consulta filtra por el entrenador autenticado y excluye `deleted_at` con valor.
- **Razón**: La US define una biblioteca personal y no existe una fuente para un catálogo global (Clarificación 2026-10-30).
- **Alternativas consideradas**:
  - Columna `is_system` con `trainer_id` nulo: Descartada; agrega estados y reglas de edición sin una US que los requiera.

## 3. Estructura y Edición de Rutinas

- **Decisión**: Tablas separadas para días, bloques y ejercicios con `cascade="all, delete-orphan"`. La edición (`PUT`) reemplaza la estructura completa, y `order_index` se deriva de la posición en el arreglo.
- **Razón**: El formulario envía la rutina completa, y reemplazar evita conciliar altas, bajas y reordenamientos.
- **Alternativas consideradas**:
  - Columna JSON con la estructura: Descartada; impide la clave foránea a `Exercise` y la consulta de rutinas que usan un ejercicio (regla "Sin materiales").

## 4. Acceso de Alumnos a Rutinas (Principio III)

- **Decisión**: Endpoints propios de solo lectura bajo `/api/v1/students/me/routine-templates`, filtrados por `TrainingRelationship.status == "ACTIVE"`. Una rutina ajena responde 404.
- **Razón**: Separa el rol en la URL, valida el vínculo en cada petición y revoca el acceso al terminar el vínculo sin pasos adicionales.

## 5. Esquema de Base de Datos

- **Decisión**: Las tablas nuevas se crean con `Base.metadata.create_all`, igual que el resto del proyecto. La marca y la categoría se incluyen en el alta de `exercises` (US-08), aunque la regla "Sin materiales" llegue con US-09.
- **Razón**: El proyecto no usa migraciones, y `create_all` no agrega columnas a tablas existentes.
