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
