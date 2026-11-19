export type ProgressPeriodKey = '4w' | '12w' | 'all';

export interface ProgressFilters {
  period: ProgressPeriodKey;
  muscle_group?: string;
}

export interface SetResult {
  weight: number | null;
  reps: number | null;
}

export type MessageKey =
  | 'weight_increased'
  | 'reps_increased'
  | 'no_change'
  | 'below_best'
  | 'bodyweight_reps_increased'
  | 'few_data';

export interface ExercisePoint {
  date: string;
  weight: number | null;
  reps: number;
  target_weight: number | null;
  is_pr: boolean;
}

export interface ExerciseEvolution {
  exercise_id: string;
  name: string;
  muscle_group: string;
  metric: 'max_weight' | 'max_reps';
  start: SetResult;
  current: SetResult;
  best: SetResult;
  message_key: MessageKey;
  weeks_without_change: number;
  last_improvement_is_pr: boolean;
  points: ExercisePoint[];
}

export interface ConsistencyWeek {
  period_start: string;
  period_end: string;
  scheduled: number;
  completed: number;
  is_partial: boolean;
}

export interface RecordEntry {
  date: string;
  exercise_id: string;
  name: string;
  weight: number | null;
  reps: number;
  previous: SetResult;
}

export interface NextExercise {
  exercise_id: string;
  name: string;
  last: SetResult | null;
  target_weight: number | null;
  reps: string;
  sets: number;
  adjusted_by_trainer: boolean;
  trainer_note: string | null;
}

export interface StudentProgress {
  period: { key: ProgressPeriodKey; start: string | null; end: string };
  muscle_group: string | null;
  muscle_groups: string[];
  has_sessions: boolean;
  summary: {
    improving_exercises_last_4w: number;
    streak: { current_weeks: number; best_weeks: number };
    records_in_period: number;
  };
  exercises: ExerciseEvolution[];
  consistency: ConsistencyWeek[];
  records: RecordEntry[];
  new_exercises: { exercise_id: string; name: string; first_date: string }[];
  next_session: { day_name: string; trainer_feedback: string | null; exercises: NextExercise[] } | null;
}

/** US-68: racha de semanas cumplidas (objetivo = días de la rutina vigente). */
export interface TrainingStreak {
  has_routine: boolean;
  weekly_target: number;
  current_weeks: number;
  max_weeks: number;
  this_week_sessions: number;
  week_start: string;
}
