# Technical Research: Búsqueda de Entrenadores, Perfiles Públicos y Solicitudes de Alta

**Feature**: `004-discovery-and-matchmaking`
**Date**: 2026-10-15

## 1. Concurrencia en la Aceptación de Solicitudes y Cupos (US-04, US-07)

- **Decisión**: Utilizar bloqueo pesimista a nivel de fila (`SELECT ... FOR UPDATE` en PostgreSQL) sobre el registro del perfil del entrenador al momento de invocar `POST /requests/{id}/accept`:
  ```python
  trainer = db.query(TrainerProfile).filter_by(id=trainer_id).with_for_update().one()
  if trainer.active_students_count >= trainer.max_students:
      raise QuotaExceededException("Cupo máximo alcanzado; no es posible aceptar nuevos alumnos.")
  trainer.active_students_count += 1
  request.status = RequestStatus.ACCEPTED
  relationship = TrainingRelationship(student_id=request.student_id, trainer_id=trainer.id, plan_id=request.plan_id, status=RelationshipStatus.ACTIVE)
  db.add(relationship)
  db.commit()
  ```
- **Razón**: Garantiza de manera atómica que bajo ninguna circunstancia concurrente se exceda el cupo máximo `max_students` establecido por el entrenador.
- **Alternativas consideradas**:
  - Verificación optimista sin lock: Expuesta a race conditions cuando dos solicitudes son aceptadas en milisegundos idénticos.

## 2. Gestión de Solicitudes Pendientes con Cupo Lleno (Alternativa A)

- **Decisión**: Las solicitudes previas mantienen su estado `PENDING` en la base de datos y se listan en el inbox del entrenador. Sin embargo, en el DTO de respuesta se incluye `can_accept: bool = (trainer.active_students_count < trainer.max_students)`. En la UI, el botón "Aceptar" se deshabilita con tooltip explicativo. Si el entrenador libera un alumno o amplía el cupo, `can_accept` pasa dinámicamente a `true` sin necesidad de reenviar la solicitud.
- **Razón**: Satisface exactamente la decisión de negocio acordada, minimizando fricción y reintentos innecesarios para el alumno.

## 3. Estrategia de Búsqueda y Filtrado (US-44)

- **Decisión**: Filtrado estructurado relacional con índices B-Tree en `specialty`, `monthly_price`, y disponibilidad `(max_students > active_students_count)`.
- **Razón**: Para la escala del MVP (cientos a miles de entrenadores), consultas SQL indexadas en PostgreSQL/SQLite son inmediatas (< 20ms) sin necesidad de motores de búsqueda externos (Elasticsearch/Meilisearch).
