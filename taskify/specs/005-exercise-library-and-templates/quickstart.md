# Quickstart Validation: Biblioteca de Ejercicios, Videos Demostrativos y Rutinas Genéricas

**Feature**: `005-exercise-library-and-templates`
**Date**: 2026-10-15

## Prerrequisitos

- Token JWT de entrenador (`$TRAINER_TOKEN`)

## Escenario 1: Creación de Ejercicio y Validación de Videos Externos (US-08, US-12, US-52)

```bash
# 1. Intentar vincular URL no soportada (ej. TikTok o Dropbox)
curl -i -X POST http://localhost:8000/api/v1/exercises \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Press Militar con Mancuernas",
    "description": "Empuje vertical desde nivel de hombros",
    "target_muscle_group": "Deltoides",
    "equipment_needed": "Mancuernas",
    "video_url": "https://www.tiktok.com/@fitness/video/123456"
  }'

# Resultado esperado: HTTP 400 Bad Request ("Plataforma de video no soportada. Solo YouTube, Vimeo o Google Drive").

# 2. Crear ejercicio válido con enlace de YouTube y notas técnicas (US-12, US-52)
curl -i -X POST http://localhost:8000/api/v1/exercises \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Press Militar con Mancuernas",
    "description": "Empuje vertical sentado en banco a 75 grados",
    "target_muscle_group": "Deltoides",
    "equipment_needed": "Mancuernas y Banco",
    "video_url": "https://www.youtube.com/watch?v=2yjwXTZQDDI",
    "technical_cues": "Evitar arquear zona lumbar; mantener codos a 45 grados en el plano escapular."
  }'

# Resultado esperado: HTTP 201 Created con video_platform="YOUTUBE" y embed_url calculada.
```

## Escenario 2: Creación de Plantilla de Rutina Genérica (US-09)

```bash
# 1. Crear plantilla con 1 ejercicio
curl -i -X POST http://localhost:8000/api/v1/routine-templates \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Empuje Básico 3 Días",
    "duration_weeks": 4,
    "intensity": "MEDIA",
    "has_no_materials_alternative": false,
    "exercises": [
      {
        "exercise_id": "<EXERCISE_ID>",
        "order_index": 1,
        "default_sets": 4,
        "default_reps": "8-10"
      }
    ]
  }'

# Resultado esperado: HTTP 201 Created con la plantilla registrada.
```
