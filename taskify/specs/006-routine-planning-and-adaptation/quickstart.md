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
