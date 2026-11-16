# Data Model: US-21 + US-62

**Plan**: [plan-us21-us62.md](./plan-us21-us62.md)

La conversación es el `TrainingRelationship` (una por vínculo). No se crea tabla de conversaciones.

## `conversation_messages` (modelo `ConversationMessage`)

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | `String(36)` PK | no | |
| `relationship_id` | FK `training_relationships.id` `ON DELETE CASCADE` | no | indexada junto con `created_at` |
| `sender_user_id` | FK `users.id` `ON DELETE CASCADE` | no | |
| `sender_role` | `String(16)` | no | `CHECK IN ('TRAINER','STUDENT')` |
| `kind` | `String(24)` | no | `CHECK IN ('TEXT','TECHNICAL_QUERY')` |
| `body` | `Text` | no | 1–2000 caracteres (validado en el esquema) |
| `exercise_id` | FK `exercises.id` `ON DELETE SET NULL` | sí | solo consultas |
| `exercise_name` | `String(150)` | sí | copia del nombre: la tarjeta sobrevive si el ejercicio se borra |
| `session_id` | `String(36)` | sí | sesión desde la que se consultó (opcional) |
| `set_number` | `Integer` | sí | serie ejecutada (opcional, 1–50) |
| `reply_to_message_id` | FK `conversation_messages.id` `ON DELETE CASCADE` | sí | respuesta del entrenador a una consulta |
| `created_at` | `DateTime(tz)` | no | UTC |
| `read_at` | `DateTime(tz)` | sí | cuándo lo leyó el destinatario |

Constraints: `ck_conversation_messages_query_exercise`: `kind <> 'TECHNICAL_QUERY' OR exercise_name IS NOT NULL`; `ck_conversation_messages_reply_kind`: `reply_to_message_id IS NULL OR kind = 'TEXT'`. Índice `ix_conversation_messages_relationship_created (relationship_id, created_at)` y `ix_conversation_messages_reply_to (reply_to_message_id)`.

Una consulta está **pendiente** si no existe ningún mensaje con `reply_to_message_id` igual a su `id`.

## `technical_notes` (modelo `TechnicalNote`)

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | `String(36)` PK | no | |
| `relationship_id` | FK `training_relationships.id` `ON DELETE CASCADE` | no | indexada |
| `message_id` | FK `conversation_messages.id` `ON DELETE CASCADE` | no | `UNIQUE`; la respuesta fijada |
| `exercise_id` | FK `exercises.id` `ON DELETE SET NULL` | sí | |
| `exercise_name` | `String(150)` | no | |
| `created_at` | `DateTime(tz)` | no | |
| `acknowledged_at` | `DateTime(tz)` | sí | "Entendido" del alumno |
| `acknowledged_session_id` | `String(36)` | sí | sesión en la que lo confirmó |

Pendiente = `acknowledged_at IS NULL` y vínculo `ACTIVE`.

## Notificaciones (tabla existente `notifications`)

| Tipo | Destinatario | `related_entity_type` / `related_entity_id` | Regla |
|---|---|---|---|
| `NEW_MESSAGE` | la otra parte | `TrainingRelationship` / id del vínculo | Si ya hay una sin leer de ese vínculo para ese destinatario, se actualiza (título, texto con la cantidad de no leídos y `created_at`). |
| `TECHNICAL_QUERY` | entrenador | `ConversationMessage` / id de la consulta | Siempre una nueva; `related_student_id` = alumno. |

Abrir la conversación (`POST .../read`) marca como leídos los mensajes recibidos y la notificación `NEW_MESSAGE` de ese vínculo.

## DTOs

- `ConversationSummary`: `relationship_id`, `status`, `can_send`, `counterpart_name`, `counterpart_role`, `trainer_id`, `student_id`, `plan_title`, `unread_count`, `last_message` (`body`, `created_at`, `is_mine`, `kind`) o `null`.
- `MessageView`: `id`, `kind`, `body`, `sender_role`, `sender_name`, `is_mine`, `created_at`, `read_at`, `exercise` (`id`, `name`) o `null`, `session_id`, `set_number`, `reply_to_message_id`, `is_answered` (consultas), `technical_note` (`id`, `acknowledged_at`) o `null` (respuestas fijadas).
- `ConversationDetail`: `conversation` (`ConversationSummary`) + `messages` (orden cronológico).
- `PendingQueriesGroup`: `student_id`, `student_name`, `relationship_id`, `queries` (`MessageView`, más antigua primero).
- `ExerciseQueryThread`: `query` (`MessageView`) + `replies` (`MessageView[]`).
- `TechnicalNoteView`: `id`, `relationship_id`, `exercise_id`, `exercise_name`, `body`, `trainer_name`, `created_at`, `acknowledged_at`.
