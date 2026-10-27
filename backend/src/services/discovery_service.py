import threading
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import User
from backend.src.schemas.discovery import (
    ActivePlanResponse,
    ActivePlanSummary,
    ActiveRoutineSummary,
    ActiveTrainerSummary,
    PaginatedTrainers,
    TrainerPublicDetail,
    TrainerSearchFilters,
    TrainerSearchResult,
    TrainingPlanPublic,
    TrainingRelationshipResponse,
    TrainingRequestAcceptPayload,
    TrainingRequestCreate,
    TrainingRequestDetailResponse,
    TrainingRequestRejectPayload,
    TrainingRequestResponse,
    TrainingRequestStatus,
    TrainingRequestStudentSummary,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.student_service import (
    is_questionnaire_completed,
    trainer_has_access,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)
from backend.src.services.trainer_service import (
    get_published_profile,
    has_available_quota,
    list_published_plans,
    quota_summary,
)

# Serializes request resolution in single-process / SQLite test pools alongside SQL `FOR UPDATE` row locks.
_REQUEST_RESOLUTION_LOCK = threading.Lock()


class DiscoveryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_sort_datetime(value: datetime) -> datetime:
    """Normaliza explícitamente un datetime a UTC aware según la convención temporal del proyecto."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _item_sort_datetime(item: ActivePlanResponse) -> datetime:
    if item.requested_at is not None:
        return _normalize_sort_datetime(item.requested_at)
    if item.start_date is not None:
        return datetime.combine(item.start_date, datetime.min.time(), tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def _require_student(user: User) -> None:
    if user.role != STUDENT_ROLE:
        raise DiscoveryError(status.HTTP_403_FORBIDDEN, "Esta acción está disponible solo para alumnos.")


def _require_trainer(user: User) -> None:
    if user.role != TRAINER_ROLE:
        raise DiscoveryError(status.HTTP_403_FORBIDDEN, "Esta acción está disponible solo para entrenadores.")


def _require_existing_trainer_profile(db: Session, user: User) -> TrainerProfile:
    _require_trainer(user)
    profile = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == user.id))
    if profile is None or profile.status != "PUBLISHED":
        raise DiscoveryError(
            status.HTTP_403_FORBIDDEN,
            "Debés tener un perfil de entrenador publicado para gestionar solicitudes.",
        )
    return profile


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

    # Subquery: active training relationships per trainer (eliminates N+1 quota queries)
    active_rel_agg = (
        select(
            TrainingRelationship.trainer_id,
            func.count(TrainingRelationship.id).label("active_students_count"),
        )
        .where(TrainingRelationship.status == "ACTIVE")
        .group_by(TrainingRelationship.trainer_id)
        .subquery()
    )

    active_students_expr = func.coalesce(active_rel_agg.c.active_students_count, 0)

    base = (
        select(
            TrainerProfile,
            plan_agg.c.plans_count,
            plan_agg.c.min_price,
            plan_agg.c.max_price,
            active_students_expr.label("active_students_count"),
        )
        .outerjoin(plan_agg, TrainerProfile.id == plan_agg.c.trainer_id)
        .outerjoin(active_rel_agg, TrainerProfile.id == active_rel_agg.c.trainer_id)
        .where(
            TrainerProfile.status == "PUBLISHED",
            plan_agg.c.plans_count > 0,
        )
    )

    if filters.specialty:
        escaped_specialty = (
            filters.specialty.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        base = base.where(
            TrainerProfile.specialty.ilike(f"%{escaped_specialty}%", escape="\\")
        )

    if filters.max_price is not None:
        base = base.where(plan_agg.c.min_price <= filters.max_price)

    if filters.only_available:
        base = base.where(TrainerProfile.max_students > active_students_expr)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    start = (filters.page - 1) * filters.page_size
    rows = db.execute(
        base.order_by(TrainerProfile.full_name, TrainerProfile.id)
        .offset(start)
        .limit(filters.page_size)
    ).all()

    items: list[TrainerSearchResult] = []
    for row in rows:
        profile = row.TrainerProfile
        active_students = int(row.active_students_count or 0)
        available_slots = max(profile.max_students - active_students, 0)
        bio_preview = (
            profile.bio[:BIO_PREVIEW_LENGTH] + "…"
            if profile.bio and len(profile.bio) > BIO_PREVIEW_LENGTH
            else profile.bio
        )
        items.append(
            TrainerSearchResult(
                id=profile.id,
                user_id=profile.user_id,
                full_name=profile.full_name,
                specialty=profile.specialty,
                bio_preview=bio_preview,
                min_price=float(row.min_price) if row.min_price else None,
                max_price=float(row.max_price) if row.max_price else None,
                available_slots=available_slots,
                has_available_quota=available_slots > 0,
                plans_count=row.plans_count or 0,
            )
        )

    return PaginatedTrainers(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


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

    active_rel = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.student_id == student_profile.id,
            TrainingRelationship.trainer_id == trainer_profile.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if active_rel is not None:
        raise DiscoveryError(
            status.HTTP_409_CONFLICT,
            "Ya tenés un vínculo activo con este entrenador.",
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
    student_name = " ".join(
        name for name in (student_profile.first_name, student_profile.last_name) if name
    ).strip() or "Un alumno"
    try:
        db.add(request)
        db.flush()
        create_notification(
            db=db,
            recipient_id=trainer_profile.user_id,
            type="NEW_REQUEST",
            title="¡Nueva solicitud de entrenamiento!",
            message=f"El alumno {student_name} ha solicitado unirse a tu plan {plan.title}.",
            related_entity_type="TrainingRequest",
            related_entity_id=request.id,
            commit=False,
        )
        db.commit()
        db.refresh(request)
    except IntegrityError as exc:
        db.rollback()
        err_msg = str(getattr(exc, "orig", exc))
        has_pending = (
            db.scalar(
                select(TrainingRequest.id).where(
                    TrainingRequest.student_id == student_profile.id,
                    TrainingRequest.trainer_id == trainer_profile.id,
                    TrainingRequest.status == "PENDING",
                )
            )
            is not None
        )
        if (
            has_pending
            or "uq_pending_training_request" in err_msg
            or "training_requests.student_id, training_requests.trainer_id" in err_msg
        ):
            raise DiscoveryError(
                status.HTTP_409_CONFLICT,
                "Ya tenés una solicitud pendiente con este entrenador.",
            ) from exc
        raise
    except Exception:
        db.rollback()
        raise
    return TrainingRequestResponse.model_validate(request).model_copy(
        update={"can_be_accepted": True}
    )


def list_student_requests(db: Session, user: User) -> list[TrainingRequestResponse]:
    _require_student(user)
    student_profile = get_student_profile(db, user)
    requests = db.scalars(
        select(TrainingRequest)
        .where(TrainingRequest.student_id == student_profile.id)
        .order_by(TrainingRequest.created_at.desc())
    ).all()
    return [
        TrainingRequestResponse.model_validate(r).model_copy(
            update={
                "can_be_accepted": r.status == "PENDING"
                and (has_available_quota(db, r.trainer) if r.trainer else False)
            }
        )
        for r in requests
    ]


def _to_request_response(
    request: TrainingRequest, can_accept_quota: bool
) -> TrainingRequestResponse:
    can_be_accepted = request.status == "PENDING" and can_accept_quota
    return TrainingRequestResponse.model_validate(request).model_copy(
        update={"can_be_accepted": can_be_accepted}
    )


def _to_request_detail_response(
    request: TrainingRequest,
    can_accept_quota: bool,
    include_sensitive_student_info: bool = True,
) -> TrainingRequestDetailResponse:
    base = _to_request_response(request, can_accept_quota)
    student_summary = TrainingRequestStudentSummary.model_validate(request.student)
    if not include_sensitive_student_info:
        student_summary = student_summary.model_copy(
            update={"contact_phone": None, "birth_date": None}
        )
    return TrainingRequestDetailResponse(
        **base.model_dump(),
        student=student_summary,
        plan_title=request.plan.title if request.plan is not None else None,
    )


def list_trainer_requests(
    db: Session, user: User, status_filter: TrainingRequestStatus | None = None
) -> list[TrainingRequestResponse]:
    _require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)
    can_accept_quota = has_available_quota(db, trainer_profile)

    query = select(TrainingRequest).where(TrainingRequest.trainer_id == trainer_profile.id)
    if status_filter is not None:
        query = query.where(TrainingRequest.status == status_filter)
    query = query.order_by(TrainingRequest.created_at.desc(), TrainingRequest.id.desc())

    requests = db.scalars(query).all()
    return [_to_request_response(r, can_accept_quota) for r in requests]


def get_trainer_request_detail(
    db: Session, user: User, request_id: str
) -> TrainingRequestDetailResponse:
    _require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)
    request = db.get(TrainingRequest, request_id)
    if request is None:
        raise DiscoveryError(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada.")
    if request.trainer_id != trainer_profile.id:
        raise DiscoveryError(
            status.HTTP_403_FORBIDDEN,
            "No autorizado para consultar esta solicitud.",
        )
    can_accept_quota = has_available_quota(db, trainer_profile)
    include_sensitive = trainer_has_access(db, user, request.student_id)
    return _to_request_detail_response(
        request, can_accept_quota, include_sensitive_student_info=include_sensitive
    )


def accept_training_request(
    db: Session,
    user: User,
    request_id: str,
    payload: TrainingRequestAcceptPayload | None = None,
) -> TrainingRelationshipResponse:
    with _REQUEST_RESOLUTION_LOCK:
        trainer_profile = _require_existing_trainer_profile(db, user)

        # Acquire row-level lock on trainer profile and request (PostgreSQL FOR UPDATE)
        locked_trainer = db.scalar(
            select(TrainerProfile)
            .where(TrainerProfile.id == trainer_profile.id)
            .with_for_update()
        )
        request = db.scalar(
            select(TrainingRequest)
            .where(TrainingRequest.id == request_id)
            .with_for_update()
        )

        if request is None:
            db.rollback()
            raise DiscoveryError(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada.")
        if request.trainer_id != locked_trainer.id:
            db.rollback()
            raise DiscoveryError(
                status.HTTP_403_FORBIDDEN,
                "No autorizado para gestionar esta solicitud.",
            )
        if request.status != "PENDING":
            db.rollback()
            raise DiscoveryError(
                status.HTTP_409_CONFLICT,
                "La solicitud ya fue procesada.",
            )
        if not has_available_quota(db, locked_trainer):
            db.rollback()
            raise DiscoveryError(
                status.HTTP_409_CONFLICT,
                "Cupos agotados; libere un cupo para poder aceptar.",
            )

        student_id = request.student_id
        trainer_id = locked_trainer.id

        existing_active = db.scalar(
            select(TrainingRelationship).where(
                TrainingRelationship.student_id == student_id,
                TrainingRelationship.trainer_id == trainer_id,
                TrainingRelationship.status == "ACTIVE",
            )
        )
        if existing_active is not None:
            db.rollback()
            raise DiscoveryError(
                status.HTTP_409_CONFLICT,
                "La solicitud ya fue procesada.",
            )

        now = utc_now()
        welcome_msg = (
            payload.welcome_message.strip()
            if payload and payload.welcome_message and payload.welcome_message.strip()
            else None
        )

        try:
            request.status = "ACCEPTED"
            request.trainer_response_message = welcome_msg
            request.resolved_at = now

            relationship = TrainingRelationship(
                student_id=student_id,
                trainer_id=trainer_id,
                plan_id=request.plan_id,
                agreed_monthly_price=request.agreed_monthly_price,
                agreed_currency=request.agreed_currency,
                status="ACTIVE",
                start_date=now.date(),
                welcome_message=welcome_msg,
                welcome_message_sent=True,
                initial_routine_id=None,
            )
            db.add(relationship)
            db.flush()

            # Emit welcome notification to the student (US-49)
            student_profile = db.get(StudentProfile, student_id)
            plan = db.get(TrainingPlan, request.plan_id)
            plan_name = plan.title if plan else "Plan de entrenamiento"
            trainer_name = locked_trainer.full_name or "tu entrenador"
            notification_body = (
                welcome_msg
                if welcome_msg
                else f"¡Bienvenido al programa! Tu entrenador {trainer_name} ha confirmado tu solicitud para el plan {plan_name}. Ya pueden comenzar a entrenar."
            )
            if student_profile:
                create_notification(
                    db=db,
                    recipient_id=student_profile.user_id,
                    type="TRAINING_ACCEPTED",
                    title="¡Bienvenido/a al programa de entrenamiento!",
                    message=notification_body,
                    related_entity_type="TrainingRelationship",
                    related_entity_id=relationship.id,
                    commit=False,
                )

            db.commit()
            db.refresh(relationship)
            return TrainingRelationshipResponse.model_validate(relationship)
        except IntegrityError as exc:
            db.rollback()
            err_msg = str(getattr(exc, "orig", exc))
            has_active = (
                db.scalar(
                    select(TrainingRelationship.id).where(
                        TrainingRelationship.student_id == student_id,
                        TrainingRelationship.trainer_id == trainer_id,
                        TrainingRelationship.status == "ACTIVE",
                    )
                )
                is not None
            )
            if (
                has_active
                or "uq_active_training_relationship" in err_msg
                or "training_relationships.student_id, training_relationships.trainer_id" in err_msg
            ):
                raise DiscoveryError(
                    status.HTTP_409_CONFLICT,
                    "La solicitud ya fue procesada.",
                ) from exc
            raise
        except Exception:
            db.rollback()
            raise


def reject_training_request(
    db: Session,
    user: User,
    request_id: str,
    payload: TrainingRequestRejectPayload | None = None,
) -> TrainingRequestResponse:
    with _REQUEST_RESOLUTION_LOCK:
        trainer_profile = _require_existing_trainer_profile(db, user)

        request = db.scalar(
            select(TrainingRequest)
            .where(TrainingRequest.id == request_id)
            .with_for_update()
        )
        if request is None:
            db.rollback()
            raise DiscoveryError(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada.")
        if request.trainer_id != trainer_profile.id:
            db.rollback()
            raise DiscoveryError(
                status.HTTP_403_FORBIDDEN,
                "No autorizado para gestionar esta solicitud.",
            )
        if request.status != "PENDING":
            db.rollback()
            raise DiscoveryError(
                status.HTTP_409_CONFLICT,
                "La solicitud ya fue procesada.",
            )

        reason = (
            payload.rejection_reason.strip()
            if payload and payload.rejection_reason and payload.rejection_reason.strip()
            else None
        )
        try:
            request.status = "REJECTED"
            request.trainer_response_message = reason
            request.resolved_at = utc_now()
            db.commit()
            db.refresh(request)
            return _to_request_response(request, can_accept_quota=False)
        except Exception:
            db.rollback()
            raise


def get_student_active_plans(db: Session, user: User) -> list[ActivePlanResponse]:
    _require_student(user)
    student_profile = get_student_profile(db, user)

    rels = db.scalars(
        select(TrainingRelationship)
        .where(
            TrainingRelationship.student_id == student_profile.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(TrainingRelationship.start_date.desc())
    ).all()

    items: list[ActivePlanResponse] = []
    for rel in rels:
        trainer_profile = db.get(TrainerProfile, rel.trainer_id)
        trainer_user = db.get(User, trainer_profile.user_id) if trainer_profile else None
        plan = db.get(TrainingPlan, rel.plan_id)

        routine = None
        if rel.initial_routine_id:
            routine = ActiveRoutineSummary(
                id=rel.initial_routine_id,
                name="Rutina Inicial",
                status="PUBLISHED",
                is_available=True,
            )

        trainer_summary = (
            ActiveTrainerSummary(
                id=trainer_profile.id,
                full_name=trainer_profile.full_name,
                specialty=trainer_profile.specialty,
                profile_picture_url=None,
                email=trainer_user.email if trainer_user else None,
                phone=trainer_profile.contact_phone,
            )
            if trainer_profile
            else None
        )

        plan_summary = ActivePlanSummary(id=plan.id, title=plan.title) if plan else None

        items.append(
            ActivePlanResponse(
                has_active_plan=True,
                relationship_id=rel.id,
                status=rel.status,
                start_date=rel.start_date,
                agreed_monthly_price=float(rel.agreed_monthly_price),
                agreed_currency=rel.agreed_currency,
                welcome_message=rel.welcome_message,
                trainer=trainer_summary,
                plan=plan_summary,
                routine=routine,
            )
        )

    pending_requests = db.scalars(
        select(TrainingRequest)
        .where(
            TrainingRequest.student_id == student_profile.id,
            TrainingRequest.status == "PENDING",
        )
        .order_by(TrainingRequest.created_at.desc(), TrainingRequest.id.desc())
    ).all()
    for request in pending_requests:
        trainer_profile = db.get(TrainerProfile, request.trainer_id)
        plan = db.get(TrainingPlan, request.plan_id)

        # H-03 / Paso 3: no exponer email ni teléfono privado del entrenador mientras esté PENDING
        trainer_summary = (
            ActiveTrainerSummary(
                id=trainer_profile.id,
                full_name=trainer_profile.full_name,
                specialty=trainer_profile.specialty,
                profile_picture_url=None,
                email=None,
                phone=None,
            )
            if trainer_profile
            else None
        )
        plan_summary = ActivePlanSummary(id=plan.id, title=plan.title) if plan else None

        items.append(
            ActivePlanResponse(
                has_active_plan=False,
                request_id=request.id,
                status="PENDING",
                requested_at=request.created_at,
                agreed_monthly_price=float(request.agreed_monthly_price),
                agreed_currency=request.agreed_currency,
                trainer=trainer_summary,
                plan=plan_summary,
            )
        )

    items.sort(key=_item_sort_datetime, reverse=True)
    return items


def get_student_active_plan(db: Session, user: User) -> ActivePlanResponse:
    plans = get_student_active_plans(db, user)
    return next(
        (plan for plan in plans if plan.has_active_plan),
        ActivePlanResponse(has_active_plan=False),
    )
