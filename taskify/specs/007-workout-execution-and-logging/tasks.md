---
description: "Tareas para completar US-51 sobre la base de US-12 y US-50"
---

# Tasks: Reproducción de video técnico del ejercicio (US-51)

**Input**: `spec.md` (User Story 2 = US-51) y contratos de ejercicios y rutinas de la spec 005.

**Alcance**: solo US-51. La variante segura del escenario 4 se conectará al mismo reproductor cuando US-53 incorpore su entidad y respuesta.

## Phase 1: Integración

- [x] T001 [P] [US51] Extender la prueba de rutina asignada para verificar que el alumno recibe la URL embebible validada y la ficha técnica del ejercicio.
- [x] T002 [US51] Agregar en `frontend/src/pages/StudentRoutinesPage.tsx` un control “Ver video técnico” que despliega y oculta el reproductor dentro de la misma pantalla.
- [x] T003 [P] [US51] Mostrar descripción, músculo trabajado y notas técnicas aun cuando el ejercicio no tenga video, sin renderizar el control de reproducción.
- [x] T004 [P] [US51] Incorporar estilos responsive, foco visible y objetivo táctil mínimo de 44 px en `frontend/src/styles/student-daily-routine-layout.css`.
- [x] T005 [US51] Ejecutar pruebas backend, Ruff, build frontend y `git diff --check`.

## Dependencias

- US-12 provee y valida `video_url` en formato embebible.
- US-50 provee la pantalla “Rutina del día”.
- US-52 provee las notas técnicas y claves de respiración mostradas como fallback o complemento del video.
- US-53 reutilizará el reproductor para las futuras variantes seguras con video.
