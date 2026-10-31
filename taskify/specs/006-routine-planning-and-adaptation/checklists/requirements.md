# Requirements Quality Checklist: Generación de Rutina Particular con IA (US-13)

**Purpose**: Verificación de calidad, consistencia y completitud de la especificación de US-13 antes de implementar (Definition of Ready).
**Created**: 2026-10-31
**Feature**: [spec.md](../spec.md)

**Note**: Esta checklist audita exclusivamente la historia US-13 en Spec 006. US-14, US-53, US-54 y US-55 se auditarán cuando corresponda a sus respectivas fases.
**Marker Semantics**: `[x]` indica que el criterio de calidad de especificación fue revisado y aprobado.

## 1. Definición y Cobertura de Historias de Usuario

- [x] CHK001 US-13 tiene prioridad (Media / P2) y estimación explícita en Story Points (5 SP).
- [x] CHK002 Los escenarios de US-13 están redactados estrictamente con la estructura Dado / Cuando / Entonces.
- [x] CHK003 Los escenarios cubren generación adaptada, sustitución/eliminación de incompatibles, supervisión humana obligatoria, aprobación explícita, inmutabilidad de la plantilla base, autorización/privacidad y manejo de fallas de IA.

## 2. Claridad de Reglas de Dominio y Negocio

- [x] CHK004 Los datos del alumno a consumir por la IA están claramente identificados (`fitness_goals`, `personal_motivation`, `birth_date`, `protected_zones`, `health_questionnaire`).
- [x] CHK005 El criterio para identificar ejercicios incompatibles (coincidencia de grupo muscular con zona protegida o contraindicación médica) está explícito.
- [x] CHK006 La IA genera una propuesta en estado 'PENDING_REVIEW' y nunca activa la rutina de manera autónoma (Principio II de la Constitución).
- [x] CHK007 La supervisión humana exige aprobación manual del entrenador antes de que la rutina sea persistida como 'APPROVED' y asignada.
- [x] CHK008 La rutina genérica original no es alterada ni sobrescrita.
- [x] CHK009 El acceso a los datos del alumno y la generación de rutina requieren vínculo activo comprobado en el backend (Principio III de la Constitución).

## 3. Consistencia de Modelos y Contratos

- [x] CHK010 `data-model.md` define `AssignedRoutine`, `AssignedRoutineDay`, `AssignedRoutineBlock` y `AssignedRoutineExercise` con estados `PENDING_REVIEW` y `APPROVED`.
- [x] CHK011 `contracts/routine-adaptation-api.yaml` define los endpoints para listar alumnos activos del entrenador, generar propuesta con IA, consultar propuesta y aprobarla.
- [x] CHK012 Todos los errores siguen el estándar RFC 7807 (`application/problem+json`).
- [x] CHK013 Principio de caja negra respetado en la especificación de negocio (sin atar a tipos SQL concretos).
- [x] CHK014 Restricciones de alcance explícitas: US-14 (edición manual de rutinas) y el resto de historias del Sprint 3 quedan excluidas de esta implementación.
