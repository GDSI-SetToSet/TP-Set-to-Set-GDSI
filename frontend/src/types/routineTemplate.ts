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
}

export interface RoutineBlockInput {
  name: string;
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
  exercise: Exercise;
}

export interface RoutineBlock {
  id: string;
  name: string;
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
