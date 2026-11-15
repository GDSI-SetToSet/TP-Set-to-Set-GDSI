# Quickstart de validación: US-65

## Prerrequisitos
- Backend: `pip install -r backend/requirements.txt`; frontend: `cd frontend && npm ci`.
- Datos: un alumno con vínculo activo y series registradas (usar el flujo de US-57 o fixtures de `backend/tests`).

## Automatizado
```bash
pytest backend/tests/test_us65_student_progress_api.py   # reglas de PR, volumen, semanas en cero, filtros, 401/403/422
ruff check backend && pytest --cov=backend/src           # cobertura ≥ 90 %
cd frontend && npm run build
```
Esperado: todo verde.

## Manual (escenarios de aceptación de la spec)
1. Iniciar sesión como alumno → "Mi evolución" (`/alumno/evolucion`): gráfico de carga del ejercicio, rango por defecto 12 semanas (escenario 1, FR-001c).
2. Vista semanal: kilaje por semana y comparación de la semana actual con las anteriores (escenario 2).
3. Alumno con una semana sin series: esa semana aparece en 0 y no altera las demás (escenario 3).
4. Filtrar por ejercicio, grupo muscular y rango de fechas (escenario 4).
5. Historial de PRs en orden cronológico con fecha; una serie con el mismo peso que el máximo previo **no** aparece (escenario 5, FR-001a).
6. Menos de 2 sesiones en un ejercicio: estado informativo en lugar del gráfico (edge case).
7. Con un token de entrenador, `GET /api/v1/students/me/progress` → 403 `application/problem+json`.

Contrato: [contracts/student-progress-api.yaml](./contracts/student-progress-api.yaml). Modelo: [data-model.md](./data-model.md).
