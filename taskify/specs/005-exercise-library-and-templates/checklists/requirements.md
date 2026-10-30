# Requirements Quality Checklist: Biblioteca de Ejercicios y Rutinas Genéricas (US-08, US-09)

**Purpose**: Verificación de calidad, consistencia y completitud de la especificación de US-08 y US-09 antes de implementar. US-12 y US-52 se auditan cuando se planifiquen.
**Created**: 2026-10-30
**Feature**: [spec.md](../spec.md)

**Note**: Esta checklist es el control de calidad de la spec mantenido por `/speckit-clarify`.
**Marker Semantics**: `[x]` indica que el criterio de calidad de especificación fue revisado y aprobado. No indica que la implementación de código esté terminada.

## 1. Definición y Cobertura de Historias de Usuario

- [x] CHK001 US-08 y US-09 tienen prioridad y estimación explícitas en Story Points.
- [x] CHK002 Los escenarios de US-08 y US-09 están redactados con la estructura Dado / Cuando / Entonces.
- [x] CHK003 Los escenarios de US-08 cubren alta, datos faltantes, listado con filtro, detalle, edición, baja y aislamiento entre entrenadores.
- [x] CHK004 Los escenarios de US-09 cubren alta, edición, datos faltantes, regla "Sin materiales" y visibilidad para alumnos con y sin vínculo.

## 2. Claridad de Reglas de Dominio y Negocio

- [x] CHK005 Está definida la estructura de la rutina en días, bloques y ejercicios (FR-002 alineado con los escenarios).
- [x] CHK006 "Tipo de ejercicio" está definido como categoría de una lista cerrada.
- [x] CHK007 "Disponible para alumnos" está acotado a vínculo activo, solo lectura y pérdida de acceso al finalizar el vínculo.
- [x] CHK008 La alternativa "Sin materiales" está definida como marca del ejercicio, con el límite frente a US-11 explícito.
- [x] CHK009 La biblioteca está acotada a ejercicios propios, sin catálogo del sistema.
- [x] CHK010 La baja de ejercicios es lógica y define el comportamiento sobre rutinas existentes.

## 3. Consistencia de Modelos y Contratos

- [x] CHK011 `data-model.md` y `contracts/exercise-library-api.yaml` reflejan días, bloques, categoría, marca y baja lógica.
- [x] CHK012 Los errores se definen conforme a RFC 7807 (`application/problem+json`).
- [x] CHK013 La spec no menciona tipos de datos de base de datos (principio de caja negra).
- [x] CHK014 Las exclusiones de alcance (eliminación de rutinas, US-11, clonación y asignación) están declaradas.
