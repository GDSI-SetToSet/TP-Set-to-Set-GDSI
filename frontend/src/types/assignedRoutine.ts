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
}

export interface AssignedRoutineExercise {
  id: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  order_index: number;
  adaptation_notes?: string | null;
  exercise: Exercise;
}

export interface AssignedRoutineBlock {
  id: string;
  name: string;
  order_index: number;
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
  student_id: string;
  template_id?: string | null;
  name: string;
  duration_weeks: number;
  intensity: string;
  status: 'PENDING_REVIEW' | 'APPROVED';
  adaptation_summary?: string | null;
  approved_at?: string | null;
  created_at: string;
  exercise_count: number;
  days: AssignedRoutineDay[];
}
