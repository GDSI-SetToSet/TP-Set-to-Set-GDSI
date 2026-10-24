from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import User
from backend.src.schemas.discovery import (
    PaginatedTrainers,
    TrainerPublicDetail,
    TrainerSearchFilters,
    TrainerSearchResult,
    TrainingPlanPublic,
    TrainingRequestCreate,
    TrainingRequestResponse,
)
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.student_service import (
    is_questionnaire_completed,
)
from backend.src.services.trainer_service import (
    get_published_profile,
    has_available_quota,
    list_published_plans,
    quota_summary,
)


class DiscoveryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_student(user: User) -> None:
    if user.role != STUDENT_ROLE:
        raise DiscoveryError(status.HTTP_403_FORBIDDEN, "Esta acción está disponible solo para alumnos.")


BIO_PREVIEW_LENGTH = 200


def search_trainers(db: Session, filters: TrainerSearchFilters) -> PaginatedTrainers:
    # Subquery: active plan aggregations per trainer
    plan_agg = (
        select(
            TrainingPlan.trainer_id,
            func.count(TrainingPlan.id).label("plans_count"),
            func.min(TrainingPlan.monthly_price).label("min_price"),
            func.max(TrainingPlan.monthly_price).label("max_price"),
        )
        .where(TrainingPlan.is_active.is_(True))
        .group_by(TrainingPlan.trainer_id)
        .subquery()
    )

    base = (
        select(
            TrainerProfile.id,
            TrainerProfile.user_id,
            TrainerProfile.full_name,
            TrainerProfile.specialty,
            TrainerProfile.bio,
            TrainerProfile.max_students,
            plan_agg.c.plans_count,
            plan_agg.c.min_price,
            plan_agg.c.max_price,
        )
        .outerjoin(plan_agg, TrainerProfile.id == plan_agg.c.trainer_id)
        .where(
            TrainerProfile.status == "PUBLISHED",
            plan_agg.c.plans_count > 0,
        )
    )

    if filters.specialty:
        base = base.where(TrainerProfile.specialty.ilike(f"%{filters.specialty}%"))

    if filters.max_price is not None:
        base = base.where(plan_agg.c.min_price <= filters.max_price)

    # Get total before pagination
    count_query = select(func.count()).select_from(base.subquery())
    total = db.scalar(count_query) or 0

    rows = db.execute(
        base.order_by(TrainerProfile.full_name).offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    ).all()

    items: list[TrainerSearchResult] = []
    for row in rows:
        qs = quota_summary(db, db.get(TrainerProfile, row.id))
        if filters.only_available and not qs["has_available_quota"]:
            continue
        bio_preview = row.bio[:BIO_PREVIEW_LENGTH] + "…" if row.bio and len(row.bio) > BIO_PREVIEW_LENGTH else row.bio
        items.append(
            TrainerSearchResult(
                id=row.id,
                user_id=row.user_id,
                full_name=row.full_name,
                specialty=row.specialty,
                bio_preview=bio_preview,
                min_price=float(row.min_price) if row.min_price else None,
                max_price=float(row.max_price) if row.max_price else None,
                available_slots=qs["available_slots"],
                has_available_quota=qs["has_available_quota"],
                plans_count=row.plans_count or 0,
            )
        )

    return PaginatedTrainers(items=items, total=total, page=filters.page, page_size=filters.page_size)


def get_public_detail(db: Session, trainer_id: str) -> TrainerPublicDetail:
    profile = get_published_profile(db, trainer_id)
    plans = list_published_plans(db, trainer_id)
    qs = quota_summary(db, profile)
    return TrainerPublicDetail(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name,
        specialty=profile.specialty,
        bio=profile.bio,
        certifications=profile.certifications,
        max_students=profile.max_students,
        available_slots=qs["available_slots"],
        has_available_quota=qs["has_available_quota"],
        plans=[TrainingPlanPublic.model_validate(p) for p in plans],
    )


def create_training_request(
    db: Session, user: User, payload: TrainingRequestCreate
) -> TrainingRequestResponse:
    _require_student(user)
    student_profile = get_student_profile(db, user)

    # FR-005: health questionnaire must be completed
    if not is_questionnaire_completed(db, student_profile):
        raise DiscoveryError(
            status.HTTP_403_FORBIDDEN,
            "Debés completar el cuestionario de salud antes de enviar una solicitud.",
        )

    # Validate trainer exists and is PUBLISHED
    trainer_profile = db.get(TrainerProfile, payload.trainer_id)
    if trainer_profile is None or trainer_profile.status != "PUBLISHED":
        raise DiscoveryError(status.HTTP_404_NOT_FOUND, "Entrenador no encontrado.")

    # Validate plan exists, is active and belongs to trainer
    plan = db.get(TrainingPlan, payload.plan_id)
    if plan is None or not plan.is_active or plan.trainer_id != trainer_profile.id:
        raise DiscoveryError(status.HTTP_404_NOT_FOUND, "Paquete no encontrado o no disponible.")

    # No duplicate pending request from same student to same trainer
    existing = db.scalar(
        select(TrainingRequest).where(
            TrainingRequest.student_id == student_profile.id,
            TrainingRequest.trainer_id == trainer_profile.id,
            TrainingRequest.status == "PENDING",
        )
    )
    if existing is not None:
        raise DiscoveryError(
            status.HTTP_409_CONFLICT,
            "Ya tenés una solicitud pendiente con este entrenador.",
        )

    # Check quota
    if not has_available_quota(db, trainer_profile):
        raise DiscoveryError(
            status.HTTP_409_CONFLICT,
            "Este entrenador no tiene cupos disponibles.",
        )

    request = TrainingRequest(
        student_id=student_profile.id,
        trainer_id=trainer_profile.id,
        plan_id=plan.id,
        agreed_monthly_price=plan.monthly_price,
        agreed_currency=plan.currency,
        status="PENDING",
        student_message=payload.student_message,
        created_at=utc_now(),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return TrainingRequestResponse.model_validate(request)


def list_student_requests(db: Session, user: User) -> list[TrainingRequestResponse]:
    _require_student(user)
    student_profile = get_student_profile(db, user)
    requests = db.scalars(
        select(TrainingRequest)
        .where(TrainingRequest.student_id == student_profile.id)
        .order_by(TrainingRequest.created_at.desc())
    ).all()
    return [TrainingRequestResponse.model_validate(r) for r in requests]
