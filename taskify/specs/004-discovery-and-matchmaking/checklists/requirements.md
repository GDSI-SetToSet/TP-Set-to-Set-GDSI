# Requirements Quality Checklist: Discovery and Matchmaking (US-06, US-07, US-44, US-46..US-49)

**Purpose**: Verificación de calidad, consistencia y completitud de especificación para el módulo de búsqueda y vinculación (Discovery & Matchmaking).
**Created**: 2026-10-24
**Feature**: [spec.md](../spec.md)

**Note**: Esta checklist es un artefacto de revisión de calidad de requerimientos propiedad del revisor.
**Review Ownership**: Este checklist audita que la especificación cumpla con la Constitución y las reglas de Spec Kit.
**Marker Semantics**: `[x]` indica que el criterio de calidad de especificación fue revisado y aprobado. No indica que la implementación de código esté terminada.

## 1. Definición y Cobertura de Historias de Usuario

- [x] CHK001 Todas las historias de usuario (US-44, US-46, US-47, US-48, US-06, US-07, US-49) tienen prioridad y estimación explícitas en Story Points.
- [x] CHK002 Los escenarios de aceptación de US-06 y US-07 están redactados con la estructura formal Dado / Cuando / Entonces (DCE).
- [x] CHK003 Los escenarios de US-06 cubren listado de pendientes, contador, llegada de nueva solicitud, evaluación detallada y bandeja con cupos agotados.
- [x] CHK004 Los escenarios de US-07 cubren aceptación exitosa, rechazo con motivo opcional, bloqueo 409 con cupo completo, revocación 403 e idempotencia ante solicitudes resueltas.

## 2. Claridad de Reglas de Dominio y Negocio

- [x] CHK005 Se especifica que la bandeja de pendientes muestra solicitudes `PENDING` sin corte rígido por mes calendario (Q1 resuelta).
- [x] CHK006 Se especifica que el cupo del entrenador (`max_students`) es concurrente sobre vínculos `TrainingRelationship` activos y no se reinicia por calendario (Q2 resuelta).
- [x] CHK007 Se ratifica la Decisión Alternativa A para cupos llenos (solicitudes preexistentes visibles, botón Aceptar deshabilitado, rechazo habilitado, y bloqueo 409) (Q3 resuelta).
- [x] CHK008 Se documenta la estrategia de actualización de bandeja por carga y refresco manual sin dependencias en tiempo real para el MVP (Q4 resuelta).
- [x] CHK009 Se delimita la autorización de salud temporal durante `PENDING` y su revocación inmediata en `REJECTED`/`CANCELLED` (Q5 resuelta, Principio Constitucional III).
- [x] CHK010 Se delimita que la pantalla de listado general de alumnos activos pertenece a US-18 (spec 009), evitando duplicación en US-07 (Q6 resuelta).
- [x] CHK011 Se documenta explícitamente la discrepancia y resolución de `rejection_reason` opcional entre OpenAPI y US-48 (Q7 resuelta).
- [x] CHK012 Se establece la garantía de atomicidad y control de concurrencia con bloqueo pesimista e idempotencia (Q8 resuelta).

## 3. Consistencia de Modelos y Contratos

- [x] CHK013 Las entidades `TrainingRequest` y `TrainingRelationship` en `data-model.md` guardan coherencia con la no retroactividad de precios (FR-010).
- [x] CHK014 El contrato `contracts/matchmaking-api.yaml` incluye endpoints para detalle (`GET /requests/{id}`), aceptación (`POST /requests/{id}/accept`) y rechazo (`POST /requests/{id}/reject`).
- [x] CHK015 Los errores devueltos (403, 404, 409) se definen conforme a RFC 7807 (`application/problem+json`).
- [x] CHK016 No se introducen dependencias huérfanas ni requerimientos no aprobados (como FR-008 de foto de perfil).
