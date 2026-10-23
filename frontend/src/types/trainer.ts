export type TrainerProfileStatus = 'DRAFT' | 'PUBLISHED';

export interface TrainerProfile {
  id: string;
  user_id: string;
  full_name: string | null;
  contact_phone: string | null;
  specialty: string | null;
  status: TrainerProfileStatus;
  bio: string | null;
  certifications: string | null;
  max_students: number;
  active_students_count: number;
  available_slots: number;
  created_at: string;
  updated_at: string;
}

export type TrainerProfileUpdate = Partial<Pick<
  TrainerProfile,
  'full_name' | 'contact_phone' | 'specialty' | 'bio' | 'certifications'
>>;

export interface TrainingPlan {
  id: string;
  trainer_id: string;
  title: string;
  description: string | null;
  monthly_price: number;
  currency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TrainingPlanInput {
  title: string;
  description: string | null;
  monthly_price: number;
}
