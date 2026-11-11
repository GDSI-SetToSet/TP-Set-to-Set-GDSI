export interface ExerciseAlternative {
  exercise_id: string;
  name: string;
  equipment_needed: string;
  variant: { exercise_id: string; name: string } | null;
}

export interface AlternativesResponse {
  alternatives: ExerciseAlternative[];
  can_skip: boolean;
}

export interface ReplacementInput {
  day_name: string;
  original_exercise_id: string;
  replacement_exercise_id: string | null;
}
