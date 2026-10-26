import type { FitnessGoal } from './student';

export type TrainingRequestStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'CANCELLED';
export type TrainingRelationshipStatus = 'ACTIVE' | 'EXPIRED' | 'TERMINATED';

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
  status: TrainingRequestStatus;
  can_be_accepted: boolean;
  student_message: string | null;
  trainer_response_message: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface TrainingRequestStudentSummary {
  id: string;
  first_name: string | null;
  last_name: string | null;
  contact_phone: string | null;
  birth_date: string | null;
}

export interface TrainingRequestDetailResponse extends TrainingRequestResponse {
  student: TrainingRequestStudentSummary;
  plan_title: string | null;
}

export interface StudentGoalsSummary {
  fitness_goals: FitnessGoal[];
  personal_motivation: string | null;
}

export interface TrainingRequestAcceptPayload {
  welcome_message?: string | null;
}

export interface TrainingRequestRejectPayload {
  rejection_reason?: string | null;
}

export interface TrainingRelationshipResponse {
  id: string;
  student_id: string;
  trainer_id: string;
  plan_id: string;
  agreed_monthly_price: number;
  agreed_currency: string;
  status: TrainingRelationshipStatus;
  start_date: string;
}

export interface ActiveTrainerSummary {
  id: string;
  full_name: string | null;
  specialty: string | null;
  profile_picture_url?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface ActivePlanSummary {
  id: string;
  title: string;
}

export interface ActiveRoutineSummary {
  id: string;
  name: string;
  status: string;
  is_available: boolean;
}

export interface ActivePlanResponse {
  has_active_plan: boolean;
  relationship_id?: string | null;
  status?: TrainingRelationshipStatus | null;
  start_date?: string | null;
  agreed_monthly_price?: number | null;
  agreed_currency?: string | null;
  welcome_message?: string | null;
  trainer?: ActiveTrainerSummary | null;
  plan?: ActivePlanSummary | null;
  routine?: ActiveRoutineSummary | null;
}

export type ActivePlansResponse = ActivePlanResponse[];

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}
