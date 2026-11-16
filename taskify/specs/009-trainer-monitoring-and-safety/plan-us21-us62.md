# Plan de implementación: US-21 (canal de mensajes) + US-62 (consultas técnicas)

**Branch**: `feature/us-21-62-messaging` (desde `sprint6`; PR hacia `sprint6`) | **Date**: 2026-11-16
**Specs**: [009 — US-21](./spec.md) (Sesión 2026-11-16) y [008 — US-62](../008-workout-feedback-and-communication/spec.md) (Session 2026-11-16)

**Alcance**: US-21 (escenarios 1–4) y US-62 (escenarios 1–4) en un solo PR (decisión del equipo, ver *Seguimiento de complejidad*), con commits separados para documentación, backend y frontend. Fuera de alcance: adjuntos, mensajes en tiempo real por WebSocket, edición o borrado de mensajes y la baja de US-35 (el escenario 4 de US-21 se prueba con un vínculo `TERMINATED`).

## Resumen

Una **conversación por vínculo** de entrenamiento: el `TrainingRelationship` es la conversación y no hay tabla de conversaciones. Se guardan los mensajes en `conversation_messages`. La consulta técnica de US-62 es un mensaje de tipo `TECHNICAL_QUERY` con referencia al ejercicio (y opcionalmente a la sesión y la serie), según la Decisión Alternativa B. La respuesta del entrenador es un mensaje que apunta a la consulta (`reply_to_message_id`). Si el entrenador la fija como nota técnica, se crea un registro en `technical_notes`, que el alumno debe confirmar ("Entendido") la próxima vez que inicia ese ejercicio.

Sin WebSockets: la conversación abierta se actualiza cada 10 segundos y al volver a la pestaña. Las notificaciones de mensajes se agrupan por conversación mientras no se lean.

## Reutilización (no duplicar)

- `notification_service.create_notification` y el modelo `Notification` (campana existente de ambos roles); nuevos tipos `NEW_MESSAGE` y `TECHNICAL_QUERY`.
- `trainer_student_service._trainer_profile` y `student_service.get_or_create_profile` / `get_student_profile` para resolver el perfil del usuario.
- `routes.ts`: `trainerNotificationPath` se extiende y se agrega `studentNotificationPath`, que reemplaza la lógica de ruteo hoy duplicada en `NotificationBell`, `HomePage` y `StudentActivePlansPage`.
- Pantalla de sesión del alumno (`StudentRoutinesPage`): la tarjeta del ejercicio ya muestra las notas técnicas de US-52; la nota fijada se muestra en el mismo lugar.
- `useDialogFocus` (patrón de modal accesible) y `errorMessage.getApiErrorInfo`.

## Contexto técnico

**Lenguaje/Versión**: Python 3.12; TypeScript/React 18; Node.js 20
**Dependencias**: existentes (FastAPI, SQLAlchemy 2.0, Pydantic v2, React Router, Axios, lucide-react)
**Almacenamiento**: dos tablas nuevas (`conversation_messages`, `technical_notes`), creadas por `create_all` en `core/migrations.py`; sin cambios en tablas existentes
**Pruebas**: Pytest (API), Ruff, `npm run build` (incluye `tsc -b`), cobertura ≥ 90 %
**Rendimiento**: el historial completo se devuelve en cada consulta (escenario 3). Con decenas o cientos de mensajes por vínculo es aceptable; si crece, paginar por `created_at` (`# ponytail:` en el servicio).
**Restricciones**: solo las dos partes del vínculo leen la conversación (404 para terceros, sin revelar si existe); envío solo con vínculo `ACTIVE` (409); errores RFC 7807; fechas UTC.

## Verificación de la Constitución

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Controles ≥ 44×44 px, contraste ≥ 4.5:1, mensajes con `role="log"` y `aria-live` para los nuevos, composer con etiqueta; la nota técnica se comunica con texto y botón explícito. |
| II. IA | N/A | Sin IA. |
| III. Privacidad | PASS | Autorización por vínculo en el backend en cada petición; un tercero recibe 404. Con el vínculo terminado no se puede enviar. El historial queda de solo lectura para las dos partes (los mensajes no son datos de salud protegidos). |
| IV. Pagos | N/A | Sin pagos. |
| V. Medios | N/A | Sin adjuntos. |
| VI. Verificación | PASS | Pruebas de API para todos los escenarios y casos de autorización; build del frontend. |
| VII. Entrega incremental | EXCEPCIÓN | Un PR con dos stories (ver abajo). Ninguna depende de una story sin mergear. |

## Estructura del proyecto

```text
backend/src/
├── models/conversation.py                 (ConversationMessage, TechnicalNote)
├── schemas/conversation.py
├── services/conversation_service.py       (US-21: lista, historial, envío, lectura, notificaciones)
├── services/technical_query_service.py    (US-62: consultas, bandeja, historial por ejercicio, notas)
└── api/v1/conversations.py                (router nuevo, registrado en main.py)
backend/tests/
├── test_us21_conversations_api.py
└── test_us62_technical_queries_api.py
frontend/src/
├── types/conversation.ts
├── services/conversationService.ts
├── pages/MessagesPage.tsx                 (rutas /entrenador/mensajes y /alumno/mensajes)
├── pages/TrainerTechnicalQueriesPage.tsx  (/entrenador/consultas)
├── components/ConversationThread.tsx      (historial + composer + tarjetas de consulta)
├── components/ExerciseQueriesPanel.tsx    (alumno: historial del ejercicio + nueva consulta)
├── components/TechnicalNoteNotice.tsx     (nota fijada con "Entendido")
├── pages/StudentRoutinesPage.tsx          (panel de consultas y nota en la tarjeta del ejercicio)
├── components/ActivePlanCard.tsx, components/TrainerStudentDetail.tsx (botón "Enviar mensaje")
├── pages/HomePage.tsx, App.tsx, constants/routes.ts, components/NotificationBell.tsx
└── styles/messages.css
```

## Seguimiento de complejidad

| Excepción | Por qué | Alternativa descartada |
|---|---|---|
| US-21 y US-62 en un solo PR (Principio VII). | Decisión del equipo (2026-11-16): US-62 vive dentro del canal de US-21 y se revisan juntas. Se mantiene un commit por story. | PRs encadenados: implicaba desarrollar US-62 sobre una rama sin mergear. |
| El historial completo se devuelve en cada actualización (cada 10 s). | Simplicidad para el MVP; el volumen esperado es bajo. | Paginación incremental por cursor: más compleja de lo necesario hoy. |
