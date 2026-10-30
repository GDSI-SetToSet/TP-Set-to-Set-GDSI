export const EXERCISE_CATEGORIES = {
  FUERZA: 'Fuerza',
  CARDIO: 'Cardio',
  MOVILIDAD: 'Movilidad',
  FLEXIBILIDAD: 'Flexibilidad',
  EQUILIBRIO: 'Equilibrio',
} as const;

export type ExerciseCategory = keyof typeof EXERCISE_CATEGORIES;

export interface ExerciseInput {
  name: string;
  description: string;
  category: ExerciseCategory;
  target_muscle_group: string;
  equipment_needed: string;
  has_no_materials_alternative: boolean;
}

export interface Exercise extends ExerciseInput {
  id: string;
  trainer_id: string;
  created_at: string;
  updated_at: string;
}
