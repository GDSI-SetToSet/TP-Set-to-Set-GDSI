export type StudentProfileStatus = 'DRAFT' | 'PUBLISHED';

export const FITNESS_GOALS = {
  fuerza: 'Fuerza',
  hipertrofia: 'Hipertrofia',
  resistencia: 'Resistencia',
  perdida_de_peso: 'Pérdida de peso',
  salud_general: 'Salud general',
  movilidad_rehabilitacion: 'Movilidad/rehabilitación',
} as const;

export type FitnessGoal = keyof typeof FITNESS_GOALS;

export interface StudentProfile {
  id: string;
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  contact_phone: string | null;
  profile_picture: string | null;
  bio: string | null;
  fitness_goals: FitnessGoal[];
  personal_motivation: string | null;
  health_questionnaire_completed: boolean;
  status: StudentProfileStatus;
  created_at: string;
  updated_at: string;
}

export type StudentProfileUpdate = Partial<Pick<
  StudentProfile,
  'first_name' | 'last_name' | 'birth_date' | 'contact_phone' | 'profile_picture' | 'bio' | 'fitness_goals' | 'personal_motivation'
>>;

export const HEALTH_QUESTIONS = {
  has_heart_condition: '¿Te dijeron alguna vez que tenés una afección cardíaca?',
  has_chest_pain_activity: '¿Sentís dolor en el pecho cuando hacés actividad física?',
  has_dizziness_or_balance_loss: '¿Tenés mareos o perdés el equilibrio?',
  has_bone_joint_problem: '¿Tenés algún problema óseo o articular que empeore con el ejercicio?',
  takes_prescription_meds: '¿Tomás medicamentos recetados para la presión o el corazón?',
} as const;

export type HealthQuestionKey = keyof typeof HEALTH_QUESTIONS;

export interface HealthQuestionnaireInput extends Record<HealthQuestionKey, boolean> {
  other_medical_conditions?: string | null;
}

export interface HealthQuestionnaire extends HealthQuestionnaireInput {
  id: string;
  status: 'CURRENT' | 'ARCHIVED';
  has_risk_answers: boolean;
  completed_at: string;
}

export interface ProtectedZone {
  id: string;
  body_area: string;
  created_at: string;
}

export interface ProtectedZonesResponse {
  zones: ProtectedZone[];
}
