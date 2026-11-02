#!/usr/bin/env python3
"""Script de seed de datos de demostración para Set to Set.

Crea un conjunto variado, coherente e idempotente de usuarios (entrenadores y alumnos),
perfiles completos, paquetes de entrenamiento, cuestionarios de salud, zonas a proteger,
aptos médicos, solicitudes/vínculos, ejercicios y rutinas (genéricas y con IA) para una
demostración académica completa, sin tener que cargar rutinas durante la presentación.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# Asegurar que la raíz del proyecto esté en sys.path para importaciones absolutas
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.core.database import Base, SessionLocal, engine
from backend.src.core.migrations import apply_migrations
from backend.src.core.security import hash_password
from backend.src.core.storage import UPLOADS_DIR
from backend.src.models.assigned_routine import (
    AssignedRoutine,
    AssignedRoutineBlock,
    AssignedRoutineDay,
    AssignedRoutineExercise,
)
from backend.src.models.exercise import Exercise
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.medical_clearance import MedicalClearance
from backend.src.models.notification import Notification
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.student_routine import RoutineChangeLog, StudentRoutine
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import PasswordResetToken, User, UserSession
from backend.src.schemas.routine_template import RoutineTemplateInput
from backend.src.services.routine_template_service import build_days
from backend.src.services.student_routine_service import sync_assigned_routine

DEMO_DOMAIN = "demo.settoset.com"
DEMO_PASSWORD = "DemoPassword123!"

# Contenido binario de un archivo PDF mínimo válido para aptos médicos
MINIMAL_VALID_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n"
    b"0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n"
    b"190\n"
    b"%%EOF\n"
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Definición de Entrenadores y Paquetes de Demostración
# ---------------------------------------------------------------------------
TRAINERS_DEMO_DATA: list[dict[str, Any]] = [
    {
        "key": "trainer_lucas",
        "email": f"lucas.benitez@{DEMO_DOMAIN}",
        "full_name": "Lucas Benítez",
        "contact_phone": "+541145218901",
        "specialty": "Fuerza e Hipertrofia",
        "bio": (
            "Especialista en entrenamiento de fuerza y sobrecarga progresiva. Más de 8 años guiando a atletas "
            "y principiantes a alcanzar su máximo potencial muscular con base científica y planificación estructurada."
        ),
        "certifications": (
            "Profesor Nacional de Educación Física (UNLP), Certificación CSCS (NSCA), Antropometrista ISAK Nivel 2."
        ),
        "max_students": 15,
        "plans": [
            {
                "title": "Fuerza y Rendimiento Integral",
                "description": (
                    "Plan enfocado en el desarrollo de fuerza máxima (sentadilla, banca y peso muerto) con seguimiento semanal de cargas y técnica."
                ),
                "monthly_price": Decimal("32000.00"),
                "currency": "ARS",
            },
            {
                "title": "Hipertrofia Muscular Avanzada",
                "description": (
                    "Rutinas periodizadas en bloques de volumen e intensidad para maximizar el crecimiento muscular con feedback continuo."
                ),
                "monthly_price": Decimal("28000.00"),
                "currency": "ARS",
            },
            {
                "title": "Iniciación al Entrenamiento de Fuerza",
                "description": (
                    "Aprendé la técnica correcta de los ejercicios fundamentales con progresiones seguras adaptadas a tu nivel inicial."
                ),
                "monthly_price": Decimal("22000.00"),
                "currency": "ARS",
            },
        ],
    },
    {
        "key": "trainer_mariana",
        "email": f"mariana.vega@{DEMO_DOMAIN}",
        "full_name": "Mariana Vega",
        "contact_phone": "+541145218902",
        "specialty": "Pérdida de Peso y Salud",
        "bio": (
            "Entrenadora personal enfocada en recomposición corporal saludable, hábitos sostenibles y entrenamiento "
            "metabólico adaptable al ritmo de la vida cotidiana sin dietas restrictivas ni sobreentrenamiento."
        ),
        "certifications": (
            "Licenciada en Alto Rendimiento Deportivo, Especialista en Nutrición Deportiva y Fitness Femenino."
        ),
        "max_students": 10,
        "plans": [
            {
                "title": "Recomposición Corporal Sostenible",
                "description": (
                    "Combinación de entrenamiento de resistencia y circuitos metabólicos para perder grasa conservando masa muscular magra."
                ),
                "monthly_price": Decimal("26000.00"),
                "currency": "ARS",
            },
            {
                "title": "Fitness Saludable y Vitalidad",
                "description": (
                    "Rutinas de impacto articular moderado para mejorar la capacidad cardiorrespiratoria, reducir el estrés y ganar energía diaria."
                ),
                "monthly_price": Decimal("20000.00"),
                "currency": "ARS",
            },
        ],
    },
    {
        "key": "trainer_ignacio",
        "email": f"ignacio.rossi@{DEMO_DOMAIN}",
        "full_name": "Ignacio Rossi",
        "contact_phone": "+541145218903",
        "specialty": "Resistencia y Rendimiento",
        "bio": (
            "Entrenador de running, maratón y triatlón. Planificación de cargas individualizadas para corredores "
            "de 5k hasta 42k y ciclistas aficionados buscando mejorar sus marcas personales de manera segura."
        ),
        "certifications": (
            "Entrenador World Athletics Nivel 2, Preparador Físico UBA, Posgrado en Fisiología del Ejercicio."
        ),
        "max_students": 12,
        "plans": [
            {
                "title": "Running y Fondismo 10k/21k",
                "description": (
                    "Planificación personalizada de ritmos, fondos y pasadas semanales con monitoreo cardíaco y prevención de lesiones típicas de corredor."
                ),
                "monthly_price": Decimal("25000.00"),
                "currency": "ARS",
            },
            {
                "title": "Acondicionamiento Aeróbico Total",
                "description": (
                    "Mejora sostenida de VO2 máx y resistencia cardiovascular general con trabajos por intervalos de alta y media intensidad."
                ),
                "monthly_price": Decimal("21000.00"),
                "currency": "ARS",
            },
        ],
    },
    {
        "key": "trainer_camila",
        "email": f"camila.navarro@{DEMO_DOMAIN}",
        "full_name": "Camila Navarro",
        "contact_phone": "+541145218904",
        "specialty": "Movilidad/rehabilitación",
        "bio": (
            "Kinesióloga y preparadora física. Enfoque preventivo, fortalecimiento de la zona media y recuperación funcional "
            "para volver a entrenar sin dolor tras molestias articulares o largas jornadas sedentarias."
        ),
        "certifications": (
            "Licenciada en Kinesiología y Fisiatría (UBA), Especialista en FMS (Functional Movement Screen) y Movilidad Articular."
        ),
        "max_students": 8,
        "plans": [
            {
                "title": "Readaptación Funcional y Postura",
                "description": (
                    "Ejercicios terapéuticos guiados para aliviar molestias lumbares, cervicales y articulares, corrigiendo desbalances posturales."
                ),
                "monthly_price": Decimal("30000.00"),
                "currency": "ARS",
            },
            {
                "title": "Movilidad Articular y Flexibilidad",
                "description": (
                    "Rutinas diarias de movilidad articular activa para ganar rango de movimiento, desbloquear caderas y prevenir lesiones."
                ),
                "monthly_price": Decimal("24000.00"),
                "currency": "ARS",
            },
            {
                "title": "Fortalecimiento de Core y Estabilidad",
                "description": (
                    "Entrenamiento preventivo para columna y pelvis con progresión controlada y ejercicios isométricos seguros."
                ),
                "monthly_price": Decimal("27000.00"),
                "currency": "ARS",
            },
        ],
    },
    {
        "key": "trainer_gonzalo",
        "email": f"gonzalo.morales@{DEMO_DOMAIN}",
        "full_name": "Gonzalo Morales",
        "contact_phone": "+541145218905",
        "specialty": "Fuerza y Potencia",
        "bio": (
            "Entrenamiento de alta intensidad, levantamiento olímpico y cross training. Cupo ultra reducido "
            "para garantizar un seguimiento diario milimétrico de la técnica y la programación."
        ),
        "certifications": (
            "CrossFit Level 2 Trainer, Entrenador Nacional de Halterofilia y Levantamiento de Pesas."
        ),
        # Cupo configurado en 1 para demostrar entrenador con cupos agotados cuando tiene 1 alumno activo
        "max_students": 1,
        "plans": [
            {
                "title": "Cross Training y Alta Intensidad",
                "description": (
                    "Programación avanzada de fuerza, gimnásticos y acondicionamiento metabólico con análisis técnico en video."
                ),
                "monthly_price": Decimal("35000.00"),
                "currency": "ARS",
            },
            {
                "title": "Halterofilia y Levantamiento Olímpico",
                "description": (
                    "Mejora técnica de Snatch y Clean & Jerk con periodización ondular para atletas de fuerza."
                ),
                "monthly_price": Decimal("38000.00"),
                "currency": "ARS",
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Definición de Alumnos de Demostración
# ---------------------------------------------------------------------------
STUDENTS_DEMO_DATA: list[dict[str, Any]] = [
    {
        "key": "student_mateo",
        "email": f"mateo.gomez@{DEMO_DOMAIN}",
        "first_name": "Mateo",
        "last_name": "Gómez",
        "birth_date": datetime(1999, 4, 12, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660001",
        "bio": "Estudiante universitario apasionado por el entrenamiento de sobrecarga. Entreno 4 veces por semana.",
        "fitness_goals": ["hipertrofia", "fuerza"],
        "personal_motivation": "Quiero ganar masa muscular de forma limpia y aprender la técnica correcta de sentadilla y banca.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": False,
            "takes_prescription_meds": False,
            "other_medical_conditions": None,
        },
        "protected_zones": [],
        "has_medical_clearance": False,
    },
    {
        "key": "student_sofia",
        "email": f"sofia.martinez@{DEMO_DOMAIN}",
        "first_name": "Sofía",
        "last_name": "Martínez",
        "birth_date": datetime(1996, 8, 23, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660002",
        "bio": "Diseñadora gráfica. Busco retomar la actividad física cuidando una rodilla operada hace 2 años.",
        "fitness_goals": ["perdida_de_peso", "salud_general"],
        "personal_motivation": "Busco bajar de peso progresivamente y crear hábitos de vida saludables que pueda sostener en el tiempo.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": True,
            "takes_prescription_meds": False,
            "other_medical_conditions": "Operación de menisco rodilla izquierda en 2024, sin dolor actual.",
        },
        "protected_zones": ["Knee"],
        "has_medical_clearance": True,
    },
    {
        "key": "student_martin",
        "email": f"martin.herrera@{DEMO_DOMAIN}",
        "first_name": "Martín",
        "last_name": "Herrera",
        "birth_date": datetime(1993, 11, 5, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660003",
        "bio": "Contador público. Decidí priorizar mi salud y volver a hacer ejercicio regular después de un largo período sedentario.",
        "fitness_goals": ["perdida_de_peso", "resistencia"],
        "personal_motivation": "Quiero bajar los niveles de colesterol, mejorar mi resistencia cardiovascular y volver a jugar al fútbol con amigos.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": False,
            "takes_prescription_meds": True,
            "other_medical_conditions": "Medicación para control preventivo de presión arterial.",
        },
        "protected_zones": [],
        "has_medical_clearance": True,
    },
    {
        "key": "student_valentina",
        "email": f"valentina.rossi@{DEMO_DOMAIN}",
        "first_name": "Valentina",
        "last_name": "Rossi",
        "birth_date": datetime(2001, 2, 18, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660004",
        "bio": "Corredora amateur. Ya completé carreras de 5k y 10k y mi meta es dar el salto a los 21k.",
        "fitness_goals": ["resistencia"],
        "personal_motivation": "Preparación para mi primera media maratón de Buenos Aires, buscando bajar de 1h50m.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": False,
            "takes_prescription_meds": False,
            "other_medical_conditions": None,
        },
        "protected_zones": [],
        "has_medical_clearance": False,
    },
    {
        "key": "student_joaquin",
        "email": f"joaquin.diaz@{DEMO_DOMAIN}",
        "first_name": "Joaquín",
        "last_name": "Díaz",
        "birth_date": datetime(1995, 7, 30, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660005",
        "bio": "Programador de software. Paso muchas horas frente a la computadora y sufro de rigidez lumbar constante.",
        "fitness_goals": ["movilidad_rehabilitacion", "salud_general"],
        "personal_motivation": "Aliviar molestias lumbares crónicas, ganar movilidad de cadera y fortalecer la zona media.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": True,
            "takes_prescription_meds": False,
            "other_medical_conditions": "Protrusión discal L5-S1 controlada médicamente.",
        },
        "protected_zones": ["Lower back"],
        "has_medical_clearance": True,
    },
    {
        "key": "student_lucia",
        "email": f"lucia.fernandez@{DEMO_DOMAIN}",
        "first_name": "Lucía",
        "last_name": "Fernández",
        "birth_date": datetime(2000, 9, 14, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660006",
        "bio": "Estudiante de arquitectura. Busco un entrenamiento que se adapte a mis horarios variables de facultad.",
        "fitness_goals": ["salud_general", "resistencia"],
        "personal_motivation": "Incorporar actividad física regular para tener más energía en el día a día y despejar la mente.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": False,
            "takes_prescription_meds": False,
            "other_medical_conditions": None,
        },
        "protected_zones": [],
        "has_medical_clearance": False,
    },
    {
        "key": "student_tomas",
        "email": f"tomas.castro@{DEMO_DOMAIN}",
        "first_name": "Tomás",
        "last_name": "Castro",
        "birth_date": datetime(1997, 12, 3, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660007",
        "bio": "Atleta aficionado de cross training. Busco pulir levantamientos olímpicos pesados y optimizar cargas.",
        "fitness_goals": ["fuerza", "hipertrofia"],
        "personal_motivation": "Competir en torneos locales de CrossFit y superar mi récord en Snatch y Clean & Jerk.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": True,
            "takes_prescription_meds": False,
            "other_medical_conditions": "Molestia articular en muñeca derecha en sobrecargas máximas.",
        },
        "protected_zones": ["Wrist and hand"],
        "has_medical_clearance": True,
    },
    {
        "key": "student_camila_t",
        "email": f"camila.torres@{DEMO_DOMAIN}",
        "first_name": "Camila",
        "last_name": "Torres",
        "birth_date": datetime(1998, 3, 27, 0, 0, 0, tzinfo=UTC),
        "contact_phone": "+541155660008",
        "bio": "Profesora de música. Superé una tendinitis de hombro y quiero ganar fuerza en tren superior de forma segura.",
        "fitness_goals": ["movilidad_rehabilitacion", "fuerza"],
        "personal_motivation": "Fortalecer hombros y espalda alta para prevenir dolores posturales al tocar instrumentos.",
        "questionnaire": {
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": True,
            "takes_prescription_meds": False,
            "other_medical_conditions": "Tendinitis manguito rotador derecho resuelta en kinesiología.",
        },
        "protected_zones": ["Shoulder"],
        "has_medical_clearance": False,
    },
]

# ---------------------------------------------------------------------------
# Solicitudes y Vínculos de Demostración
# ---------------------------------------------------------------------------
REQUESTS_DEMO_DATA: list[dict[str, Any]] = [
    {
        # Sofía Martínez solicita a Lucas Benítez -> PENDING (para probar bandeja de entrada del entrenador)
        "student_key": "student_sofia",
        "trainer_key": "trainer_lucas",
        "plan_title": "Iniciación al Entrenamiento de Fuerza",
        "status": "PENDING",
        "days_ago": 1,
        "student_message": "¡Hola Lucas! Tengo una molestia previa en la rodilla, quisiera arrancar con buena técnica para no resentirme.",
        "trainer_response_message": None,
        "create_notification": {
            "recipient": "trainer_lucas",
            "type": "NEW_REQUEST",
            "title": "¡Nueva solicitud de entrenamiento!",
            "message": "El alumno Sofía Martínez ha solicitado unirse a tu plan Iniciación al Entrenamiento de Fuerza.",
        },
    },
    {
        # Martín Herrera solicita a Mariana Vega -> ACCEPTED + Vínculo ACTIVE (para probar vista de plan activo en alumno)
        "student_key": "student_martin",
        "trainer_key": "trainer_mariana",
        "plan_title": "Recomposición Corporal Sostenible",
        "status": "ACCEPTED",
        "days_ago": 5,
        "student_message": "Hola Mariana, me gustaría empezar a entrenar para bajar de peso de manera cuidada y sostenible.",
        "trainer_response_message": "¡Hola Martín! Bienvenido al equipo. Vamos a armar un plan progresivo respetando tus tiempos y cuidando tu salud.",
        "active_relationship": {
            "welcome_message": "¡Hola Martín! Bienvenido al equipo. Vamos a armar un plan progresivo respetando tus tiempos y cuidando tu salud.",
            "start_days_ago": 4,
        },
        "create_notification": {
            "recipient": "student_martin",
            "type": "TRAINING_ACCEPTED",
            "title": "¡Bienvenido/a al programa de entrenamiento!",
            "message": "¡Hola Martín! Bienvenido al equipo. Vamos a armar un plan progresivo respetando tus tiempos y cuidando tu salud.",
        },
    },
    {
        # Valentina Rossi solicita a Ignacio Rossi -> REJECTED (para probar historial de solicitudes rechazadas)
        "student_key": "student_valentina",
        "trainer_key": "trainer_ignacio",
        "plan_title": "Running y Fondismo 10k/21k",
        "status": "REJECTED",
        "days_ago": 3,
        "student_message": "Hola Ignacio! Busco prepararme para una carrera de 21k en 6 semanas partiendo de 10k.",
        "trainer_response_message": "Hola Valentina, para 21k requerimos un bloque de adaptación aeróbica de al menos 14 semanas para evitar sobrecargas y lesiones. Te recomiendo sumarte para la edición del próximo ciclo.",
    },
    {
        # Tomás Castro solicita a Gonzalo Morales -> ACCEPTED + Vínculo ACTIVE (ocupa el único cupo de Gonzalo Morales para demostrar 'Sin cupos')
        "student_key": "student_tomas",
        "trainer_key": "trainer_gonzalo",
        "plan_title": "Cross Training y Alta Intensidad",
        "status": "ACCEPTED",
        "days_ago": 7,
        "student_message": "Buenas Gonzalo, entreno cross training hace 3 años y quiero pulir levantamientos olímpicos pesados.",
        "trainer_response_message": "¡Bienvenido Tomás! Vamos a romper esas marcas personales con una planificación estricta de fuerza.",
        "active_relationship": {
            "welcome_message": "¡Bienvenido Tomás! Vamos a romper esas marcas personales con una planificación estricta de fuerza.",
            "start_days_ago": 6,
        },
        "create_notification": {
            "recipient": "student_tomas",
            "type": "TRAINING_ACCEPTED",
            "title": "¡Bienvenido/a al programa de entrenamiento!",
            "message": "¡Bienvenido Tomás! Vamos a romper esas marcas personales con una planificación estricta de fuerza.",
        },
    },
]


# ---------------------------------------------------------------------------
# Ejercicios y Rutinas de Demostración
# ---------------------------------------------------------------------------
def _exercise(
    name: str,
    category: str,
    muscle: str,
    equipment: str,
    description: str,
    cues: str,
    zones: tuple[str, ...] = (),
    no_materials: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "target_muscle_group": muscle,
        "equipment_needed": equipment,
        "description": description,
        "technical_cues": cues,
        "contraindicated_zones": list(zones),
        "has_no_materials_alternative": no_materials,
    }


def _block(name: str, minutes: int, *exercises: tuple[str, int, str, int, float | None]) -> dict[str, Any]:
    return {
        "name": name,
        "estimated_duration_minutes": minutes,
        "exercises": [
            {"exercise": exercise, "sets": sets, "reps": reps, "rest_seconds": rest, "target_weight_kg": weight}
            for exercise, sets, reps, rest, weight in exercises
        ],
    }


# Ignacio y Camila quedan sin ejercicios ni rutinas para poder mostrar la carga manual.
EXERCISES_DEMO_DATA: dict[str, list[dict[str, Any]]] = {
    "trainer_lucas": [
        _exercise("Sentadilla con Barra", "FUERZA", "Cuádriceps", "Barra y rack", "Sentadilla trasera con barra.", "Rodillas en línea con la punta de los pies.", ("Knee", "Lower back")),
        _exercise("Press de Banca", "FUERZA", "Pectoral", "Barra y banco", "Empuje horizontal con barra.", "Escápulas retraídas durante todo el recorrido.", ("Shoulder",)),
        _exercise("Peso Muerto", "FUERZA", "Cadena posterior", "Barra", "Levantamiento de la barra desde el piso.", "Espalda neutra y barra pegada al cuerpo.", ("Lower back",)),
        _exercise("Remo con Barra", "FUERZA", "Dorsales", "Barra", "Tirón horizontal con el torso inclinado.", "Llevar los codos hacia atrás sin balancear el torso."),
        _exercise("Plancha Abdominal", "FUERZA", "Core", "Ninguno", "Isométrico de zona media.", "Cadera alineada con hombros y talones.", no_materials=True),
    ],
    "trainer_mariana": [
        _exercise("Sentadilla con Peso Corporal", "FUERZA", "Cuádriceps", "Ninguno", "Sentadilla libre sin carga externa.", "Bajar controlado y empujar con todo el pie.", ("Knee",), True),
        _exercise("Remo con Banda Elástica", "FUERZA", "Dorsales", "Banda elástica", "Tirón horizontal con banda.", "Mantener los hombros lejos de las orejas."),
        _exercise("Flexiones de Brazos", "FUERZA", "Pectoral", "Ninguno", "Empuje horizontal con el peso del cuerpo.", "Cuerpo en bloque; apoyar rodillas si hace falta.", ("Shoulder",), True),
        _exercise("Caminata en Cinta", "CARDIO", "Sistema cardiovascular", "Cinta", "Trabajo aeróbico continuo.", "Ritmo que permita conversar.", no_materials=True),
        _exercise("Burpees Modificados", "CARDIO", "Cuerpo completo", "Ninguno", "Burpee sin salto ni flexión.", "Apoyar los pies de a uno para reducir el impacto.", no_materials=True),
        _exercise("Movilidad de Cadera", "MOVILIDAD", "Cadera", "Colchoneta", "Círculos de cadera en cuadrupedia.", "Movimiento lento y sin dolor.", no_materials=True),
    ],
    "trainer_gonzalo": [
        _exercise("Sentadilla Frontal", "FUERZA", "Cuádriceps", "Barra y rack", "Sentadilla con la barra adelante.", "Codos altos y torso vertical.", ("Wrist and hand",)),
        _exercise("Peso Muerto Rumano", "FUERZA", "Isquiotibiales", "Barra", "Bisagra de cadera con piernas semirrígidas.", "Empujar la cadera hacia atrás.", ("Lower back",)),
        _exercise("Power Clean", "FUERZA", "Cuerpo completo", "Barra", "Cargada de potencia desde el piso.", "Extensión completa antes de recibir la barra.", ("Wrist and hand", "Lower back")),
        _exercise("Snatch", "FUERZA", "Cuerpo completo", "Barra", "Arranque olímpico.", "Barra cerca del cuerpo y recepción estable.", ("Wrist and hand", "Shoulder")),
        _exercise("Remo Ergómetro", "CARDIO", "Cuerpo completo", "Remo ergómetro", "Intervalos en remo.", "Empujar con piernas y terminar con brazos."),
        _exercise("Sentadilla Goblet", "FUERZA", "Cuádriceps", "Kettlebell", "Sentadilla con la carga al pecho.", "Pecho arriba y codos adentro."),
        _exercise("Swing con Kettlebell", "FUERZA", "Cadena posterior", "Kettlebell", "Balanceo balístico desde la cadera.", "La potencia sale de la cadera, no de los brazos."),
    ],
}

ROUTINES_DEMO_DATA: list[dict[str, Any]] = [
    {
        "trainer_key": "trainer_lucas",
        "name": "Fuerza Base 3 Días",
        "duration_weeks": 8,
        "intensity": "ALTA",
        "days": [
            {"name": "Día 1 - Pierna", "blocks": [_block("Principal", 50, ("Sentadilla con Barra", 5, "5", 150, 80.0), ("Plancha Abdominal", 3, "45 seg", 60, None))]},
            {"name": "Día 2 - Empuje", "blocks": [_block("Principal", 45, ("Press de Banca", 5, "5", 150, 60.0), ("Remo con Barra", 4, "8", 90, 50.0))]},
            {"name": "Día 3 - Tirón", "blocks": [_block("Principal", 50, ("Peso Muerto", 4, "5", 180, 100.0), ("Plancha Abdominal", 3, "60 seg", 60, None))]},
        ],
    },
    {
        "trainer_key": "trainer_lucas",
        "name": "Iniciación Cuerpo Completo",
        "duration_weeks": 6,
        "intensity": "MEDIA",
        "days": [
            {"name": "Día 1", "blocks": [_block("Técnica", 40, ("Sentadilla con Barra", 3, "10", 90, 30.0), ("Press de Banca", 3, "10", 90, 25.0), ("Remo con Barra", 3, "10", 90, 25.0))]},
        ],
    },
    {
        "trainer_key": "trainer_mariana",
        "name": "Recomposición Inicial",
        "duration_weeks": 8,
        "intensity": "MEDIA",
        "days": [
            {"name": "Día 1 - Fuerza", "blocks": [_block("Principal", 35, ("Sentadilla con Peso Corporal", 4, "12", 60, None), ("Remo con Banda Elástica", 4, "12", 60, None), ("Flexiones de Brazos", 3, "10", 60, None))]},
            {"name": "Día 2 - Cardio", "blocks": [_block("Aeróbico", 30, ("Caminata en Cinta", 1, "30 min", 0, None)), _block("Vuelta a la calma", 10, ("Movilidad de Cadera", 2, "10", 30, None))]},
        ],
    },
    {
        "trainer_key": "trainer_mariana",
        "name": "Circuito Metabólico en Casa",
        "duration_weeks": 4,
        "intensity": "ALTA",
        "has_no_materials_alternative": True,
        "days": [
            {"name": "Día 1", "blocks": [_block("Circuito", 25, ("Burpees Modificados", 4, "12", 45, None), ("Sentadilla con Peso Corporal", 4, "15", 45, None), ("Flexiones de Brazos", 4, "10", 45, None))]},
        ],
    },
    {
        "trainer_key": "trainer_gonzalo",
        "name": "Acondicionamiento Cross Training",
        "duration_weeks": 6,
        "intensity": "ALTA",
        "days": [
            {"name": "Día 1 - Fuerza", "blocks": [_block("Principal", 40, ("Sentadilla Goblet", 5, "8", 90, 32.0), ("Swing con Kettlebell", 5, "15", 60, 24.0))]},
            {"name": "Día 2 - Motor", "blocks": [_block("Intervalos", 30, ("Remo Ergómetro", 6, "500 m", 90, None))]},
        ],
    },
    {
        # Incluye ejercicios contraindicados para Tomás: sirve para mostrar la adaptación con IA.
        "trainer_key": "trainer_gonzalo",
        "name": "Halterofilia Técnica",
        "duration_weeks": 6,
        "intensity": "EXIGENTE",
        "days": [
            {"name": "Día 1 - Arranque", "blocks": [_block("Técnica", 45, ("Snatch", 6, "3", 120, 50.0), ("Sentadilla Frontal", 4, "5", 120, 70.0))]},
            {"name": "Día 2 - Envión", "blocks": [_block("Técnica", 45, ("Power Clean", 6, "3", 120, 70.0), ("Peso Muerto Rumano", 4, "6", 120, 80.0))]},
        ],
    },
]

# Martín ya tiene una rutina con IA aprobada; Tomás entrena una genérica y tiene una propuesta por revisar.
AI_ROUTINES_DEMO_DATA: list[dict[str, Any]] = [
    {
        "trainer_key": "trainer_mariana",
        "student_key": "student_martin",
        "template_name": "Recomposición Inicial",
        "name": "Recomposición Inicial - Adaptada para Martín",
        "status": "APPROVED",
        "intensity": "BAJA",
        "rest_bonus_seconds": 30,
        "replacements": {},
        "adaptation_note": "Más descanso por el control de presión arterial.",
        "adaptation_summary": (
            "Se bajó la intensidad de Media a Baja y se sumaron 30 segundos de descanso por la medicación "
            "para la presión informada en el cuestionario de salud."
        ),
    },
    {
        "trainer_key": "trainer_gonzalo",
        "student_key": "student_tomas",
        "template_name": "Halterofilia Técnica",
        "name": "Halterofilia Técnica - Adaptada para Tomás",
        "status": "PENDING_REVIEW",
        "intensity": "ALTA",
        "rest_bonus_seconds": 0,
        "replacements": {
            "Snatch": "Swing con Kettlebell",
            "Sentadilla Frontal": "Sentadilla Goblet",
            "Power Clean": "Remo Ergómetro",
        },
        "adaptation_note": "Reemplazado por la molestia de muñeca.",
        "adaptation_summary": (
            "Se reemplazaron los ejercicios con carga sobre la muñeca derecha (Snatch, Sentadilla Frontal y "
            "Power Clean) por alternativas de la biblioteca, y se bajó la intensidad de Exigente a Alta."
        ),
    },
]
# Rutinas genéricas asignadas directamente: (entrenador, alumno, rutina).
ROUTINE_ASSIGNMENTS_DEMO_DATA: list[tuple[str, str, str]] = [
    ("trainer_gonzalo", "student_tomas", "Acondicionamiento Cross Training"),
]


def _seed_routines(
    db: Session,
    trainer_map: dict[str, TrainerProfile],
    student_map: dict[str, StudentProfile],
    stats: dict[str, int],
    now: datetime,
) -> None:
    """Carga ejercicios y rutinas; lo existente no se pisa para respetar cambios hechos en la demo."""
    exercise_ids: dict[tuple[str, str], str] = {}
    for trainer_key, exercises in EXERCISES_DEMO_DATA.items():
        trainer = trainer_map[trainer_key]
        for data in exercises:
            exercise = db.scalar(
                select(Exercise).where(Exercise.trainer_id == trainer.id, Exercise.name == data["name"])
            )
            if exercise is None:
                exercise = Exercise(trainer_id=trainer.id, created_at=now, updated_at=now, **data)
                db.add(exercise)
                db.flush()
            exercise_ids[(trainer_key, data["name"])] = exercise.id
            stats["exercises"] += 1

    templates: dict[tuple[str, str], RoutineTemplate] = {}
    for data in ROUTINES_DEMO_DATA:
        trainer_key = data["trainer_key"]
        trainer = trainer_map[trainer_key]
        template = db.scalar(
            select(RoutineTemplate).where(RoutineTemplate.trainer_id == trainer.id, RoutineTemplate.name == data["name"])
        )
        if template is None:
            content = {key: value for key, value in data.items() if key != "trainer_key"}
            for day in content["days"]:
                for block in day["blocks"]:
                    for entry in block["exercises"]:
                        entry["exercise_id"] = exercise_ids[(trainer_key, entry["exercise"])]
            # Pasa por el schema real para que el seed no pueda cargar rutinas inválidas.
            payload = RoutineTemplateInput.model_validate(content)
            template = RoutineTemplate(
                trainer_id=trainer.id,
                name=payload.name,
                duration_weeks=payload.duration_weeks,
                intensity=payload.intensity,
                has_no_materials_alternative=payload.has_no_materials_alternative,
                days=build_days(payload),
                created_at=now,
                updated_at=now,
            )
            db.add(template)
            db.flush()
        templates[(trainer_key, data["name"])] = template
        stats["routines"] += 1

    for trainer_key, student_key, routine_name in ROUTINE_ASSIGNMENTS_DEMO_DATA:
        relationship = _active_relationship(db, trainer_map[trainer_key], student_map[student_key])
        if relationship.initial_routine_id is None:
            relationship.initial_routine_id = templates[(trainer_key, routine_name)].id
            db.flush()

    for data in AI_ROUTINES_DEMO_DATA:
        trainer_key = data["trainer_key"]
        trainer = trainer_map[trainer_key]
        student = student_map[data["student_key"]]
        routine = db.scalar(
            select(AssignedRoutine).where(
                AssignedRoutine.trainer_id == trainer.id,
                AssignedRoutine.student_id == student.id,
                AssignedRoutine.name == data["name"],
            )
        )
        stats["ai_routines"] += 1
        if routine is not None:
            continue
        routine = _build_ai_routine(data, trainer, student, templates, exercise_ids, now)
        db.add(routine)
        db.flush()
        if routine.status == "APPROVED":
            relationship = _active_relationship(db, trainer, student)
            relationship.initial_routine_id = routine.id
            sync_assigned_routine(db, relationship, routine)


def _active_relationship(db: Session, trainer: TrainerProfile, student: StudentProfile) -> TrainingRelationship:
    return db.scalars(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.student_id == student.id,
            TrainingRelationship.status == "ACTIVE",
        )
    ).one()


def _build_ai_routine(
    data: dict[str, Any],
    trainer: TrainerProfile,
    student: StudentProfile,
    templates: dict[tuple[str, str], RoutineTemplate],
    exercise_ids: dict[tuple[str, str], str],
    now: datetime,
) -> AssignedRoutine:
    """Arma una propuesta fija a partir de la rutina base: la demo no depende de un proveedor de IA."""
    trainer_key = data["trainer_key"]
    template = templates[(trainer_key, data["template_name"])]
    replacements = data["replacements"]
    bonus = data["rest_bonus_seconds"]

    def adapted_entry(entry: Any) -> AssignedRoutineExercise:
        replacement = replacements.get(entry.exercise.name)
        changed = replacement is not None or bonus > 0
        return AssignedRoutineExercise(
            order_index=entry.order_index,
            exercise_id=exercise_ids[(trainer_key, replacement)] if replacement else entry.exercise_id,
            sets=entry.sets,
            reps=entry.reps,
            rest_seconds=entry.rest_seconds + bonus,
            adaptation_notes=data["adaptation_note"] if changed else None,
            target_weight_kg=None if replacement else entry.target_weight_kg,
        )

    return AssignedRoutine(
        trainer_id=trainer.id,
        student_id=student.id,
        template_id=template.id,
        name=data["name"],
        duration_weeks=template.duration_weeks,
        intensity=data["intensity"],
        has_no_materials_alternative=template.has_no_materials_alternative,
        status=data["status"],
        adaptation_summary=data["adaptation_summary"],
        approved_at=now if data["status"] == "APPROVED" else None,
        created_at=now,
        updated_at=now,
        days=[
            AssignedRoutineDay(
                order_index=day.order_index,
                name=day.name,
                blocks=[
                    AssignedRoutineBlock(
                        order_index=block.order_index,
                        name=block.name,
                        estimated_duration_minutes=block.estimated_duration_minutes,
                        exercises=[adapted_entry(entry) for entry in block.exercises],
                    )
                    for block in day.blocks
                ],
            )
            for day in template.days
        ],
    )


def seed_demo_data(db: Session, verbose: bool = True) -> dict[str, int]:
    """Crea o actualiza de forma idempotente todos los datos de demostración."""
    stats = {
        "trainers": 0,
        "plans": 0,
        "students": 0,
        "questionnaires": 0,
        "protected_zones": 0,
        "medical_clearances": 0,
        "requests": 0,
        "relationships": 0,
        "notifications": 0,
        "exercises": 0,
        "routines": 0,
        "ai_routines": 0,
    }

    now = _utc_now()
    trainer_map: dict[str, TrainerProfile] = {}
    student_map: dict[str, StudentProfile] = {}
    plan_map: dict[tuple[str, str], TrainingPlan] = {}
    user_map: dict[str, User] = {}

    # 1. Sembrar Entrenadores y Paquetes
    for t_data in TRAINERS_DEMO_DATA:
        email = t_data["email"].strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=TRAINER_ROLE,
                is_active=True,
                failed_login_attempts=0,
                locked_until=None,
                created_at=now,
            )
            db.add(user)
            db.flush()
        else:
            user.role = TRAINER_ROLE
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            db.flush()

        user_map[t_data["key"]] = user

        profile = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == user.id))
        if profile is None:
            profile = TrainerProfile(
                user_id=user.id,
                full_name=t_data["full_name"],
                contact_phone=t_data["contact_phone"],
                specialty=t_data["specialty"],
                status="PUBLISHED",
                bio=t_data["bio"],
                certifications=t_data["certifications"],
                max_students=t_data["max_students"],
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
            db.flush()
        else:
            profile.full_name = t_data["full_name"]
            profile.contact_phone = t_data["contact_phone"]
            profile.specialty = t_data["specialty"]
            profile.status = "PUBLISHED"
            profile.bio = t_data["bio"]
            profile.certifications = t_data["certifications"]
            profile.max_students = t_data["max_students"]
            profile.updated_at = now
            db.flush()

        trainer_map[t_data["key"]] = profile
        stats["trainers"] += 1

        # Paquetes del entrenador
        for p_data in t_data["plans"]:
            title = p_data["title"].strip()
            plan = db.scalar(
                select(TrainingPlan).where(
                    TrainingPlan.trainer_id == profile.id,
                    TrainingPlan.title == title,
                )
            )
            if plan is None:
                plan = TrainingPlan(
                    trainer_id=profile.id,
                    title=title,
                    description=p_data["description"],
                    monthly_price=p_data["monthly_price"],
                    currency=p_data["currency"],
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(plan)
                db.flush()
            else:
                plan.description = p_data["description"]
                plan.monthly_price = p_data["monthly_price"]
                plan.currency = p_data["currency"]
                plan.is_active = True
                plan.updated_at = now
                db.flush()

            plan_map[(t_data["key"], title)] = plan
            stats["plans"] += 1

    # 2. Sembrar Alumnos, Cuestionarios, Zonas a Proteger y Apto Médico
    for s_data in STUDENTS_DEMO_DATA:
        email = s_data["email"].strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=STUDENT_ROLE,
                is_active=True,
                failed_login_attempts=0,
                locked_until=None,
                created_at=now,
            )
            db.add(user)
            db.flush()
        else:
            user.role = STUDENT_ROLE
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            db.flush()

        user_map[s_data["key"]] = user

        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
        if profile is None:
            profile = StudentProfile(
                user_id=user.id,
                first_name=s_data["first_name"],
                last_name=s_data["last_name"],
                birth_date=s_data["birth_date"],
                contact_phone=s_data["contact_phone"],
                bio=s_data["bio"],
                fitness_goals=s_data["fitness_goals"],
                personal_motivation=s_data["personal_motivation"],
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
            db.flush()
        else:
            profile.first_name = s_data["first_name"]
            profile.last_name = s_data["last_name"]
            profile.birth_date = s_data["birth_date"]
            profile.contact_phone = s_data["contact_phone"]
            profile.bio = s_data["bio"]
            profile.fitness_goals = s_data["fitness_goals"]
            profile.personal_motivation = s_data["personal_motivation"]
            profile.status = "PUBLISHED"
            profile.updated_at = now
            db.flush()

        student_map[s_data["key"]] = profile
        stats["students"] += 1

        # Cuestionario de salud (obligatorio para matchmaking)
        q_data = s_data["questionnaire"]
        q = db.scalar(
            select(HealthQuestionnaire).where(
                HealthQuestionnaire.student_id == profile.id,
                HealthQuestionnaire.status == "CURRENT",
            )
        )
        if q is None:
            q = HealthQuestionnaire(
                student_id=profile.id,
                status="CURRENT",
                has_heart_condition=q_data["has_heart_condition"],
                has_chest_pain_activity=q_data["has_chest_pain_activity"],
                has_dizziness_or_balance_loss=q_data["has_dizziness_or_balance_loss"],
                has_bone_joint_problem=q_data["has_bone_joint_problem"],
                takes_prescription_meds=q_data["takes_prescription_meds"],
                other_medical_conditions=q_data["other_medical_conditions"],
                completed_at=now,
            )
            db.add(q)
            db.flush()
        else:
            q.has_heart_condition = q_data["has_heart_condition"]
            q.has_chest_pain_activity = q_data["has_chest_pain_activity"]
            q.has_dizziness_or_balance_loss = q_data["has_dizziness_or_balance_loss"]
            q.has_bone_joint_problem = q_data["has_bone_joint_problem"]
            q.takes_prescription_meds = q_data["takes_prescription_meds"]
            q.other_medical_conditions = q_data["other_medical_conditions"]
            db.flush()

        stats["questionnaires"] += 1

        # Zonas a proteger
        for area in s_data["protected_zones"]:
            pz = db.scalar(
                select(ProtectedZone).where(
                    ProtectedZone.student_id == profile.id,
                    ProtectedZone.body_area == area,
                )
            )
            if pz is None:
                pz = ProtectedZone(
                    student_id=profile.id,
                    body_area=area,
                    created_at=now,
                )
                db.add(pz)
                db.flush()
            stats["protected_zones"] += 1

        # Apto médico (opcional pero muy útil para la demo)
        if s_data.get("has_medical_clearance"):
            clearance_dir = UPLOADS_DIR / profile.id
            clearance_dir.mkdir(parents=True, exist_ok=True)
            clearance_file = clearance_dir / "apto_medico_demo.pdf"
            if not clearance_file.exists():
                clearance_file.write_bytes(MINIMAL_VALID_PDF)

            mc = db.scalar(
                select(MedicalClearance).where(
                    MedicalClearance.student_id == profile.id,
                    MedicalClearance.status == "CURRENT",
                )
            )
            if mc is None:
                mc = MedicalClearance(
                    student_id=profile.id,
                    file_path=str(clearance_file),
                    original_filename="apto_medico_demo.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=len(MINIMAL_VALID_PDF),
                    issue_date=date.today() - timedelta(days=30),
                    status="CURRENT",
                    created_at=now,
                )
                db.add(mc)
                db.flush()
            stats["medical_clearances"] += 1

    # 3. Sembrar Solicitudes y Vínculos
    for r_data in REQUESTS_DEMO_DATA:
        student = student_map[r_data["student_key"]]
        trainer = trainer_map[r_data["trainer_key"]]
        plan = plan_map[(r_data["trainer_key"], r_data["plan_title"])]
        req_status = r_data["status"]
        created_time = now - timedelta(days=r_data["days_ago"])
        resolved_time = now - timedelta(days=r_data["days_ago"] - 1) if req_status != "PENDING" else None

        req = db.scalar(
            select(TrainingRequest).where(
                TrainingRequest.student_id == student.id,
                TrainingRequest.trainer_id == trainer.id,
                TrainingRequest.plan_id == plan.id,
                TrainingRequest.status == req_status,
            )
        )
        if req is None:
            req = TrainingRequest(
                student_id=student.id,
                trainer_id=trainer.id,
                plan_id=plan.id,
                agreed_monthly_price=plan.monthly_price,
                agreed_currency=plan.currency,
                status=req_status,
                student_message=r_data["student_message"],
                trainer_response_message=r_data["trainer_response_message"],
                created_at=created_time,
                resolved_at=resolved_time,
            )
            db.add(req)
            db.flush()
        else:
            req.student_message = r_data["student_message"]
            req.trainer_response_message = r_data["trainer_response_message"]
            db.flush()

        stats["requests"] += 1

        # Vínculo activo si corresponde
        if "active_relationship" in r_data:
            rel_info = r_data["active_relationship"]
            rel = db.scalar(
                select(TrainingRelationship).where(
                    TrainingRelationship.student_id == student.id,
                    TrainingRelationship.trainer_id == trainer.id,
                    TrainingRelationship.status == "ACTIVE",
                )
            )
            if rel is None:
                rel = TrainingRelationship(
                    student_id=student.id,
                    trainer_id=trainer.id,
                    plan_id=plan.id,
                    agreed_monthly_price=plan.monthly_price,
                    agreed_currency=plan.currency,
                    status="ACTIVE",
                    start_date=(now - timedelta(days=rel_info["start_days_ago"])).date(),
                    welcome_message=rel_info["welcome_message"],
                    welcome_message_sent=True,
                    initial_routine_id=None,
                )
                db.add(rel)
                db.flush()
            else:
                rel.welcome_message = rel_info["welcome_message"]
                rel.welcome_message_sent = True
                db.flush()

            stats["relationships"] += 1

        # Notificación correspondiente
        if "create_notification" in r_data:
            notif_info = r_data["create_notification"]
            recipient_user = user_map[notif_info["recipient"]]
            notif = db.scalar(
                select(Notification).where(
                    Notification.recipient_id == recipient_user.id,
                    Notification.type == notif_info["type"],
                    Notification.title == notif_info["title"],
                )
            )
            if notif is None:
                notif = Notification(
                    recipient_id=recipient_user.id,
                    type=notif_info["type"],
                    title=notif_info["title"],
                    message=notif_info["message"],
                    related_entity_type="TrainingRequest" if req_status == "PENDING" else "TrainingRelationship",
                    related_entity_id=req.id,
                    is_read=False,
                    created_at=created_time,
                )
                db.add(notif)
                db.flush()
            stats["notifications"] += 1

    # 4. Sembrar Ejercicios y Rutinas (requieren los vínculos activos)
    _seed_routines(db, trainer_map, student_map, stats, now)

    db.commit()

    if verbose:
        print("\n" + "=" * 70)
        print("  SET TO SET - SEED DE DATOS DE DEMOSTRACIÓN COMPLETADO CON ÉXITO")
        print("=" * 70)
        print(f" • Entrenadores:          {stats['trainers']}")
        print(f" • Paquetes publicados:   {stats['plans']}")
        print(f" • Alumnos registrados:   {stats['students']}")
        print(f" • Cuestionarios salud:   {stats['questionnaires']}")
        print(f" • Zonas a proteger:      {stats['protected_zones']}")
        print(f" • Aptos médicos:         {stats['medical_clearances']}")
        print(f" • Solicitudes demo:      {stats['requests']}")
        print(f" • Vínculos activos:      {stats['relationships']}")
        print(f" • Notificaciones:        {stats['notifications']}")
        print(f" • Ejercicios:            {stats['exercises']}")
        print(f" • Rutinas genéricas:     {stats['routines']}")
        print(f" • Rutinas con IA:        {stats['ai_routines']}")
        print("=" * 70)

    return stats


def clean_demo_data(db: Session, verbose: bool = True) -> dict[str, int]:
    """Elimina de forma aislada y segura ÚNICAMENTE los registros de demostración.

    Identifica registros por el dominio @demo.settoset.com y preserva cualquier
    otro dato preexistente en la base de datos.
    """
    demo_users = db.scalars(select(User).where(User.email.like(f"%@{DEMO_DOMAIN}"))).all()
    user_ids = [u.id for u in demo_users]

    if not user_ids:
        if verbose:
            print("\n[i] No se encontraron datos de demo para limpiar.")
        return {"users": 0}

    # Obtener perfiles asociados
    trainer_profiles = db.scalars(
        select(TrainerProfile).where(TrainerProfile.user_id.in_(user_ids))
    ).all()
    trainer_ids = [tp.id for tp in trainer_profiles]

    student_profiles = db.scalars(
        select(StudentProfile).where(StudentProfile.user_id.in_(user_ids))
    ).all()
    student_ids = [sp.id for sp in student_profiles]

    counts = {
        "notifications": 0,
        "relationships": 0,
        "requests": 0,
        "plans": 0,
        "medical_clearances": 0,
        "protected_zones": 0,
        "health_questionnaires": 0,
        "trainer_profiles": len(trainer_ids),
        "student_profiles": len(student_ids),
        "user_sessions": 0,
        "reset_tokens": 0,
        "users": len(user_ids),
    }

    # 1. Notificaciones de usuarios demo
    for n in db.scalars(select(Notification).where(Notification.recipient_id.in_(user_ids))).all():
        db.delete(n)
        counts["notifications"] += 1

    # 2. Copias de rutina por alumno (se ubican a través del vínculo, que se borra después)
    if student_ids:
        for sr in db.scalars(
            select(StudentRoutine)
            .join(TrainingRelationship, StudentRoutine.relationship_id == TrainingRelationship.id)
            .where(TrainingRelationship.student_id.in_(student_ids))
        ).all():
            for rcl in db.scalars(
                select(RoutineChangeLog).where(RoutineChangeLog.student_routine_id == sr.id)
            ).all():
                db.delete(rcl)
            db.delete(sr)

    # 2b. Vínculos activos / históricos de demo
    if student_ids or trainer_ids:
        for rel in db.scalars(
            select(TrainingRelationship).where(
                (TrainingRelationship.student_id.in_(student_ids))
                | (TrainingRelationship.trainer_id.in_(trainer_ids))
            )
        ).all():
            db.delete(rel)
            counts["relationships"] += 1

    # 3. Solicitudes de entrenamiento de demo
    if student_ids or trainer_ids:
        for req in db.scalars(
            select(TrainingRequest).where(
                (TrainingRequest.student_id.in_(student_ids))
                | (TrainingRequest.trainer_id.in_(trainer_ids))
            )
        ).all():
            db.delete(req)
            counts["requests"] += 1

    # 4. Paquetes de entrenadores demo
    if trainer_ids:
        for plan in db.scalars(
            select(TrainingPlan).where(TrainingPlan.trainer_id.in_(trainer_ids))
        ).all():
            db.delete(plan)
            counts["plans"] += 1

    # 4b. Rutinas y ejercicios asociados a cuentas demo
    if trainer_ids or student_ids:
        for ar in db.scalars(
            select(AssignedRoutine).where(
                (AssignedRoutine.trainer_id.in_(trainer_ids))
                | (AssignedRoutine.student_id.in_(student_ids))
            )
        ).all():
            db.delete(ar)

    if trainer_ids:
        for rt in db.scalars(
            select(RoutineTemplate).where(RoutineTemplate.trainer_id.in_(trainer_ids))
        ).all():
            db.delete(rt)

        for ex in db.scalars(
            select(Exercise).where(Exercise.trainer_id.in_(trainer_ids))
        ).all():
            db.delete(ex)

    # 5. Aptos médicos de alumnos demo (y sus archivos en disco)
    if student_ids:
        for mc in db.scalars(
            select(MedicalClearance).where(MedicalClearance.student_id.in_(student_ids))
        ).all():
            file_p = Path(mc.file_path)
            if file_p.exists() and (DEMO_DOMAIN in mc.original_filename or "demo" in mc.original_filename):
                file_p.unlink(missing_ok=True)
            db.delete(mc)
            counts["medical_clearances"] += 1

        # Limpiar carpetas de aptos creadas para alumnos demo
        for sid in student_ids:
            s_dir = UPLOADS_DIR / sid
            if s_dir.exists():
                for f in s_dir.iterdir():
                    f.unlink(missing_ok=True)
                s_dir.rmdir()

    # 6. Zonas a proteger
    if student_ids:
        for pz in db.scalars(
            select(ProtectedZone).where(ProtectedZone.student_id.in_(student_ids))
        ).all():
            db.delete(pz)
            counts["protected_zones"] += 1

    # 7. Cuestionarios de salud
    if student_ids:
        for hq in db.scalars(
            select(HealthQuestionnaire).where(HealthQuestionnaire.student_id.in_(student_ids))
        ).all():
            db.delete(hq)
            counts["health_questionnaires"] += 1

    # 8. Perfiles
    for tp in trainer_profiles:
        db.delete(tp)
    for sp in student_profiles:
        db.delete(sp)

    # 9. Sesiones y reset tokens
    for s in db.scalars(select(UserSession).where(UserSession.user_id.in_(user_ids))).all():
        db.delete(s)
        counts["user_sessions"] += 1

    for rt in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids))).all():
        db.delete(rt)
        counts["reset_tokens"] += 1

    # 10. Usuarios
    for u in demo_users:
        db.delete(u)

    db.commit()

    if verbose:
        print("\n" + "=" * 70)
        print("  SET TO SET - LIMPIEZA DE DATOS DE DEMOSTRACIÓN COMPLETADA")
        print("=" * 70)
        print(f" • Usuarios eliminados:         {counts['users']}")
        print(f" • Perfiles de entrenador:      {counts['trainer_profiles']}")
        print(f" • Perfiles de alumno:          {counts['student_profiles']}")
        print(f" • Paquetes eliminados:         {counts['plans']}")
        print(f" • Solicitudes eliminadas:      {counts['requests']}")
        print(f" • Vínculos eliminados:         {counts['relationships']}")
        print(f" • Cuestionarios eliminados:    {counts['health_questionnaires']}")
        print(f" • Zonas a proteger eliminadas: {counts['protected_zones']}")
        print(f" • Aptos médicos eliminados:    {counts['medical_clearances']}")
        print(f" • Notificaciones eliminadas:   {counts['notifications']}")
        print(" [✓] Todos los datos ajenos a la demo permanecen intactos.")
        print("=" * 70)

    return counts


def print_demo_credentials() -> None:
    """Imprime una tabla formateada con las cuentas de demostración y sus credenciales."""
    print("\n" + "=" * 80)
    print("                    CREDENCIALES DE DEMOSTRACIÓN (PASSWORD: DemoPassword123!)")
    print("=" * 80)
    print(f"{'ROL':<12} | {'NOMBRE':<20} | {'CORREO ELECTRÓNICO':<35} | {'ROL / ESPECIALIDAD'}")
    print("-" * 80)
    for t in TRAINERS_DEMO_DATA:
        print(f"{'ENTRENADOR':<12} | {t['full_name']:<20} | {t['email']:<35} | {t['specialty']}")
    print("-" * 80)
    for s in STUDENTS_DEMO_DATA:
        full_name = f"{s['first_name']} {s['last_name']}"
        goals = ", ".join(s["fitness_goals"])
        print(f"{'ALUMNO':<12} | {full_name:<20} | {s['email']:<35} | Metas: {goals}")
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generador y limpiador de datos de demostración académica para Set to Set."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--clean",
        action="store_true",
        help="Elimina exclusivamente los datos de demostración (@demo.settoset.com), sin tocar datos reales.",
    )
    group.add_argument(
        "--reset",
        action="store_true",
        help="Limpia los datos de demostración y los vuelve a sembrar desde cero de forma limpia.",
    )

    args = parser.parse_args()

    # También para --clean y --reset: una base nueva todavía no tiene tablas.
    Base.metadata.create_all(bind=engine)
    apply_migrations(engine)

    db: Session = SessionLocal()
    try:
        if args.clean:
            clean_demo_data(db)
        elif args.reset:
            clean_demo_data(db)
            seed_demo_data(db)
            print_demo_credentials()
        else:
            seed_demo_data(db)
            print_demo_credentials()
    finally:
        db.close()


if __name__ == "__main__":
    main()
