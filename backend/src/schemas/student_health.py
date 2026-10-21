from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictBool


class HealthQuestionnaireInput(BaseModel):
    has_heart_condition: StrictBool
    has_chest_pain_activity: StrictBool
    has_dizziness_or_balance_loss: StrictBool
    has_bone_joint_problem: StrictBool
    takes_prescription_meds: StrictBool
    other_medical_conditions: str | None = None


class HealthQuestionnaireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    has_heart_condition: bool
    has_chest_pain_activity: bool
    has_dizziness_or_balance_loss: bool
    has_bone_joint_problem: bool
    takes_prescription_meds: bool
    other_medical_conditions: str | None
    status: str
    has_risk_answers: bool
    completed_at: datetime
