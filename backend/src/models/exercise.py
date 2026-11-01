from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class VideoPlatform(str, Enum):
    YOUTUBE = "YOUTUBE"
    VIMEO = "VIMEO"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    NONE = "NONE"


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trainer_id: Mapped[str] = mapped_column(
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    target_muscle_group: Mapped[str] = mapped_column(String(100), nullable=False)
    equipment_needed: Mapped[str] = mapped_column(String(150), nullable=False)
    has_no_materials_alternative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contraindicated_zones: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_platform: Mapped[VideoPlatform] = mapped_column(
        SqlEnum(VideoPlatform, name="video_platform"), default=VideoPlatform.NONE, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
