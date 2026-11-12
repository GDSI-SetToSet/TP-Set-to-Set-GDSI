export interface TrainerStudentListItem {
  relationship_id: string;
  student_id: string;
  full_name: string;
  profile_status: string;
  package_title: string | null;
  routine_name: string | null;
  has_activity: boolean;
  unreviewed_alert_count: number | null;
}

export interface TrainerStudentDetail {
  relationship: {
    id: string;
    status: string;
    start_date: string;
    package_title: string | null;
    agreed_monthly_price: number;
    agreed_currency: string;
  };
  profile: {
    id: string;
    first_name: string | null;
    last_name: string | null;
    birth_date: string | null;
    contact_phone: string | null;
    profile_picture: string | null;
    bio: string | null;
    status: string;
  };
  goals: {
    fitness_goals: string[];
    personal_motivation: string | null;
  };
  limitations: {
    protected_zones: string[];
    safety_indicators: string[];
  };
  routine: {
    id: string;
    name: string;
    source: string;
  } | null;
  metrics: {
    finished_sessions: number;
    last_session_at: string | null;
    logged_sets: number;
    last_rpe: number | null;
    last_tonnage_kg: number | null;
  };
  available_existing_views: Record<string, boolean | string>;
}

export type DailyRoutineStatus = 'NOT_STARTED' | 'TRAINING' | 'FINISHED';

export interface DailyRoutineSet {
  set_number: number;
  reps_completed: string;
  weight_kg: number | null;
  duration_seconds: number | null;
  recorded_at: string;
}

export interface DailyRoutineExercise {
  exercise_id: string;
  exercise_name: string;
  sets: DailyRoutineSet[];
}

export interface DailyRoutineSession {
  id: string;
  day_name: string;
  modality: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  rpe: number | null;
}

export interface DailyRoutineItem {
  relationship_id: string;
  student_id: string;
  student_name: string;
  routine_name: string | null;
  status: DailyRoutineStatus;
  session: DailyRoutineSession | null;
  exercises: DailyRoutineExercise[];
}
