export interface ProgressFilters {
  exercise_id?: string;
  muscle_group?: string;
  from?: string;
  to?: string;
}

export interface LoadPoint {
  date: string;
  weight_kg: number;
  reps: string;
  is_pr: boolean;
}

export interface ExerciseLoad {
  exercise_id: string;
  name: string;
  muscle_group: string;
  has_trend: boolean;
  points: LoadPoint[];
}

export interface WeeklyVolume {
  week_start: string;
  week_end: string;
  volume_kg: number;
  is_partial: boolean;
}

export interface WeekComparison {
  current_volume_kg: number;
  previous_volume_kg: number;
  delta_vs_previous_pct: number | null;
  previous_avg_kg: number;
}

export interface PersonalRecordEntry {
  exercise_id: string;
  exercise_name: string;
  weight_kg: number;
  reps: string;
  achieved_at: string;
  previous_weight_kg: number | null;
  is_initial: boolean;
}

export interface StudentProgress {
  range: { from: string; to: string; is_default: boolean };
  muscle_groups: string[];
  has_data: boolean;
  exercises: ExerciseLoad[];
  weekly_volume: WeeklyVolume[];
  week_comparison: WeekComparison;
  personal_records: PersonalRecordEntry[];
}
