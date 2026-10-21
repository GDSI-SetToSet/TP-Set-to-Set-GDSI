# Technical Research: Perfil Profesional del Entrenador, Paquetes y Gestión de Cupos

**Feature**: `002-trainer-profile-and-plans`
**Date**: 2026-10-15

## 1. Modelo de Concurrencia y Cálculo de Cupos Disponibles

- **Decisión**: Mantener `max_students: int` configurable en el perfil del entrenador y calcular `active_students_count` dinámicamente como subconsulta sobre relaciones activas (`TrainingRelationship.status == 'ACTIVE'`), o mantener un contador sincronizado transaccionalmente mediante locks de base de datos (`SELECT FOR UPDATE`) al momento de aceptar solicitudes.
- **Razón**: Previene condiciones de carrera (*race conditions*) donde dos alumnos sean aceptados concurrentemente superando el cupo límite de 100 o el tope configurado.
- **Alternativas consideradas**:
  - Solo contar en memoria sin transacción: Riesgo de sobrecupo bajo solicitudes concurrentes.

## 2. Regla de Bloqueo por Cupos Agotados (Alternativa A)

- **Decisión**: Cuando `active_students_count >= max_students`:
  - En la búsqueda/perfil público se expone `has_available_quota: false` y badge "Sin cupos disponibles".
  - Nuevas solicitudes directas son rechazadas en backend con error `409 Conflict`.
  - Las solicitudes pendientes previas se mantienen en la bandeja con flag `can_be_accepted: false`. La acción `POST /requests/{id}/accept` valida `active_students_count < max_students` a nivel de servicio del backend devolviendo error descriptivo si está en el tope.
- **Razón**: Cumple estrictamente con la decisión funcional confirmada por el usuario, evitando pérdida de solicitudes históricas pero impidiendo compromisos operativos no deseados por el entrenador.

## 3. Manejo de Tarifas y Monedas

- **Decisión**: Almacenar importes en enteros o decimales precisos (`Numeric(10, 2)` o enteros en centavos), con campo `currency: str = "ARS"` por defecto.
- **Razón**: Permite soporte para pesos argentinos sin imprecisión de punto flotante IEEE 754, garantizando que el rango de 0 a 1.000.000 ARS sea validado limpiamente con Pydantic.
