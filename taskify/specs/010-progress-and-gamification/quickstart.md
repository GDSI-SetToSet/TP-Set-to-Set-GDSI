# Quickstart de validación: US-65

## Prerrequisitos
- Backend: `pip install -r backend/requirements.txt`; frontend: `cd frontend && npm ci`.
- Datos: un alumno con vínculo activo y series registradas (usar el flujo de US-57 o fixtures de `backend/tests`).

## Automatizado
```bash
pytest backend/tests/test_us65_student_progress_api.py   # message_key, récords, constancia, próxima sesión, filtros, 401/403/422
ruff check backend && pytest --cov=backend/src           # cobertura ≥ 90 %
cd frontend && npm run build && npm test
```
Esperado: todo verde.

## Manual (escenarios de aceptación de la spec)
1. Alumno → "Mi evolución" (`/alumno/evolucion`): tres tarjetas de resumen y la lista de ejercicios con su frase; período por defecto 12 semanas (escenario 1).
2. Tocar un ejercicio: gráfico con récords destacados y línea punteada del objetivo.
3. "¿Estoy siendo constante?": barras por semana; la semana en curso punteada con "En curso: x de y"; una semana sin sesiones queda vacía y sin alerta (escenarios 2 y 3).
4. Cambiar el período y filtrar por grupo muscular (escenario 4).
5. "¿Qué logré?": récords con "(antes …)"; la primera carga de un ejercicio no aparece (escenario 5).
6. "¿Qué me toca ahora?": la última vez frente a lo programado, con la marca "Ajustado por tu entrenador" si corresponde (escenario 6).
7. Alumno sin sesiones, con una sola o sin rutina: mensaje específico en cada caso (escenario 7). Ninguna pantalla muestra "estancado", "bajó" ni porcentajes.
8. Con un token de entrenador, `GET /api/v1/students/me/progress` → 403 `application/problem+json`.

Contrato: [contracts/student-progress-api.yaml](./contracts/student-progress-api.yaml). Modelo: [data-model.md](./data-model.md).
