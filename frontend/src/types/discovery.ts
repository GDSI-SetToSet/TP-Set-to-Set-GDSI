export interface TrainerSearchResult {
  id: string;
  user_id: string;
  full_name: string | null;
  specialty: string | null;
  bio_preview: string | null;
  min_price: number | null;
  max_price: number | null;
  available_slots: number;
  has_available_quota: boolean;
  plans_count: number;
}

export interface TrainingPlanPublic {
  id: string;
  title: string;
  description: string | null;
  monthly_price: number;
  currency: string;
}

export interface TrainerPublicDetail {
  id: string;
  user_id: string;
  full_name: string | null;
  specialty: string | null;
  bio: string | null;
  certifications: string | null;
  max_students: number;
  available_slots: number;
  has_available_quota: boolean;
  plans: TrainingPlanPublic[];
}

export interface TrainerSearchFilters {
  specialty?: string;
  max_price?: number;
  only_available?: boolean;
  page?: number;
  page_size?: number;
}

export interface PaginatedTrainers {
  items: TrainerSearchResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface TrainingRequestCreate {
  trainer_id: string;
  plan_id: string;
  student_message?: string | null;
}

export interface TrainingRequestResponse {
  id: string;
  student_id: string;
  trainer_id: string;
  plan_id: string;
  agreed_monthly_price: number;
  agreed_currency: string;
  status: string;
  student_message: string | null;
  created_at: string;
}
