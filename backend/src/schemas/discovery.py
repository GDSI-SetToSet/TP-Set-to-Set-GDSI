from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TrainingRequestStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "CANCELLED"]
TrainingRelationshipStatus = Literal["ACTIVE", "EXPIRED", "TERMINATED"]


class TrainerSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str | None
    specialty: str | None
    bio_preview: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    available_slots: int = 0
    has_available_quota: bool = False
    plans_count: int = 0


class TrainerPublicDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str | None
    specialty: str | None
    bio: str | None
    certifications: str | None
    max_students: int
    available_slots: int = 0
    has_available_quota: bool = False
    plans: list["TrainingPlanPublic"] = []


class TrainingPlanPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    monthly_price: float
    currency: str


class TrainerSearchFilters(BaseModel):
    specialty: str | None = None
    max_price: float | None = Field(default=None, ge=0)
    only_available: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class PaginatedTrainers(BaseModel):
    items: list[TrainerSearchResult]
    total: int
    page: int
    page_size: int


class TrainingRequestCreate(BaseModel):
    trainer_id: str
    plan_id: str
    student_message: str | None = None


class TrainingRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    trainer_id: str
    plan_id: str
    agreed_monthly_price: float
    agreed_currency: str
    status: str
    can_be_accepted: bool = False
    student_message: str | None = None
    trainer_response_message: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class TrainingRequestStudentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str | None = None
    last_name: str | None = None
    contact_phone: str | None = None
    birth_date: datetime | None = None


class TrainingRequestDetailResponse(TrainingRequestResponse):
    student: TrainingRequestStudentSummary
    plan_title: str | None = None


class TrainerInboxFilters(BaseModel):
    status: TrainingRequestStatus | None = None


class TrainingRequestAcceptPayload(BaseModel):
    welcome_message: str | None = None


class TrainingRequestRejectPayload(BaseModel):
    rejection_reason: str | None = None


class TrainingRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    trainer_id: str
    plan_id: str
    agreed_monthly_price: float
    agreed_currency: str
    status: TrainingRelationshipStatus
    start_date: date


class ActiveTrainerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str | None
    specialty: str | None
    profile_picture_url: str | None = None
    email: str | None = None
    phone: str | None = None


class ActivePlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str


class ActiveRoutineSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str = "PUBLISHED"
    is_available: bool = True


class ActivePlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    has_active_plan: bool
    relationship_id: str | None = None
    status: TrainingRelationshipStatus | None = None
    start_date: date | None = None
    agreed_monthly_price: float | None = None
    agreed_currency: str | None = None
    welcome_message: str | None = None
    trainer: ActiveTrainerSummary | None = None
    plan: ActivePlanSummary | None = None
    routine: ActiveRoutineSummary | None = None


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    message: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    is_read: bool = False
    created_at: datetime
    read_at: datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    total: int
    unread_count: int
