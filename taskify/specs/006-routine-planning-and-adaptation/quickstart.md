# Quickstart: validar US-14

**Prerequisitos**: `pip install -r backend/requirements.txt`; entrenador y alumno con vínculo ACTIVE, rutina genérica asignada.

```bash
pytest backend/tests -k student_routine --cov=backend/src --cov-fail-under=90
ruff check backend && (cd frontend && npm run build)
```

**Escenarios manuales** (ver [contrato](./contracts/student-routine-edit-api.yaml)):
1. Editar ejercicio/series/intensidad → guardar borrador → el alumno sigue viendo la versión vigente → confirmar → el alumno ve la nueva.
2. Agregar ejercicio contraindicado para una zona protegida → `422` con alerta; no se guarda.
3. Rutina "Sin materiales": editar sin alternativa → borrador se guarda, confirmar devuelve `422`.
4. Registrar volumen semanal deseado y ajustar intensidad.
5. Dos pestañas editando → la segunda recibe `409`.
6. Tras confirmar existe una entrada en el registro de cambios (autor, fecha, diferencias).

# Quickstart: validar US-53

**Prerequisitos**: entrenador con vínculo ACTIVE a un alumno con zona protegida (p. ej. "Knee"); ejercicio de la biblioteca con `contraindicated_zones` = ["knee"] incluido en la rutina vigente del alumno; ver [contrato](./contracts/safe-variants-api.yaml).

```bash
pytest backend/tests -k safe_variant --cov=backend/src --cov-fail-under=90
ruff check backend && (cd frontend && npm run build)
```

**Escenarios manuales**:
1. Sin variante: el alumno consulta el ejercicio → `BLOCKED`, `can_skip: true`; el entrenador recibe **una** notificación; consultar de nuevo no genera otra.
2. El entrenador vincula una variante que cubre "knee" → el caso pasa a `RESOLVED`; el alumno consulta → `VARIANT` con video/explicación.
3. Alumno con dos zonas (rodilla y hombro) y una variante que cubre solo una → `BLOCKED` (nueva notificación solo si el caso estaba `RESOLVED`).
4. Quitar la zona protegida del alumno o la variante → la siguiente consulta refleja el cambio sin reiniciar la sesión.
5. Alumno consulta un ejercicio que no está en su rutina → `404`; sin vínculo activo → `403`.
6. En US-14, agregar un ejercicio contraindicado ofrece la variante resuelta en `safe_variant` (ya no `null`).
