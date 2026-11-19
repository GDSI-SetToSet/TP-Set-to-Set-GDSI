# Plan de implementación: US-65 — Evolución de cargas, volumen semanal y PRs

> **Rediseño (T020–T029):** este documento describe la versión inicial (volumen semanal, PR por mayor peso, filtros de fecha). Vigente: `spec.md` (FR-001 a FR-002), `data-model.md` y `contracts/`.

**Branch**: `010-progress-and-gamification` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

**Alcance**: solo US-65. US-67 (logros) y US-68 (racha) quedan fuera de este plan (Principio VII: una story por PR).

## Resumen

Pantalla del alumno "Mi evolución" con tres bloques: carga por ejercicio en el tiempo, volumen semanal (con comparación de la semana actual contra las anteriores) e historial cronológico de PRs. Un **único endpoint de solo lectura** `GET /api/v1/students/me/progress` calcula todo en el servidor a partir de `WorkoutSetLog` existentes: sin tablas ni migraciones nuevas. Reglas aclaradas (spec, sesión 2026-11-15): PR = mayor peso en una serie completada, sin importar repeticiones, y se registra solo si supera estrictamente el máximo previo (FR-001a); volumen = Σ(kg × reps) de series con peso (FR-001b); rango por defecto 12 semanas (FR-001c).

## Reutilización (no duplicar)

- `training_evolution_service.py` (US-30, vista del entrenador): reutilizar `_monday`, y `session_comparison_service._number` para parsear `reps_completed` (cadenas como "45 seg" o "al fallo" no son numéricas y quedan fuera del volumen). No se reutiliza `get_training_evolution` (está atado a vínculo y a otras métricas).
- `student_service.get_or_create_profile` para resolver el alumno autenticado.
- Frontend: `utils/trainingEvolution.mjs` (`niceTicks`, `formatDay`, `formatNumber`, `formatRange`) y el patrón de gráfico SVG propio de `EvolutionCharts.tsx` (sin librería de gráficos nueva).
- La tabla `PersonalRecord` guarda solo el **máximo vigente** por (alumno, ejercicio) y se actualiza en el lugar; no sirve como historial. El historial se **deriva** de `WorkoutSetLog` (ver research.md).

## Contexto técnico

**Lenguaje/Versión**: Python 3.12; TypeScript/React 18; Node.js 20

**Dependencias principales**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Pytest, React Router, Axios (todas existentes)

**Almacenamiento**: modelos existentes; no se crean tablas ni migraciones

**Pruebas**: Pytest (integración + unitarias del cálculo), `npm run build`, Ruff, cobertura ≥ 90 % del pipeline

**Plataforma objetivo**: aplicación web responsiva en servidor Linux

**Tipo de proyecto**: aplicación web existente (FastAPI + React)

**Rendimiento**: SC-001 — render < 500 ms con datos agregados. Una sola solicitud; los logs se leen con una consulta filtrada por alumno y los agregados se calculan en memoria. Si el historial crece, agregar en SQL (`# ponytail:` en el servicio).

**Restricciones**: autorización en el servidor, solo datos propios del alumno autenticado (rol alumno); errores RFC 7807; fechas UTC; semanas lunes–domingo en UTC.

**Escala/Alcance**: un alumno, historial de cientos a pocos miles de series.

## Verificación de la Constitución

| Principio | Estado | Justificación |
|---|---|---|
| I. Accesibilidad | PASS | Responsivo, contraste ≥ 4.5:1, objetivos táctiles ≥ 44×44 px, gráficos SVG con `role="img"` y `aria-label` y tabla/lista textual equivalente; estados vacío/cargando/error con mensajes comprensibles. |
| II. IA con supervisión | N/A | No hay IA ni asignación de rutinas. |
| III. Privacidad de salud | PASS | El endpoint devuelve solo datos del alumno autenticado (sin parámetro `student_id`); validación en backend. Rol entrenador recibe 403. |
| IV. Pagos | N/A | Sin pagos. |
| V. Medios externos | N/A | Sin medios. |
| VI. Verificación continua | PASS | Pruebas de backend (reglas de PR, volumen, semanas en cero, filtros, autorización) y build del frontend. |
| VII. Entrega incremental | PASS | Una story (US-65), un PR hacia `develop`; US-67 y US-68 no se implementan. Depende de US-57/US-59 (registro de series y PRs), ya presentes. |

Re-evaluación post-diseño: sin cambios, PASS.

## Estructura del proyecto

### Documentación

```text
taskify/specs/010-progress-and-gamification/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/student-progress-api.yaml
└── tasks.md   (lo genera /speckit-tasks)
```

### Código fuente

```text
backend/
├── src/
│   ├── api/v1/students.py                  (nueva ruta GET /me/progress)
│   ├── schemas/student_progress.py         (nuevo)
│   └── services/student_progress_service.py (nuevo)
└── tests/test_us65_student_progress_api.py (nuevo)
frontend/
└── src/
    ├── pages/StudentProgressPage.tsx       (nuevo)
    ├── components/StudentProgressCharts.tsx (nuevo; reutiliza utils de gráficos)
    ├── services/studentProgressService.ts  (nuevo)
    ├── types/studentProgress.ts            (nuevo)
    ├── constants/routes.ts                 (studentProgress: '/alumno/evolucion')
    └── App.tsx                             (ruta protegida rol alumno + enlace desde la home del alumno)
```

**Decisión de estructura**: servicio y esquemas propios porque la vista del alumno tiene otras reglas (PR histórico, volumen en kg) y otra autorización que `training_evolution_service`; se comparten solo los helpers puros.

## Seguimiento de complejidad

Sin incumplimientos constitucionales.
