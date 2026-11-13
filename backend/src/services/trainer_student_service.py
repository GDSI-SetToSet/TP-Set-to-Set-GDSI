from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.trainer_student import (
    TrainerStudentDetail,
    TrainerStudentGoals,
    TrainerStudentLimitations,
    TrainerStudentListItem,
    TrainerStudentMetrics,
    TrainerStudentProfile,
    TrainerStudentRelationship,
    TrainerStudentRoutine,
)
from backend.src.services.routine_template_service import (
    RoutineTemplateError,
    list_routine_assignments,
)
from backend.src.services.session_summary_service import session_tonnage
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
)


class TrainerStudentError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        self.errors = None
        super().__init__(detail)


def _trainer_profile(db: Session, user: User) -> TrainerProfile:
    try:
        return get_or_create_profile(db, user)
    except TrainerProfileError as error:
        raise TrainerStudentError(error.status_code, error.detail) from error


def _active_relationship(
    db: Session, trainer_profile_id: str, student_id: str
) -> TrainingRelationship:
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer_profile_id,
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if relationship is None:
        raise TrainerStudentError(404, "No se encontró un vínculo activo con ese alumno.")
    return relationship


def _assignment_map(db: Session, user: User) -> dict[str, dict[str, str | int | None]]:
    try:
        assignments = list_routine_assignments(db, user)
    except RoutineTemplateError as error:
        raise TrainerStudentError(error.status_code, error.detail) from error
    return {str(item["relationship_id"]): item for item in assignments}


def list_trainer_students(db: Session, user: User) -> list[TrainerStudentListItem]:
    from backend.src.services.abandonment_risk_service import list_abandonment_risk

    trainer = _trainer_profile(db, user)
    rows = db.execute(
        select(TrainingRelationship, StudentProfile, User)
        .join(StudentProfile, TrainingRelationship.student_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(StudentProfile.last_name, StudentProfile.first_name, TrainingRelationship.id)
    ).all()
    assignments = _assignment_map(db, user)
    risks = list_abandonment_risk(db, user, notify=False)
    risk_order = {item.relationship_id: index for index, item in enumerate(risks) if item.at_risk}
    result: list[TrainerStudentListItem] = []
    for relationship, student, student_user in rows:
        sessions = db.scalar(
            select(WorkoutSession.id)
            .where(
                WorkoutSession.relationship_id == relationship.id,
                WorkoutSession.finished_at.is_not(None),
            )
            .limit(1)
        )
        assignment = assignments.get(relationship.id, {})
        result.append(
            TrainerStudentListItem(
                relationship_id=relationship.id,
                student_id=student.id,
                full_name=" ".join(
                    part for part in (student.first_name, student.last_name) if part
                ).strip()
                or student_user.email,
                profile_status=student.status,
                package_title=relationship.plan.title if relationship.plan else None,
                routine_name=assignment.get("routine_name"),
                has_activity=sessions is not None,
            )
        )
    result.sort(
        key=lambda item: (0, risk_order[item.relationship_id])
        if item.relationship_id in risk_order
        else (1, 0)
    )
    return result


def get_trainer_student_detail(
    db: Session, user: User, student_id: str
) -> TrainerStudentDetail:
    trainer = _trainer_profile(db, user)
    relationship = _active_relationship(db, trainer.id, student_id)
    profile = db.get(StudentProfile, student_id)
    if profile is None:
        raise TrainerStudentError(404, "No se encontró el alumno.")

    sessions = list(
        db.scalars(
            select(WorkoutSession)
            .where(
                WorkoutSession.relationship_id == relationship.id,
                WorkoutSession.student_id == student_id,
                WorkoutSession.finished_at.is_not(None),
            )
            .order_by(WorkoutSession.started_at.desc(), WorkoutSession.id.desc())
        )
    )
    logs = list(
        db.scalars(
            select(WorkoutSetLog).where(
                WorkoutSetLog.relationship_id == relationship.id,
                WorkoutSetLog.student_id == student_id,
            )
        )
    )
    latest_session = sessions[0] if sessions else None
    latest_logs = (
        [log for log in logs if log.session_id == latest_session.id]
        if latest_session is not None
        else []
    )
    assignment = _assignment_map(db, user).get(relationship.id, {})
    routine_id = assignment.get("routine_template_id")
    routine_name = assignment.get("routine_name")

    return TrainerStudentDetail(
        relationship=TrainerStudentRelationship(
            id=relationship.id,
            status=relationship.status,
            start_date=relationship.start_date,
            package_title=relationship.plan.title if relationship.plan else None,
            agreed_monthly_price=float(relationship.agreed_monthly_price),
            agreed_currency=relationship.agreed_currency,
        ),
        profile=TrainerStudentProfile(
            id=profile.id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            birth_date=profile.birth_date,
            contact_phone=profile.contact_phone,
            profile_picture=profile.profile_picture,
            bio=profile.bio,
            status=profile.status,
        ),
        goals=TrainerStudentGoals(
            fitness_goals=profile.fitness_goals,
            personal_motivation=profile.personal_motivation,
        ),
        limitations=TrainerStudentLimitations(
            protected_zones=[zone.body_area for zone in profile.protected_zones],
            safety_indicators=[],
        ),
        routine=(
            TrainerStudentRoutine(
                id=str(routine_id),
                name=str(routine_name),
                source="assignment",
            )
            if routine_id and routine_name
            else None
        ),
        metrics=TrainerStudentMetrics(
            finished_sessions=len(sessions),
            last_session_at=latest_session.started_at if latest_session else None,
            logged_sets=len(logs),
            last_rpe=latest_session.rpe if latest_session else None,
            last_tonnage_kg=round(session_tonnage(latest_logs), 2) if latest_session else None,
        ),
        available_existing_views={
            "relationship_id": relationship.id,
            "routine_assignments": True,
            "workout_sessions": True,
            "workout_logs": True,
            "body_map_reports": True,
        },
    )
