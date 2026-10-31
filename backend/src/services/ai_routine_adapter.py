import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.src.models.exercise import Exercise
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile

INTENSITY_ORDER = ["BAJA", "MEDIA", "ALTA", "EXIGENTE"]


@dataclass
class AdaptedExerciseData:
    exercise_id: str
    order_index: int
    sets: int
    reps: str
    rest_seconds: int
    adaptation_notes: str | None = None


@dataclass
class AdaptedBlockData:
    name: str
    order_index: int
    exercises: list[AdaptedExerciseData] = field(default_factory=list)


@dataclass
class AdaptedDayData:
    name: str
    order_index: int
    blocks: list[AdaptedBlockData] = field(default_factory=list)


@dataclass
class AIRoutineProposalResult:
    name: str
    duration_weeks: int
    intensity: str
    adaptation_summary: str
    days: list[AdaptedDayData] = field(default_factory=list)


class AIRoutineAdapter(ABC):
    """Interfaz abstracta para adaptadores de IA (Principio II de la Constitución)."""

    @abstractmethod
    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        pass


def _conflicts_with_zones(exercise: Exercise, zones: list[ProtectedZone]) -> str | None:
    """Verifica si el ejercicio compromete alguna de las zonas corporales protegidas."""
    searchable_text = f"{exercise.name} {exercise.target_muscle_group} {exercise.description}".lower()

    # Mapeo de términos de zonas protegidas a raíces corporales
    zone_keywords: dict[str, list[str]] = {
        "hombro": ["hombro", "deltoid", "manguito"],
        "rodilla": ["rodilla", "cuadricep", "cuádriceps", "isquio", "patel", "sentadilla", "estocada"],
        "lumbar": ["lumbar", "espalda baja", "peso muerto", "dorsal", "raquis"],
        "espalda": ["espalda", "dorsal", "trapecio", "lumbar"],
        "codo": ["codo", "tricep", "tríceps", "bicep", "bíceps", "brazo"],
        "cuello": ["cuello", "cervical", "trapecio"],
        "tobillo": ["tobillo", "gemelo", "pantorrilla", "sóleo", "salto"],
        "pecho": ["pecho", "pectoral", "press de banca"],
        "muneca": ["muñeca", "antebrazo"],
    }

    for zone in zones:
        area_lower = zone.body_area.lower()
        # Verificar coincidencia directa de la zona en el músculo objetivo o nombre
        if area_lower in searchable_text:
            return zone.body_area
        for key, tokens in zone_keywords.items():
            if key in area_lower and any(token in searchable_text for token in tokens):
                return zone.body_area
    return None


class HeuristicAIRoutineAdapter(AIRoutineAdapter):
    """Adaptador de IA basado en reglas biomecánicas y fisiológicas de adaptación.

    Cumple con el Principio II al ser determinista, seguro y sin dependencias
    externas ni credenciales en desarrollo y pruebas automatizadas.
    """

    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        modifications_log: list[str] = []
        student_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "el alumno"
        goals = [g.upper() for g in (student.fitness_goals or [])]

        # 1. Ajuste de intensidad global
        current_intensity = template.intensity.upper()
        if current_intensity not in INTENSITY_ORDER:
            current_intensity = "MEDIA"
        target_intensity = current_intensity

        # Reducción por salud si hay afección cardíaca o dolor en actividad
        if questionnaire and (
            questionnaire.has_heart_condition
            or questionnaire.has_chest_pain_activity
            or questionnaire.has_bone_joint_problem
        ):
            idx = INTENSITY_ORDER.index(current_intensity)
            if idx > 0:
                target_intensity = INTENSITY_ORDER[max(0, idx - 1)]
                modifications_log.append(
                    f"Intensidad ajustada de {current_intensity} a {target_intensity} por antecedentes de salud informados."
                )

        # 2. Catálogo de ejercicios disponibles para reemplazo
        available_alternatives = [
            e
            for e in trainer_exercises
            if e.deleted_at is None and _conflicts_with_zones(e, protected_zones) is None
        ]

        # 3. Procesamiento y adaptación de días, bloques y ejercicios
        adapted_days: list[AdaptedDayData] = []

        for day in template.days:
            adapted_blocks: list[AdaptedBlockData] = []
            for block in day.blocks:
                adapted_exercises: list[AdaptedExerciseData] = []
                for entry in block.exercises:
                    orig_ex = entry.exercise
                    conflict_zone = _conflicts_with_zones(orig_ex, protected_zones)

                    selected_exercise_id = orig_ex.id
                    adaptation_note = None

                    if conflict_zone:
                        # Buscar alternativa segura en la biblioteca del entrenador
                        candidates = [e for e in available_alternatives if e.id != orig_ex.id]
                        if candidates:
                            # Preferir ejercicio de categoría similar
                            same_cat = [e for e in candidates if e.category == orig_ex.category]
                            replacement = same_cat[0] if same_cat else candidates[0]
                            selected_exercise_id = replacement.id
                            adaptation_note = (
                                f"Sustituido '{orig_ex.name}' por '{replacement.name}' para proteger {conflict_zone}."
                            )
                            modifications_log.append(adaptation_note)
                        else:
                            # Si no hay alternativa segura, eliminar el ejercicio de la rutina
                            modifications_log.append(
                                f"Eliminado '{orig_ex.name}' por incompatibilidad con zona protegida '{conflict_zone}' sin alternativa disponible."
                            )
                            continue

                    # Adaptar series, repeticiones y descansos según objetivos
                    adapted_sets = entry.sets
                    adapted_reps = entry.reps
                    adapted_rest = entry.rest_seconds

                    if "HIPERTROFIA" in goals:
                        adapted_sets = max(3, min(entry.sets, 4))
                        adapted_reps = "8-12"
                        adapted_rest = max(60, min(entry.rest_seconds, 90))
                    elif "FUERZA" in goals:
                        adapted_sets = max(3, min(entry.sets + 1, 5))
                        adapted_reps = "5-6"
                        adapted_rest = max(120, entry.rest_seconds)
                    elif "RESISTENCIA" in goals or "PERDIDA_GRASA" in goals:
                        adapted_sets = max(3, entry.sets)
                        adapted_reps = "15-20"
                        adapted_rest = min(entry.rest_seconds, 45)
                    elif "SALUD_POSTURAL" in goals or "REHABILITACION" in goals:
                        adapted_sets = min(entry.sets, 3)
                        adapted_reps = "12-15"
                        adapted_rest = max(entry.rest_seconds, 60)

                    # Ajustes adicionales si el cuestionario de salud lo amerita
                    if questionnaire and (questionnaire.has_heart_condition or questionnaire.has_chest_pain_activity):
                        adapted_sets = min(adapted_sets, 3)
                        adapted_rest = max(adapted_rest, 90)

                    adapted_exercises.append(
                        AdaptedExerciseData(
                            exercise_id=selected_exercise_id,
                            order_index=len(adapted_exercises),
                            sets=adapted_sets,
                            reps=adapted_reps,
                            rest_seconds=adapted_rest,
                            adaptation_notes=adaptation_note,
                        )
                    )

                if adapted_exercises:
                    adapted_blocks.append(
                        AdaptedBlockData(
                            name=block.name,
                            order_index=len(adapted_blocks),
                            exercises=adapted_exercises,
                        )
                    )

            if adapted_blocks:
                adapted_days.append(
                    AdaptedDayData(
                        name=day.name,
                        order_index=len(adapted_days),
                        blocks=adapted_blocks,
                    )
                )

        # 4. Síntesis del resumen de adaptaciones
        if not modifications_log:
            modifications_log.append("Rutina compatible: se mantuvieron los ejercicios base adaptando volumen y descanso.")

        goals_text = ", ".join(goals) if goals else "Generales"
        summary_lines = [
            f"Propuesta de rutina adaptada por IA para {student_name}:",
            f"- Objetivos del alumno: {goals_text}",
            f"- Intensidad asignada: {target_intensity}",
            "- Modificaciones y adaptaciones:",
        ]
        for log in modifications_log:
            summary_lines.append(f"  • {log}")
        summary_lines.append("\n* Requiere revisión y aprobación manual del entrenador (Human-in-the-Loop).")

        return AIRoutineProposalResult(
            name=f"{template.name} - Adaptada para {student_name}",
            duration_weeks=template.duration_weeks,
            intensity=target_intensity,
            adaptation_summary="\n".join(summary_lines),
            days=adapted_days,
        )


def get_ai_routine_adapter() -> AIRoutineAdapter:
    """Factory para obtener la instancia del adaptador de IA activo."""
    provider = os.getenv("AI_ROUTINE_PROVIDER", "heuristic").lower()
    if provider == "heuristic":
        return HeuristicAIRoutineAdapter()
    return HeuristicAIRoutineAdapter()
