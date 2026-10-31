import type { Exercise } from './exercise';

export const ROUTINE_INTENSITIES = {
  BAJA: 'Baja',
  MEDIA: 'Media',
  ALTA: 'Alta',
  EXIGENTE: 'Exigente',
} as const;

export type RoutineIntensity = keyof typeof ROUTINE_INTENSITIES;

export interface RoutineExerciseInput {
  exercise_id: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  target_weight_kg: number | null;
}

export interface RoutineBlockInput {
  name: string;
  estimated_duration_minutes: number;
  exercises: RoutineExerciseInput[];
}

export interface RoutineDayInput {
  name: string;
  blocks: RoutineBlockInput[];
}

export interface RoutineTemplateInput {
  name: string;
  duration_weeks: number;
  intensity: RoutineIntensity;
  has_no_materials_alternative: boolean;
  days: RoutineDayInput[];
}

export interface RoutineExercise {
  id: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  target_weight_kg: number | null;
  exercise: Exercise;
}

export interface RoutineBlock {
  id: string;
  name: string;
  estimated_duration_minutes: number | null;
  exercises: RoutineExercise[];
}

export interface RoutineDay {
  id: string;
  name: string;
  blocks: RoutineBlock[];
}

export interface RoutineTemplate {
  id: string;
  trainer_id: string;
  trainer_name: string | null;
  name: string;
  duration_weeks: number;
  intensity: RoutineIntensity;
  has_no_materials_alternative: boolean;
  exercise_count: number;
  days: RoutineDay[];
}

export interface RoutineAssignmentStudent {
  relationship_id: string;
  student_id: string;
  student_name: string;
  routine_template_id: string | null;
  routine_name: string | null;
}
