from datetime import datetime

from backend.src.core.database import Base
from backend.src.models.user import new_id
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column


class HealthQuestionnaire(Base):
    __tablename__ = "health_questionnaires"
    __table_args__ = (
        Index(
            "uq_health_questionnaires_current",
            "student_id",
            unique=True,
            sqlite_where=text("status = 'CURRENT'"),
            postgresql_where=text("status = 'CURRENT'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="CURRENT", nullable=False)
    has_heart_condition: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_chest_pain_activity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_dizziness_or_balance_loss: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_bone_joint_problem: Mapped[bool] = mapped_column(Boolean, nullable=False)
    takes_prescription_meds: Mapped[bool] = mapped_column(Boolean, nullable=False)
    other_medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def has_risk_answers(self) -> bool:
        return any(
            (
                self.has_heart_condition,
                self.has_chest_pain_activity,
                self.has_dizziness_or_balance_loss,
                self.has_bone_joint_problem,
                self.takes_prescription_meds,
            )
        )
