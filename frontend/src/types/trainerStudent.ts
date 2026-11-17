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

export interface PlannedMetrics {
  sets: number;
  reps: string;
  target_weight_kg: number | null;
}

export interface PerformedMetrics {
  sets_completed: number;
  reps: string[];
  max_weight_kg: number | null;
  volume_kg: number;
  total_duration_seconds: number | null;
}

export interface ExerciseComparison {
  exercise_id: string;
  exercise_name: string;
  replaced_exercise_name: string | null;
  planned: PlannedMetrics | null;
  performed: PerformedMetrics | null;
  previous: PerformedMetrics | null;
}

/** US-24: sesión finalizada vs lo planificado y vs la sesión previa del mismo día de rutina. */
export interface SessionComparison {
  session: DailyRoutineSession;
  previous_session: DailyRoutineSession | null;
  planned_duration_seconds: number | null;
  volume_kg: number;
  previous_volume_kg: number | null;
  exercises: ExerciseComparison[];
}

export interface AbandonmentRiskItem {
  relationship_id: string;
  student_id: string;
  student_name: string;
  at_risk: boolean;
  reason: 'MISSED_TRAININGS' | 'INACTIVE_TWO_WEEKS' | null;
  weekly_trainings: number;
  days_without_report: number;
  missed_trainings: number;
  last_report_at: string | null;
}

export type EvolutionGrouping = 'session' | 'week';
export type EvolutionPeriod = '4w' | '12w' | 'all';
export type TrafficLight = 'green' | 'yellow' | 'red' | null;
export type ExerciseStatus = 'progressing' | 'stalled' | 'declined' | 'unchanged' | 'few_data' | 'no_metric';
export type EffortMessageKey =
  | 'excessive_effort'
  | 'fatigue'
  | 'room_for_more'
  | 'progressing_effort_rising'
  | 'progressing_with_margin';

export interface SetResult { weight: number | null; reps: number | null }

export interface ExercisePoint {
  key: string;
  period_start: string;
  period_end: string;
  weight: number | null;
  reps: number | null;
  target_weight: number | null;
  rpe: number | null;
  is_pr: boolean;
  is_partial: boolean;
}

export interface ExerciseProgress {
  exercise_id: string;
  name: string;
  muscle_group: string;
  metric: 'max_weight' | 'max_reps' | 'none';
  start: SetResult | null;
  current: SetResult | null;
  change_pct: number | null;
  last_improvement: { date: string; is_pr: boolean } | null;
  status: ExerciseStatus;
  points: ExercisePoint[];
}

export interface AdherenceWeek {
  period_start: string;
  period_end: string;
  scheduled: number;
  completed: number;
  is_partial: boolean;
}

export interface MostSkipped {
  exercise_id: string;
  name: string;
  completion_pct: number;
  skip_count: number;
  main_reason: 'replacement_requested' | null;
}

export interface RpePoint {
  key: string;
  period_start: string;
  period_end: string;
  rpe: number | null;
  has_report: boolean;
  trainer_feedback: string | null;
  is_partial: boolean;
}

export interface MuscleGroupSets {
  muscle_group: string;
  avg_completed_per_week: number;
  avg_scheduled_per_week: number;
}

export interface ReviewItem {
  type: 'exercise_declined' | 'exercise_stalled' | 'fatigue' | 'excessive_effort' | 'exercise_skipped' | 'week_without_training';
  exercise_id: string | null;
  label: string;
}

export interface TrainingEvolution {
  period: { key: EvolutionPeriod; start: string | null; end: string };
  group_by: EvolutionGrouping;
  muscle_group: string | null;
  muscle_groups: string[];
  has_sessions: boolean;
  summary: {
    progress: { improving: number; with_data: number; status: TrafficLight };
    adherence: {
      completed_sessions: number;
      scheduled_sessions: number;
      pct: number | null;
      sets_completion_pct: number | null;
      status: TrafficLight;
    };
    effort: {
      avg_rpe_last_4: number | null;
      trend: 'rising' | 'stable' | 'falling' | null;
      message_key: EffortMessageKey | null;
      status: TrafficLight;
    };
    to_review: { count: number; status: TrafficLight };
  };
  exercises: ExerciseProgress[];
  adherence: AdherenceWeek[];
  most_skipped: MostSkipped[];
  rpe: RpePoint[];
  sets_by_muscle_group: MuscleGroupSets[];
  to_review: ReviewItem[];
}

/** US-35: baja del alumno. */
export type TerminationCategory = 'FALTA_DE_PAGO' | 'RAZONES_PERSONALES' | 'OTRO';

export interface StudentTerminationPayload {
  category: TerminationCategory;
  detail?: string | null;
}

export interface StudentTerminationResult {
  relationship_id: string;
  student_id: string;
  status: 'TERMINATED';
  end_date: string;
  terminated_at: string;
  category: TerminationCategory;
  detail: string | null;
  available_slots: number;
}
