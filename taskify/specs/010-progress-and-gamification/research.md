# Investigación: US-65

> **Rediseño (T020–T029):** este documento describe la versión inicial (volumen semanal, PR por mayor peso, filtros de fecha). Vigente: `spec.md` (FR-001 a FR-002), `data-model.md` y `contracts/`.

## D1 — Historial de PRs derivado de las series, no de `PersonalRecord`
- **Decisión** (consulta acotada solo por `student_id`, sin filtrar por vínculo ni sesión finalizada, para que el historial sobreviva a un cambio de entrenador): calcular el historial recorriendo los `WorkoutSetLog` con peso > 0 del alumno, por ejercicio y en orden de `recorded_at`; una serie es PR si su peso supera **estrictamente** el máximo acumulado previo del mismo ejercicio. La primera serie con peso de un ejercicio es el PR inicial (`is_initial = true`, coherente con `is_initial_pr` de US-59).
- **Rationale**: `PersonalRecord` tiene unicidad (alumno, ejercicio) y se sobrescribe, así que solo conserva el último récord; la spec pide lista cronológica con fecha de cada PR. Derivar evita migración y el caso de logs borrados (el delete de US-59 ya recalcula el vigente; el historial derivado se corrige solo).
- **Alternativas**: tabla `personal_record_history` (migración + backfill + doble escritura: descartada); leer solo `PersonalRecord` (pierde el historial).
- **Orden**: ascendente por fecha ("cronológicamente", escenario 5).
- **Empates**: mismo peso que el máximo previo no es PR; si dos series de una misma sesión empatan en `recorded_at`, desempata `set_number`.

## D2 — "Serie de trabajo completada"
- `WorkoutSetLog` no tiene bandera de calentamiento ni de "completada": un log existe solo si la serie se registró. Reglas separadas: **PR y puntos de carga** cuentan toda serie registrada con `weight_kg > 0` (FR-001a: sin importar las repeticiones; coincide con US-59, que ya notifica un PR aunque las reps sean "al fallo"); **volumen** exige además `reps_completed` numérico, por lo que "45 seg" o "al fallo" no suman kilaje (FR-001b). Por eso `reps` se expone como el texto registrado. Series sin peso se excluyen de todo. Si en el futuro se agrega calentamiento, se filtra en un único punto del servicio.

## D3 — Volumen y semanas
- Volumen semanal = Σ(`weight_kg` × reps). Semana lunes–domingo UTC. Se devuelve **una entrada por semana del rango**, con 0 para semanas sin series (escenario 3). La semana actual se marca `is_partial = true`.
- Comparación: `current_week` frente al promedio de las semanas completas previas del rango y frente a la semana inmediata anterior (`delta_vs_previous_pct`, `null` si la anterior es 0).
- Sin filtrar por sesión finalizada: el volumen cuenta series registradas aunque la sesión siga en curso (el alumno ve su avance al instante).

## D4 — Filtros y rango
- Parámetros opcionales: `exercise_id`, `muscle_group` (`Exercise.target_muscle_group`), `from`/`to` (fechas ISO). Sin ninguno: últimas 12 semanas (FR-001c), incluida la semana actual. Los filtros se combinan con AND. `from > to` → 422 RFC 7807.
- Los PRs se calculan sobre todo el historial (para respetar el máximo previo) y recién después se filtran por rango/ejercicio/grupo.

## D5 — Serie de carga por ejercicio
- Un punto por (ejercicio, día) con la mayor carga del día (más peso; ante igualdad, más repeticiones). La respuesta trae `exercises[]` con sus puntos; el cliente elige cuál graficar (por defecto el primero con más puntos). Si el ejercicio tiene menos de 2 puntos, `has_trend = false` y el cliente muestra el estado informativo (edge case de la spec).

## D6 — Gráficos
- SVG propio con los helpers de `utils/trainingEvolution.mjs`, igual que `EvolutionCharts.tsx` (US-30). Sin librería nueva (YAGNI, tamaño del bundle).

## D7 — Fuera de alcance
- Visibilidad para el entrenador (cubierta por US-30), logros (US-67), racha (US-68), peso corporal / 1RM estimado.
