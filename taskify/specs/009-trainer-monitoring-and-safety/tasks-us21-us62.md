---
description: "Lista de tareas de US-21 (spec 009) y US-62 (spec 008)"
---

# Tasks: US-21 — Canal de mensajes + US-62 — Consultas técnicas

**Entrada**: `spec.md` (Sesión 2026-11-16 — US-21), `../008-workout-feedback-and-communication/spec.md` (Session 2026-11-16 — US-62), `plan-us21-us62.md`, `data-model-us21-us62.md`, `contracts/messaging-api.yaml`

**Alcance**: US-21 y US-62 en un PR hacia `sprint6`, con commits de documentación, backend y frontend. **Pruebas**: obligatorias (Principio VI).

## Fase 1: Preparación

- [X] T001 Crear la rama `feature/us-21-62-messaging` desde `sprint6`. Revisar `backend/tests/test_trainer_student_api.py` (`register_and_login`, `create_relationship`) para reutilizarlos en las pruebas.

## Fase 2: US-21 (P1) — Canal de mensajes

**Prueba independiente**: `pytest backend/tests/test_us21_conversations_api.py` y pasos 1–5 de la verificación manual.

- [X] T002 [US21] Crear `backend/src/models/conversation.py` con `ConversationMessage` y `TechnicalNote` según `data-model-us21-us62.md` (constraints, índices, FKs) y registrarlos en `backend/src/models/__init__.py` y en los imports de `backend/tests/conftest.py`.
- [X] T003 [P] [US21] Definir en `backend/src/schemas/conversation.py` `MessageCreate` (cuerpo 1–2000 sin espacios sobrantes, mensaje "Escribí un mensaje (hasta 2000 caracteres)."), `ConversationSummary`, `MessageView`, `ConversationDetail` y los esquemas de US-62.
- [X] T004 [US21] Implementar en `backend/src/services/conversation_service.py`: resolución del vínculo para el usuario (trainer o student; 404 si no es parte), `list_conversations` (activos + terminados con mensajes, no leídos, último mensaje, orden por último mensaje), `get_conversation` (historial cronológico), `send_message` (solo vínculo `ACTIVE` → 409; respuestas a consultas solo del entrenador → 403; `reply_to` debe ser `TECHNICAL_QUERY` del mismo vínculo → 422; `pin_as_technical_note` solo con `reply_to` → 422 y crea `TechnicalNote`), `mark_read` (mensajes recibidos + notificación `NEW_MESSAGE`) y la notificación agrupada `NEW_MESSAGE`.
- [X] T005 [US21] Crear `backend/src/api/v1/conversations.py` con `GET /conversations`, `GET|POST /conversations/{id}/messages`, `POST /conversations/{id}/read` (204) y registrarlo en `backend/src/main.py`.
- [X] T006 [US21] Escribir `backend/tests/test_us21_conversations_api.py`: escenario 1 (ambas partes abren la conversación), 2 (notificación agrupada que se actualiza y se marca leída al abrir), 3 (historial completo en orden, de ambos lados), 4 (vínculo `TERMINATED` → 409 para las dos partes, historial legible), validación del cuerpo (vacío, solo espacios, > 2000), tercero → 404, sin token → 401, alumno con dos entrenadores ve dos conversaciones.
- [X] T007 [P] [US21] Crear `frontend/src/types/conversation.ts` y `frontend/src/services/conversationService.ts`.
- [X] T008 [US21] Crear `frontend/src/components/ConversationThread.tsx` (historial con `role="log"`, composer con contador, actualización cada 10 s y al volver a la pestaña, marca de leído al abrir, estado de solo lectura con vínculo terminado) y `frontend/src/pages/MessagesPage.tsx` (lista de conversaciones con no leídos + hilo seleccionado por `?relationshipId=`; en celular, una vista a la vez).
- [X] T009 [US21] Rutas `trainerMessages: '/entrenador/mensajes'` y `studentMessages: '/alumno/mensajes'` en `frontend/src/constants/routes.ts` y `frontend/src/App.tsx`; tarjeta "Mensajes" en `frontend/src/pages/HomePage.tsx` para ambos roles; botón "Enviar mensaje" en `frontend/src/components/ActivePlanCard.tsx` y `frontend/src/components/TrainerStudentDetail.tsx`; `NEW_MESSAGE` en `trainerNotificationPath` y nuevo `studentNotificationPath` usado por `NotificationBell`, `HomePage` y `StudentActivePlansPage`; documentar las rutas en `README.md`.
- [X] T010 [P] [US21] Estilos responsivos en `frontend/src/styles/messages.css` (burbujas propias y ajenas con contraste ≥ 4.5:1, controles ≥ 44 px).

## Fase 3: US-62 (P2) — Consultas técnicas

**Prueba independiente**: `pytest backend/tests/test_us62_technical_queries_api.py` y pasos 6–10 de la verificación manual.

- [X] T011 [US62] Implementar en `backend/src/services/technical_query_service.py`: `create_query` (solo alumno → 403; vínculo activo → 409; ejercicio existente → 422; `session_id` propio del vínculo → 422; `set_number` 1–50; notificación `TECHNICAL_QUERY` al entrenador), `pending_queries_by_student` (solo vínculos activos, consultas sin respuesta, agrupadas por alumno), `exercise_threads` (consultas del ejercicio con sus respuestas) y `list_pending_notes` / `acknowledge_note` (idempotente; 404 si no es del alumno).
- [X] T012 [US62] Exponer `POST /conversations/{id}/technical-queries`, `GET /conversations/{id}/exercises/{exercise_id}/technical-queries`, `GET /trainers/me/technical-queries`, `GET /students/me/technical-notes` y `POST /students/me/technical-notes/{id}/acknowledge` en `backend/src/api/v1/conversations.py`.
- [X] T013 [US62] Escribir `backend/tests/test_us62_technical_queries_api.py`: escenario 1 (consulta con ejercicio, sesión y serie; aparece en el chat como tarjeta), 2 (notificación y bandeja agrupada por alumno; desaparece al responder), 3 (respuesta fijada → nota pendiente; "Entendido" la quita; idempotencia), 4 (historial por ejercicio para las dos partes), entrenador no puede crear consultas, alumno no puede responder, ejercicio inexistente, sesión ajena, vínculo terminado, tercero → 404.
- [X] T014 [US62] Crear `frontend/src/pages/TrainerTechnicalQueriesPage.tsx` (`/entrenador/consultas`: grupos por alumno, respuesta inline con "Fijar como nota técnica", enlace al chat) y la tarjeta de consulta en `ConversationThread` (ejercicio, serie, estado respondida/pendiente; el entrenador responde desde el chat). Tarjeta "Consultas técnicas" en la home del entrenador; `TECHNICAL_QUERY` en `trainerNotificationPath`.
- [X] T015 [US62] Crear `frontend/src/components/ExerciseQueriesPanel.tsx` (historial del ejercicio + formulario de consulta con serie opcional) y `frontend/src/components/TechnicalNoteNotice.tsx`; integrarlos en la tarjeta del ejercicio de `frontend/src/pages/StudentRoutinesPage.tsx`: el panel en la rutina y en la sesión; la nota bloquea "Iniciar serie" en modo sesión hasta "Entendido".

## Fase 4: Verificación

- [X] T016 `ruff check backend`, `pytest --cov=backend/src` (≥ 90 %), `npm run build`.
- [X] T017 Recorrido manual en el navegador con la demo (entrenador y alumno) de los escenarios de ambas stories, incluida la vista de celular.
- [X] T018 Commits (documentación, backend, frontend) y PR hacia `sprint6`.

## Verificación manual

1. Entrenador → detalle del alumno → "Enviar mensaje": abre la conversación (US-21 esc. 1).
2. Alumno → "Mis entrenadores" → "Enviar mensaje": misma conversación (esc. 1).
3. El entrenador manda 3 mensajes: el alumno ve **una** notificación "3 mensajes nuevos"; al abrir, se marca leída (esc. 2).
4. Con la conversación abierta en las dos sesiones, los mensajes nuevos aparecen sin recargar en ≤ 10 s (esc. 3).
5. Vínculo terminado: el composer no se muestra y la API responde 409 (esc. 4).
6. Alumno en la sesión → ejercicio → "Consultar a mi entrenador" con la serie: la consulta aparece como tarjeta en el chat (US-62 esc. 1).
7. Entrenador: notificación y bandeja "Consultas técnicas" agrupada por alumno (esc. 2).
8. El entrenador responde fijando la nota: desaparece de la bandeja (esc. 2 y 3).
9. Alumno inicia la sesión: el ejercicio muestra la nota y pide "Entendido" antes de "Iniciar serie"; después ya no bloquea (esc. 3).
10. El historial del ejercicio muestra consulta y respuesta para las dos partes (esc. 4).
