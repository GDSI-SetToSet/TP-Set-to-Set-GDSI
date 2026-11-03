import type { Exercise } from './exercise';

export interface ActiveStudent {
  relationship_id: string;
  student_id: string;
  full_name: string;
  age: number | null;
  fitness_goals: string[];
  protected_zones_count: number;
}

export interface GenerateAIRoutineInput {
  student_id: string;
  template_id: string;
  provider?: 'gemini' | 'heuristic';
}

export interface AssignedRoutineExercise {
  id: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  order_index: number;
  adaptation_notes?: string | null;
  target_weight_kg?: number | null;
  exercise: Exercise;
}

export interface AssignedRoutineBlock {
  id: string;
  name: string;
  order_index: number;
  estimated_duration_minutes?: number | null;
  exercises: AssignedRoutineExercise[];
}

export interface AssignedRoutineDay {
  id: string;
  name: string;
  order_index: number;
  blocks: AssignedRoutineBlock[];
}

export interface AssignedRoutine {
  id: string;
  trainer_id: string;
  trainer_name?: string | null;
  student_id: string;
  template_id?: string | null;
  name: string;
  duration_weeks: number;
  intensity: string;
  has_no_materials_alternative: boolean;
  status: 'PENDING_REVIEW' | 'APPROVED';
  adaptation_summary?: string | null;
  approved_at?: string | null;
  created_at: string;
  exercise_count: number;
  days: AssignedRoutineDay[];
}

export interface TrainerAIRoutine extends AssignedRoutine {
  student_name: string;
  relationship_id: string;
  is_assigned: boolean;
}
