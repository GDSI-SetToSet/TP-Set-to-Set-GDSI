# Technical Research: Perfil del Alumno, Cuestionario de Salud y Apto Médico

**Feature**: `003-student-profile-and-health`
**Date**: 2026-10-15

## 1. Estrategia de Almacenamiento Protegido para Aptos Médicos (US-43, Principio III)

- **Decisión**: Implementar una interfaz desacoplada `StorageService` con un adaptador local de almacenamiento privado (`LocalStorageProvider`) para el MVP inicial, guardando los binarios en un directorio seguro del servidor fuera de la raíz web pública (ej. `var/data/medical_clearances/`), y sirviendo el contenido exclusivamente a través de un endpoint autenticado (`GET /api/v1/students/{id}/medical-clearance/download`) con validación de RBAC por cada solicitud.
- **Razón**: Cumple estrictamente con el Principio III de la Constitución (tecnología neutral, validación en backend en cada petición, sin acceso público ni URLs expuestas). Permite migrar en el futuro a almacenamiento en la nube (S3 / Google Cloud Storage) implementando `S3StorageProvider` sin alterar la lógica de negocio ni los controladores.
- **Alternativas consideradas**:
  - URLs prefirmadas directas a bucket público/privado: Requiere configuración e infraestructura cloud externa en el MVP; además, si la URL se comparte o filtra durante su ventana de validez, permite accesos no autorizados sin pasar por la validación de relación activa en el backend.
  - Almacenar archivos en base de datos como BLOB: Sobrecarga el tamaño de la base de datos relacional y degrada el rendimiento de backups.

## 2. Matriz de Autorización del Lado del Servidor (RBAC por Relación)

- **Decisión**: Para consultar el cuestionario de salud, lesiones y certificados médicos del alumno `X`:
  - Si el usuario es el propio alumno `X`: **PERMITIDO**.
  - Si el usuario es un entrenador `Y`:
    - Se consulta la existencia de un `TrainingRequest` pendiente de resolución entre `X` e `Y`: **PERMITIDO** (solo lectura de antecedentes para evaluar la postulación).
    - Se consulta la existencia de una relación activa (`TrainingRelationship.status == 'ACTIVE'`): **PERMITIDO**.
    - Si la relación está finalizada (`TERMINATED`), cancelada o inexistente: **DENEGADO (HTTP 403 Forbidden)** de manera inmediata (US-35 y Principio III).
- **Razón**: Garantiza cero fugas de datos sensibles en endpoints de salud sin delegar la seguridad en el cliente.

## 3. Manejo Histórico de Certificados Médicos (Alternativa A)

- **Decisión**: Modelo acumulativo con clave foránea a `student_id`. Al subir un nuevo certificado:
  - En una transacción atómica, todos los certificados previos del alumno pasan a estado `status = 'ARCHIVED'`.
  - El nuevo certificado se inserta con `status = 'CURRENT'`.
- **Razón**: Permite al entrenador auditar evolutivamente los aptos previos manteniendo una referencia clara y única del certificado vigente para habilitar la práctica deportiva.

## 4. Nombre, Teléfono, Onboarding y Catálogo de Objetivos (US-39, US-40; clarificaciones 2026-10-20)

- **Decisión**: `first_name` y `last_name` separados (el `full_name` del código actual se migra: columnas nuevas, datos existentes se parten por el primer espacio o se dejan en `first_name`). Teléfono validado con `^\+?[0-9]{10,15}$`. Objetivos: enum cerrado de 6 valores (`fuerza, hipertrofia, resistencia, perdida_de_peso, salud_general, movilidad_rehabilitacion`) validado en el schema; guardado como lista JSON. El perfil pasa a `PUBLISHED` solo con nombre, apellido, fecha de nacimiento, teléfono y ≥1 objetivo; la motivación es opcional. Objetivos y motivación se leen con la misma matriz de RBAC de la sección 2 (alumno, o entrenador con solicitud pendiente/relación activa).
- **Razón**: Alinea spec, data-model, contrato y código; un catálogo cerrado simplifica validación y filtrado por el entrenador.
- **Alternativas consideradas**: `full_name` único (rechazado: contradice US-39); objetivos libres u "Otro" (rechazado: texto libre ya cubierto por la motivación); exigir el cuestionario de salud para publicar (rechazado: acopla US-41).

## 5. Cuestionario de Salud: Alcance, Versionado y Bloqueo (US-41; clarificaciones 2026-10-21)

- **Decisión**:
  - El cuestionario es solo de salud; los objetivos se leen del perfil (`/students/{id}/goals`), sin copia propia.
  - Las 5 preguntas Sí/No son obligatorias y sin valor por defecto (`bool` requerido en el schema: una omitida da 422).
  - Cada envío inserta una versión nueva `CURRENT` y archiva la anterior en la misma transacción (mismo patrón que el apto médico, sección 3). Los entrenadores autorizados leen solo la `CURRENT`; `ARCHIVED` no tiene endpoint.
  - `health_questionnaire_completed` es derivado (existe una fila `CURRENT`), no una columna. `has_risk_answers` también es derivado (alguna de las 5 en `true`).
  - Un "Sí" no bloquea al alumno: solo expone `has_risk_answers = true` al entrenador.
  - La validación reutilizable `require_health_questionnaire(db, student_profile)` vive en `student_service` y lanza `StudentProfileError(403)`; las specs 004 (enviar solicitud) y 006 (acceder a rutina) la invocan.
  - La lectura por entrenadores reutiliza `trainer_has_access` (stub de US-40, spec 004) y la matriz de la sección 2.
- **Razón**: Una sola fuente de verdad para objetivos; "no respondió" no puede confundirse con "No" en un dato de seguridad; trazabilidad de lo declarado sin exponerlo al entrenador; la validación única evita duplicar la regla en cada spec.
- **Alternativas consideradas**: objetivos duplicados en el cuestionario (rechazado: dos fuentes que se contradicen); sobrescribir sin historial (rechazado: sin trazabilidad); exigir apto médico ante un "Sí" (rechazado: autodiagnóstico sin criterio médico); columna almacenada para `completed` (rechazada: puede desincronizarse de las versiones).
